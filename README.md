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
| POST | `/auth/register` | no | Create an account. JSON: `{"username": "...", "email": "...", "password": "..."}` |
| POST | `/auth/login` | no | Log in with form fields `username` (or your email), `password`. Returns a token |
| POST | `/auth/google` | no | Sign in or sign up with Google. JSON: `{"credential": "<ID token from the Google button>"}` |
| GET | `/auth/me` | yes | Your account (username, email, sign-in methods) |
| PATCH | `/auth/me` | yes | Change your username. JSON: `{"username": "..."}` |
| POST | `/auth/password` | yes | Change your password (or set a first one on a Google-only account) |
| POST | `/auth/google/link` | yes | Connect a Google account to your account |
| GET | `/profile/stats` | yes | Your single player stats |

- Usernames: 3–20 characters (letters, numbers, `_`), case-insensitive (`Bob` = `bob`)
- Emails: required at sign-up, one account per email, case-insensitive
- Passwords: 8–128 characters, stored hashed (never in plain text). Google-only accounts have none until they set one
- Signing in with Google never takes over an existing account with the same email (emails aren't verified at sign-up). Log in with your password, then connect Google from your profile
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

## Google Maps keys (needed for single player)

Login and lobbies work without this. **Single player won't start until you do these steps once.**

**1. Get a key.** If a teammate already has one, ask them for it and skip to step 2. Otherwise:
1. Go to https://console.cloud.google.com and create a project. Google asks you to add billing, but normal development use is free.
2. Open **APIs & Services → Library**. Search for and **Enable** both **Maps JavaScript API** and **Street View Static API**.
3. Open **APIs & Services → Credentials → Create credentials → API key**. Copy the key.

**2. Create the two key files.** Run this from the repository root (it works in PowerShell too):

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local
```

**3. Paste your key** after the `=` in both files, with no spaces or quotes:
- `backend/.env` → `GOOGLE_MAPS_API_KEY=your-key`
- `frontend/.env.local` → `VITE_GOOGLE_MAPS_API_KEY=your-key`

**4. Restart:** press `Ctrl+C`, then run `python start-dev.py` again.

⚠ **Never commit or share these files publicly.** Git already ignores them. If you ever see `.env` or `.env.local` in `git status`, stop and ask.

## Sign in with Google (optional)

Everything else works without this; the Google button just doesn't show until you set it up. It needs one **OAuth client ID** (not an API key, and there's no secret to keep).

**1. Get a client ID.** If a teammate already has one, ask them for it and skip to step 2. Otherwise, in the same Google Cloud project as the Maps key:
1. Open **APIs & Services → OAuth consent screen** (Google may call it **Google Auth Platform**). Choose **External**, fill in the app name and your email, and save. While the app is in **Testing**, add each teammate's Gmail under **Test users**.
2. Open **APIs & Services → Credentials → Create credentials → OAuth client ID**. Application type: **Web application**.
3. Under **Authorized JavaScript origins** add `http://localhost:5173` and `http://localhost`. No redirect URIs are needed.
4. Copy the **Client ID** (it ends in `.apps.googleusercontent.com`).

**2. Paste it** into the same files as the Maps key, in both:
- `backend/.env` → `GOOGLE_CLIENT_ID=your-client-id`
- `frontend/.env.local` → `VITE_GOOGLE_CLIENT_ID=your-client-id`

**3. Restart**, and open the app at `http://localhost:5173`. Google rejects `127.0.0.1` unless you add that origin as well.

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

### Automatic checks

GitHub Actions runs backend tests (Python 3.12) and frontend build/type checks
and lint (Node.js 24) on every pull request and push to `main`. Both jobs install
from the committed lockfiles. See the PR's **Checks** tab for results.

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
│   ├── main.py          # creates the app, registers routers, serves /health
│   ├── config.py        # shared settings
│   ├── db.py            # shared database connection and Base
│   ├── scoring.py       # existing distance calculation utility
│   └── modules/
│       ├── auth/
│       │   ├── router.py    # /auth/... (register, login, Google, account changes)
│       │   ├── service.py   # account rules (login by email, Google accounts and linking)
│       │   ├── google.py    # verifies Google sign-in tokens
│       │   ├── models.py    # User database model
│       │   ├── schemas.py   # authentication request/response models
│       │   ├── security.py  # password hashing and JWT helpers
│       │   └── deps.py      # get_current_user dependency
│       ├── profile/
│       │   ├── router.py    # /profile/stats
│       │   ├── models.py    # RoundResult: one row per scored round
│       │   └── service.py   # record_round (call it from any game mode) and stats
│       └── lobby/
│           ├── router.py    # existing /ws entry point and runtime state
│           └── service.py   # existing player, lobby, and manager classes
├── migrations/          # database changes (Alembic)
├── tests/
└── pyproject.toml       # dependencies
```

Backend business modules live under `app/modules/`. Their boundaries do not need to match frontend pages; future ranking logic can become its own module. Shared configuration and database infrastructure remain at the app level.

