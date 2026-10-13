# CS 673 Group Project

React + TypeScript + Vite frontend and FastAPI backend. The frontend currently provides registration and login. The backend provides user accounts and a login-protected endpoint.

## Quick start: run both services

Install **Node.js 24 LTS (including npm)**, **uv**, and **Python 3.11+** first. After cloning, open a terminal in the repository root, which contains `start-dev.py`, `frontend/`, and `backend/`.

**Windows (PowerShell):**

```powershell
cd "E:\CS 673\CS673_Group_Proj"
python start-dev.py
```

**macOS:**

```bash
cd /path/to/CS673_Group_Proj
python3 start-dev.py
```

Replace the example directory with your local checkout path. If Python is not installed separately, uv can manage it on either platform:

```bash
uv run --no-project --python 3.11 start-dev.py
```

The script automatically:

1. Synchronizes backend dependencies from the lockfile with `uv sync --locked`.
2. Applies database migrations with `alembic upgrade head`.
3. Installs frontend dependencies with `npm ci`.
4. Starts both servers and checks that they respond.

You do not need to run the individual install or startup commands below when using this script. It does not run `git pull` or upgrade dependency versions.

- Frontend: http://127.0.0.1:5173
- Backend API documentation: http://127.0.0.1:8000/docs
- Live logs: shown in the same terminal with `[backend]` and `[frontend]` prefixes.
- Stop both services: press **Ctrl+C** in the script's terminal.
- Saved logs: `.dev-logs/backend.log` and `.dev-logs/frontend.log`. Logs are overwritten on each run and ignored by Git. You can delete `.dev-logs/` after stopping the servers; it is recreated automatically.

Stop existing servers on ports **8000** and **5173** before running the script. To check tools, files, and ports without installing dependencies or starting services:

```bash
python start-dev.py --check
```

Use `python3` instead of `python` on macOS. The script also accepts an absolute path and works from any working directory.

## What's built

| Method | Path | Needs login? | What it does |
|---|---|---|---|
| GET | `/health` | no | Check the server is up |
| POST | `/auth/register` | no | Create an account. JSON: `{"username": "...", "password": "..."}` |
| POST | `/auth/login` | no | Log in with form fields `username`, `password`. Returns a token |
| GET | `/auth/me` | yes | Returns the logged-in user |

- Usernames: 3–20 characters (letters, numbers, `_`), case-insensitive (`Bob` = `bob`)
- Passwords: 8–128 characters, stored hashed (never in plain text)
- Login tokens last 24 hours

## Setup (once)

You need **Git**, **Node.js 24 LTS** (includes npm), and **uv**. uv installs Python for you. Reopen your terminal after installing these tools.

Check your environment:

```bash
git --version
node --version
npm --version
uv --version
```

On Windows PowerShell, use `npm.cmd` instead of `npm` if script execution policy blocks `npm.ps1`.

**Install uv**

macOS / Linux:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Windows (PowerShell):
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Reopen your terminal, then check it worked: `uv --version`

**Clone and install**

```bash
git clone https://github.com/Lambor888/CS673_Group_Proj.git
cd CS673_Group_Proj/backend
uv sync
uv run alembic upgrade head
```

`uv sync` installs the dependencies. `alembic upgrade head` creates your local database (`backend/dev.db`).

## Run the backend

### Start the backend individually

From the `backend/` folder:

```bash
uv run fastapi dev app/main.py
```

Open **http://localhost:8000/docs** — you can try every endpoint from the browser.

The server restarts by itself when you save a file. Stop it with `Ctrl+C`.

## Set up and run the frontend

The frontend is already initialized in this repository. After cloning, install its dependencies; do not run `create-vite` again.

Open a second terminal at the repository root:

```bash
cd frontend
npm ci
npm run dev
```

Open the local URL printed by Vite, normally **http://localhost:5173**. Keep both the frontend and backend terminals running to use registration and login. Stop either server with `Ctrl+C` in its terminal.

During development, `frontend/vite.config.ts` forwards `/api/*` requests to `http://127.0.0.1:8000`, removing the `/api` prefix. For example, `/api/auth/login` reaches `/auth/login` on the backend. This proxy is for development; a production deployment needs its own API routing configuration.

The current login state is kept in memory, so refreshing the page requires logging in again.

From `frontend/`, the available checks are:

```bash
npx tsc -b --pretty false
npm run lint
```

To create a production build, run `npm run build`. This generates `frontend/dist/` automatically. `dist/` is build output, not a source or image folder, and must not be committed. Running the development server does not require a production build.

## Frontend organization conventions

```text
frontend/src/
├── features/
│   └── userAuth/
│       ├── AuthPage.tsx
│       ├── AuthPage.css
│       └── api.ts
├── common/                # Reusable components shared across features
├── assets/                # Image and icon source files
├── App.tsx                # Compose pages and application routes
├── main.tsx               # Application entry point
└── index.css              # Global styles
```

- Create a separate folder under `src/features/` for each feature, such as `userAuth`, `lobby`, or `game`. Keep its pages, feature-specific components, logic, and styles inside that folder.
- Use lower camel case for feature folders and PascalCase for React component filenames, such as `LoginForm.tsx`.
- Keep component styles next to their component. Use CSS Modules when scoped styles are needed, such as `LoginForm.module.css`. Add `pages/` or `components/` subfolders only when a feature needs them.
- Put reusable components shared across features in `src/common/`, such as `Button.tsx` or `Modal.tsx`. Keep feature-specific business logic in its feature folder.
- Keep image and icon source files in `src/assets/`. Feature subfolders such as `src/assets/userAuth/` are allowed. Import these assets from components; do not put source images in `dist/`.
- Use English for code comments, interface text, validation messages, and documentation.
- Commit `package.json` and `package-lock.json`. Do not commit `node_modules/`, `dist/`, secrets, or local environment files.

See [the frontend README](frontend/README.md) for a short setup reference.

## Try it out

1. In `/docs`, open **POST /auth/register** → *Try it out* → create a user
2. Click **Authorize** (top right) → enter that username and password
3. Open **GET /auth/me** → *Try it out* → you should see your user

## Run the tests

```bash
uv run pytest
```

Tests use a temporary database and never touch your `dev.db`.

## After every `git pull`

From `backend/`:

```bash
uv sync
uv run alembic upgrade head
```

If you see `no such table` or `no such column`, you skipped the second command.

If frontend dependencies changed, run `npm ci` from `frontend/` before restarting its development server.

## Reset your local database

Delete `backend/dev.db`, then run `uv run alembic upgrade head`.

## Where things are

```
backend/
├── app/
│   ├── main.py          # starts the app
│   ├── config.py        # settings
│   ├── db.py            # database connection
│   ├── models.py        # database tables
│   ├── schemas.py       # what the API accepts and returns
│   ├── security.py      # password hashing + login tokens
│   ├── deps.py          # get_current_user (login check)
│   └── routers/
│       └── auth.py      # /auth endpoints
├── migrations/          # database changes (Alembic)
├── tests/
└── pyproject.toml       # dependencies
```
