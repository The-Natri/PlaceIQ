// PlaceIQ desktop app (Electron).
//
// A launcher, not a rewrite: it runs the same Docker stack as
// `docker compose up` (docker-compose.yml) and shows http://localhost:8080 in
// its own window. Steps: check Docker -> start the stack -> wait for
// /api/health (loading screen) -> open the app -> on quit, stop the stack.
//
// Docker Desktop must be installed; the app does not bundle it (see README).
const { app, BrowserWindow, ipcMain, shell } = require("electron");
const { execFile, spawn } = require("child_process");
const path = require("path");
const http = require("http");

const APP_URL = "http://localhost:8080";
const HEALTH_URL = "http://127.0.0.1:8080/api/health";
// Must match `name:` in docker-compose.yml, so the app and a terminal
// `docker compose up` share the same containers and data.
const PROJECT = "college-placement-system";
// Installed: the stack's files are bundled under resources/stack.
// Development (npm start in desktop/): the repository itself.
const STACK_DIR = app.isPackaged ? path.join(process.resourcesPath, "stack") : path.join(__dirname, "..");
const COMPOSE = ["compose", "--project-name", PROJECT, "-f", path.join(STACK_DIR, "docker-compose.yml")];
// First start builds the images, loads the data and trains the model.
const FIRST_START_TIMEOUT_MS = 15 * 60 * 1000;

let win = null;
let weStartedTheStack = false;
let shuttingDown = false;

function status(text, kind = "progress") {
  if (win && !win.isDestroyed()) win.webContents.send("status", { text, kind });
}

function healthy() {
  return new Promise((resolve) => {
    const req = http.get(HEALTH_URL, { timeout: 3000 }, (res) => {
      res.resume();
      resolve(res.statusCode === 200);
    });
    req.on("error", () => resolve(false));
    req.on("timeout", () => { req.destroy(); resolve(false); });
  });
}

function dockerRunning() {
  return new Promise((resolve) => {
    execFile("docker", ["info"], { timeout: 20000, windowsHide: true }, (err) => {
      if (!err) return resolve("running");
      resolve(err.code === "ENOENT" ? "missing" : "stopped");
    });
  });
}

// Runs `docker compose ...`, forwarding its progress lines to the loading screen.
function compose(args) {
  return new Promise((resolve) => {
    const child = spawn("docker", [...COMPOSE, ...args], { cwd: STACK_DIR, windowsHide: true });
    let tail = "";
    const onData = (buf) => {
      const lines = buf.toString().split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
      if (lines.length) {
        tail = lines[lines.length - 1];
        status(tail);
      }
    };
    child.stdout.on("data", onData);
    child.stderr.on("data", onData);
    child.on("error", (err) => resolve({ ok: false, detail: err.message }));
    child.on("close", (code) => resolve({ ok: code === 0, detail: tail }));
  });
}

async function startStack() {
  status("Checking Docker…");
  const docker = await dockerRunning();
  if (docker === "missing") {
    return status("Docker Desktop is not installed. PlaceIQ runs inside Docker: install Docker Desktop (free for personal and education use), start it, then press Retry.", "error-install");
  }
  if (docker === "stopped") {
    return status("Docker Desktop is not running. Start it, wait until it shows “Engine running”, then press Retry.", "error");
  }

  if (await healthy()) {
    // Started outside the app (docker compose up or start.ps1): just show
    // it, and leave it running on quit, since it isn't ours to stop.
    status("PlaceIQ is already running. Opening…");
    return win.loadURL(APP_URL);
  }

  status("Starting PlaceIQ (the first start builds everything and takes several minutes)…");
  const up = await compose(["up", "-d"]);
  if (!up.ok) {
    return status(`Docker could not start PlaceIQ: ${up.detail || "unknown error"}. If port 8080 is used by another program, close it, then press Retry.`, "error");
  }
  weStartedTheStack = true;

  status("Waiting for PlaceIQ to be ready…");
  const deadline = Date.now() + FIRST_START_TIMEOUT_MS;
  while (Date.now() < deadline) {
    if (await healthy()) {
      status("Ready. Opening…");
      return win.loadURL(APP_URL);
    }
    await new Promise((r) => setTimeout(r, 2000));
  }
  status("PlaceIQ did not become ready in time. Check Docker Desktop (Containers → placeiq_app → Logs), then press Retry.", "error");
}

function createWindow() {
  win = new BrowserWindow({
    width: 1366,
    height: 860,
    minWidth: 900,
    minHeight: 600,
    title: "PlaceIQ",
    backgroundColor: "#0f1b3d",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });
  win.setMenuBarVisibility(false);

  // The window only ever shows PlaceIQ itself. Any other link (an external
  // site) opens in the normal browser instead of inside the app.
  win.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });
  win.webContents.on("will-navigate", (event, url) => {
    if (!url.startsWith(APP_URL) && !url.startsWith("file:")) {
      event.preventDefault();
      shell.openExternal(url);
    }
  });

  win.loadFile(path.join(__dirname, "loading.html"));
  win.webContents.once("did-finish-load", startStack);
}

ipcMain.on("retry", () => {
  win.loadFile(path.join(__dirname, "loading.html"));
  win.webContents.once("did-finish-load", startStack);
});
ipcMain.on("open-docker-download", () => shell.openExternal("https://www.docker.com/products/docker-desktop/"));

app.whenReady().then(createWindow);
app.on("window-all-closed", () => app.quit());

// Stop the stack before the app exits, so no containers are left running
// (data stays in the Docker volumes). The quit is held until that is done.
app.on("before-quit", (event) => {
  if (!weStartedTheStack || shuttingDown) return;
  event.preventDefault();
  shuttingDown = true;
  if (win && !win.isDestroyed()) {
    win.loadFile(path.join(__dirname, "loading.html"));
    win.webContents.once("did-finish-load", () => status("Stopping PlaceIQ…"));
  }
  compose(["down"]).then(() => app.exit(0));
});
