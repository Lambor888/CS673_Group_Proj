"""Sync dependencies and run both development servers on Windows and macOS."""

import argparse
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener

ROOT = Path(__file__).resolve().parent
LOGS = ROOT / '.dev-logs'
WINDOWS = os.name == 'nt'


class Runner:
    def __init__(self):
        self.processes = []
        self.readers = []

    def start(self, name, command, directory):
        LOGS.mkdir(exist_ok=True)
        log = (LOGS / f'{name}.log').open('w', encoding='utf-8')
        options = ({'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP}
                   if WINDOWS else {'start_new_session': True})
        try:
            process = subprocess.Popen(
                command, cwd=directory, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                text=True, encoding='utf-8', errors='replace', bufsize=1,
                env={**os.environ, 'PYTHONUNBUFFERED': '1', 'PYTHONIOENCODING': 'utf-8'},
                **options,
            )
        except BaseException:
            log.close()
            raise
        self.processes.append(process)

        def relay():
            try:
                for line in process.stdout:
                    log.write(line)
                    log.flush()
                    print(f'[{name}] {line.rstrip()}', flush=True)
            finally:
                process.stdout.close()
                log.close()

        reader = threading.Thread(target=relay, daemon=True)
        reader.start()
        self.readers.append(reader)
        return process

    def step(self, name, command, directory):
        print(f'Running {name}...', flush=True)
        process = self.start(name, command, directory)
        code = process.wait()
        if code:
            raise RuntimeError(f'{name} failed (exit code {code}). Startup cancelled.')

    def stop(self):
        for process in reversed(self.processes):
            if WINDOWS:
                if process.poll() is None:
                    subprocess.run(
                        ['taskkill', '/PID', str(process.pid), '/T', '/F'],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        check=False,
                    )
            else:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
        for process in self.processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                if WINDOWS:
                    process.kill()
                else:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                process.wait(timeout=5)
            if not WINDOWS:
                # A reload worker may outlive its parent.
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        for reader in self.readers:
            reader.join(timeout=2)


def preflight():
    tools = {}
    for name in ('uv', 'node', 'npm.cmd' if WINDOWS else 'npm'):
        tools[name] = shutil.which(name)
        if not tools[name]:
            raise RuntimeError(f'{name} was not found. Install it and reopen your terminal.')
    for name in ('backend/pyproject.toml', 'backend/uv.lock', 'frontend/package-lock.json'):
        if not (ROOT / name).is_file():
            raise RuntimeError(f'Missing project file: {name}')
    for port in (8000, 5173):
        with socket.socket() as listener:
            if WINDOWS:
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            try:
                listener.bind(('127.0.0.1', port))
            except OSError as error:
                raise RuntimeError(f'Port {port} is unavailable. Stop existing servers first.') from error
    return tools


def wait_ready(services, timeout=60):
    opener = build_opener(ProxyHandler({}))
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if any(process.poll() is not None for process in services):
            raise RuntimeError(f'A server exited during startup. See {LOGS}.')
        try:
            with opener.open('http://127.0.0.1:8000/health', timeout=2) as response:
                healthy = json.load(response).get('status') == 'ok'
            with opener.open('http://127.0.0.1:5173', timeout=2) as response:
                if healthy and response.status == 200:
                    return
        except (URLError, OSError, ValueError):
            pass
        time.sleep(1)
    raise RuntimeError(f'Server startup timed out. See {LOGS}.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Check tools, files and ports without installing or starting anything.')
    args = parser.parse_args()
    runner = Runner()
    try:
        tools = preflight()
        if args.check:
            print('Preflight checks passed.')
            return 0
        backend, frontend = ROOT / 'backend', ROOT / 'frontend'
        uv, node = tools['uv'], tools['node']
        npm = tools['npm.cmd' if WINDOWS else 'npm']
        # Invoke npm via Node on Windows to avoid cmd.exe quoting and shell policies.
        if WINDOWS:
            npm_cli = Path(npm).parent / 'node_modules/npm/bin/npm-cli.js'
            if not npm_cli.is_file():
                raise RuntimeError(f'Cannot locate npm CLI at {npm_cli}. Check your Node.js installation.')
            npm_command = [node, str(npm_cli)]
        else:
            npm_command = [npm]
        runner.step('backend-sync', [uv, 'sync', '--locked'], backend)
        runner.step('migrations', [uv, 'run', '--no-sync', 'alembic', 'upgrade', 'head'], backend)
        runner.step('frontend-install', [*npm_command, 'ci'], frontend)
        backend_process = runner.start('backend', [uv, 'run', '--no-sync', 'fastapi', 'dev', 'app/main.py', '--host', '127.0.0.1', '--port', '8000'], backend)
        frontend_process = runner.start('frontend', [node, str(frontend / 'node_modules/vite/bin/vite.js'), '--host', '127.0.0.1', '--port', '5173', '--strictPort'], frontend)
        services = [backend_process, frontend_process]
        wait_ready(services)
        print('\nFrontend: http://127.0.0.1:5173\nBackend docs: http://127.0.0.1:8000/docs\nPress Ctrl+C to stop both services.', flush=True)
        while True:
            if any(process.poll() is not None for process in services):
                raise RuntimeError(f'A server stopped. See {LOGS}.')
            time.sleep(0.5)
    except KeyboardInterrupt:
        print('\nStopping development services...', flush=True)
        return 0
    except (OSError, RuntimeError) as error:
        print(f'Error: {error}', file=sys.stderr)
        return 1
    finally:
        # Allow cleanup to finish even if Ctrl+C is pressed a second time.
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        runner.stop()


if __name__ == '__main__':
    sys.exit(main())
