# Frontend

React + TypeScript + Vite. See the [project README](../README.md) for backend setup and team conventions.

## Start frontend and backend together

From this `frontend/` directory, run:

```bash
cd ..
python start-dev.py
```

On macOS, use `python3 start-dev.py`. This requires Python 3.11+, Node.js/npm, and uv. Alternatively, run `uv run --no-project --python 3.11 start-dev.py` from the repository root.

The script installs dependencies, applies database migrations, and starts both services. Logs appear in the same terminal. Press **Ctrl+C** to stop both services. Stop any existing servers on ports 8000 and 5173 first.

See [Quick start](../README.md#quick-start-run-both-services) for full instructions.

## Run the frontend separately

Install Node.js 24 LTS, which includes npm. From this directory:

```bash
npm ci
npm run dev
```

On Windows PowerShell, use `npm.cmd` if `npm.ps1` is blocked. The project is already initialized; do not run `create-vite` again.

Open the URL printed by Vite, normally http://localhost:5173. Run the FastAPI backend on port 8000 in a separate terminal. The development proxy forwards `/api/*` to the backend and removes `/api`.

## Source organization

- `src/features/<featureName>/`: one folder per feature, containing its pages, components, logic, and styles.
- `src/common/`: reusable components shared across features.
- `src/assets/`: image and icon source files, optionally grouped by feature.
- `src/App.tsx`: page composition and application routing.
- `src/main.tsx`: application entry point.
- `src/index.css`: global styles.

Keep a component and its CSS together. Use English for comments, user-facing text, and documentation. Use lower camel case for feature folders and PascalCase for React component filenames.

## Checks

```bash
npx tsc -b --pretty false
npm run lint
```

`npm run build` creates production output in `dist/`. This folder is generated and ignored by Git; do not edit it or store source images there. It is not needed for `npm run dev`.

Commit `package.json` and `package-lock.json`, but not `node_modules/`, `dist/`, secrets, or local environment files. After pulling dependency changes, run `npm ci` again.

## Current authentication behavior

Registration and login call the existing FastAPI endpoints. Login state is stored in memory and resets on page refresh. API calls currently use a handwritten adapter in `src/features/userAuth/api.ts`; OpenAPI client generation has not been configured yet.
