# CS 673 Project — Backend

FastAPI backend with user accounts: sign up, log in, and a login-protected endpoint.

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

You need **git** and **uv**. uv installs Python for you.

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
git clone https://github.com/Lambor888/CS673P-ro-je-c-t.git
cd CS673P-ro-je-c-t/backend
uv sync
uv run alembic upgrade head
```

`uv sync` installs the dependencies. `alembic upgrade head` creates your local database (`backend/dev.db`).

## Run

From the `backend/` folder:

```bash
uv run fastapi dev app/main.py
```

Open **http://localhost:8000/docs** — you can try every endpoint from the browser.

The server restarts by itself when you save a file. Stop it with `Ctrl+C`.

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

```bash
uv sync
uv run alembic upgrade head
```

If you see `no such table` or `no such column`, you skipped the second command.

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
