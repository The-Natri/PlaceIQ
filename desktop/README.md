# PlaceIQ desktop app (Windows)

A small Electron app that starts PlaceIQ and shows it in its own window,
so you don't have to use a terminal.

- **Download:** `desktop/dist/PlaceIQ-1.0.0-portable.exe` after building (see below).
- **Install:** none. It's a portable .exe; double-click it.

## What it needs

- **Docker Desktop, installed and running.** It's free for personal and
  education use: <https://www.docker.com/products/docker-desktop/>.
  PlaceIQ (database, app and ML service) runs inside Docker, and the desktop
  app only starts it and displays it.
- **Internet on the first launch only.** Docker downloads the base images
  (Postgres, Python, Node) and the libraries. Later launches work offline.
- **About 1 GB of free RAM** while it runs (Docker Desktop's own VM needs more).

## What it does NOT bundle

- **Docker Desktop.** It can't be bundled. If Docker isn't running, the app
  says so and shows a **Retry** button. If Docker isn't installed, it also
  shows a link to download it.
- **Prebuilt images.** The .exe carries PlaceIQ's source (backend, ML service,
  database scripts, UI source). On the first launch Docker **builds** the
  images from it. That takes several minutes (about 4 minutes on the
  development laptop), then the app loads the synthetic dataset and trains the
  model. Later launches take seconds.
- **Code signing.** The .exe is unsigned (signing certificates cost money), so
  Windows SmartScreen may warn "Windows protected your PC". Choose
  **More info → Run anyway**.

## What happens when you open it

1. It checks that Docker is running. If not, it shows a message and a **Retry** button.
2. It runs `docker compose up -d`, the same stack as running it from a terminal.
   A loading screen shows Docker's progress.
3. It waits until `http://localhost:8080/api/health` answers, then shows PlaceIQ.
4. When you close the window, it runs `docker compose down`. The containers
   stop and are removed, and **your data stays** in Docker volumes.

If PlaceIQ was already running (started with `docker compose up` or
`start.ps1`), the app just shows it and leaves it running when you close the
window, because it didn't start it.

The app and the terminal commands share the same containers and data (the
compose project name is fixed in `docker-compose.yml`).

## Logins (synthetic demo data)

- Placement office: `tpo@campus.edu` / `Admin@123`
- Students: any seeded student e-mail / `Student@123`

## Build it

Needs Node.js (free). From this folder:

```bash
npm install
npm run dist        # -> dist/PlaceIQ-1.0.0-portable.exe (and dist/win-unpacked/)
npm start           # or run it without packaging, using the repository as the stack
```

Everything used is free and open source: Electron and electron-builder (MIT).
