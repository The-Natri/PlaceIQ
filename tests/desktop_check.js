// Drives the PACKAGED desktop app (desktop/dist/win-unpacked/PlaceIQ.exe):
// it must start the Docker stack, show PlaceIQ, let a student and the admin
// sign in, and stop the stack when the window is closed.
//   DESKTOP_EXE=... SL_STUDENT=<email> node tests/desktop_check.js
const { _electron: electron } = require("playwright");
const { execSync } = require("child_process");

const results = [];
const check = (name, ok, detail = "") => results.push({ ok: Boolean(ok), name, detail });
const containers = () => execSync('docker ps --format "{{.Names}}"').toString().trim().split(/\s+/).filter(Boolean);

(async () => {
  delete process.env.ELECTRON_RUN_AS_NODE;
  check("Before launch: no PlaceIQ containers running", containers().length === 0, containers().join(",") || "none");
  const t0 = Date.now();
  // Electron treats ELECTRON_RUN_AS_NODE as set even when empty, so it is removed outright.
  const env = { ...process.env };
  delete env.ELECTRON_RUN_AS_NODE;
  const app = await electron.launch({ executablePath: process.env.DESKTOP_EXE, env });
  const proc = app.process();  // kept: the handle is disposed once the app exits
  const win = await app.firstWindow();
  try {
    await win.waitForURL("http://localhost:8080/**", { timeout: 15 * 60 * 1000 });
    check("App started the stack and opened http://localhost:8080", true, `${Math.round((Date.now() - t0) / 1000)}s`);
    check("Containers started by the app", containers().length === 3, containers().join(","));
    // The app keeps its login between launches (like a browser), so a
    // previous session may still be open: sign out first if so.
    await win.waitForLoadState("networkidle");
    if (!win.url().includes("/login")) await win.getByRole("button", { name: "Logout" }).click();
    await win.getByRole("heading", { name: "Sign in" }).waitFor({ timeout: 30000 });
    await win.locator("#login-email").fill(process.env.SL_STUDENT);
    await win.locator("#login-password").fill("Student@123");
    await win.getByRole("button", { name: "Sign in" }).click();
    await win.getByRole("heading", { name: /Welcome,/ }).waitFor({ timeout: 30000 });
    check("Student signs in inside the app window", true);
    await win.getByRole("button", { name: "Logout" }).click();
    await win.getByRole("button", { name: "Admin / TPO" }).click();
    await win.locator("#login-email").fill("tpo@campus.edu");
    await win.locator("#login-password").fill("Admin@123");
    await win.getByRole("button", { name: "Sign in" }).click();
    await win.getByRole("heading", { name: "Placement drives" }).waitFor({ timeout: 30000 });
    check("Admin signs in inside the app window", true);
    if (process.env.SHOT) await win.screenshot({ path: process.env.SHOT });
  } catch (e) {
    check("Flow completed", false, e.message.split("\n")[0] + " (page: " + win.url() + ")");
    if (process.env.SHOT_FAIL) await win.screenshot({ path: process.env.SHOT_FAIL }).catch(() => {});
  }
  // Close the window the way a user does; the app stops the stack before exiting.
  const closed = proc.exitCode !== null ? Promise.resolve() : new Promise((r) => proc.on("exit", r));
  await win.close();
  await Promise.race([closed, new Promise((r) => setTimeout(r, 120000))]);
  check("App exited after the window was closed", proc.exitCode !== null, `exit code ${proc.exitCode}`);
  check("After quit: no containers left running", containers().length === 0, containers().join(",") || "none");
  const left = execSync('tasklist /FI "IMAGENAME eq PlaceIQ.exe" /NH').toString();
  check("After quit: no PlaceIQ.exe processes left", !/PlaceIQ\.exe/i.test(left), left.trim().split("\n")[0]);
  for (const r of results) console.log(`${r.ok ? "PASS" : "FAIL"} | ${r.name.padEnd(55)} | ${r.detail}`);
  const passed = results.filter((r) => r.ok).length;
  console.log(`\nTOTAL: ${passed}/${results.length} passed`);
  process.exit(passed === results.length ? 0 : 1);
})();
