// Headless check that PlaceIQ works from ONE URL: the login page, the API,
// a student flow and an admin flow, all through http://localhost:8080 (or
// BASE). It also checks that refreshing on a deep link works (SPA fallback),
// that the browser never contacts another origin or port, and that no
// console errors occur. It applies to one drive as a student, so run it
// against a database whose contents may change (a fresh or demo instance).
//
//   BASE=http://localhost:8080 SL_STUDENT=<seeded student email> node tests/single_link_check.js
// Needs playwright (npm install playwright); CHROMIUM_PATH may point at a local Chromium.
const { chromium } = require("playwright");

const BASE = (process.env.BASE || "http://localhost:8080").replace(/\/$/, "");
const STUDENT = process.env.SL_STUDENT;
const ADMIN = process.env.SL_ADMIN || "tpo@campus.edu";
const ADMIN_PASSWORD = process.env.SL_ADMIN_PASSWORD || "Admin@123";
const STUDENT_PASSWORD = process.env.SL_STUDENT_PASSWORD || "Student@123";
if (!STUDENT) throw new Error("set SL_STUDENT to a seeded student's email");

const results = [];
const check = (name, ok, detail = "") => results.push({ ok: Boolean(ok), name, detail });

(async () => {
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH });
  const page = await browser.newPage({ viewport: { width: 1366, height: 820 } });
  page.setDefaultTimeout(20000);
  const origin = new URL(BASE).origin;
  const foreign = new Set();
  const consoleErrors = [];
  page.on("request", (r) => {
    const u = new URL(r.url());
    if (u.protocol.startsWith("http") && u.origin !== origin) foreign.add(u.origin);
  });
  page.on("console", (m) => { if (m.type() === "error") consoleErrors.push(m.text()); });
  page.on("pageerror", (e) => consoleErrors.push(e.message));

  try {
    // --- Login page and API on the same origin --------------------------------
    const res = await page.goto(`${BASE}/login`, { waitUntil: "networkidle" });
    await page.getByRole("heading", { name: "Sign in" }).waitFor();
    check("Login page served at /login", res.status() === 200, `HTTP ${res.status()}`);
    const health = await page.request.get(`${BASE}/api/health`);
    check("API on the same origin: GET /api/health", health.status() === 200, `HTTP ${health.status()} ${await health.text()}`);

    // --- Student ---------------------------------------------------------------
    await page.locator("#login-email").fill(STUDENT);
    await page.locator("#login-password").fill(STUDENT_PASSWORD);
    await page.getByRole("button", { name: "Sign in" }).click();
    await page.getByRole("heading", { name: /Welcome,/ }).waitFor();
    check("Student signs in and sees the dashboard", true, page.url());
    await page.getByText("How this is worked out").waitFor();
    const pct = await page.locator('[role="meter"]').getAttribute("aria-valuenow");
    check("Placement probability shown (backend -> internal ML service)", pct !== null, `${pct}%`);

    await page.getByRole("tab", { name: /Eligible Drives/ }).click();
    if (process.env.SL_READONLY === "1") {
      // Read-only mode (a demo database that should not change): list only.
      await page.locator("table tbody tr").first().waitFor();
      check("Student sees eligible drives (read-only run, no application made)", true,
        `${await page.locator("table tbody tr").count()} rows`);
      await page.goto(`${BASE}/student?tab=applications`, { waitUntil: "networkidle" });
      await page.locator("table tbody tr").first().waitFor();
      check("Refresh on a deep link (/student?tab=applications) keeps the page", true);
    } else {
      const applyButtons = page.getByRole("button", { name: "Apply" });
      await applyButtons.first().waitFor();
      const row = page.locator("table tbody tr", { has: applyButtons.first() });
      // The cell shows an initial-letter avatar, then the company name, then the role.
      const company = (await row.locator("td").first().innerText()).split("\n").map((t) => t.trim()).find((t) => t.length > 1);
      await applyButtons.first().click();
      await page.locator(".alert-success").waitFor();
      check("Student applies to an eligible drive", true, company);

      await page.goto(`${BASE}/student?tab=applications`, { waitUntil: "networkidle" });
      await page.getByRole("cell", { name: new RegExp(company) }).first().waitFor();
      check("Refresh on a deep link (/student?tab=applications) keeps the page and shows the application", true, company);
    }
    await page.getByRole("button", { name: "Logout" }).click();

    // --- Admin -----------------------------------------------------------------
    await page.getByRole("button", { name: "Admin / TPO" }).click();
    await page.locator("#login-email").fill(ADMIN);
    await page.locator("#login-password").fill(ADMIN_PASSWORD);
    await page.getByRole("button", { name: "Sign in" }).click();
    await page.getByRole("heading", { name: "Placement drives" }).waitFor();
    const drives = await page.locator("table tbody tr").count();
    check("Admin signs in and sees the drive list", drives > 0, `${drives} drives`);

    const href = await page.locator('table tbody tr a[href^="/admin/drives/"]').first().getAttribute("href");
    await page.goto(`${BASE}${href}`, { waitUntil: "networkidle" });
    await page.getByText("Applications close").waitFor();
    check(`Refresh on a deep link (${href}) loads the drive detail`, true);

    await page.goto(`${BASE}/admin/analytics?tab=timeline`, { waitUntil: "networkidle" });
    await page.locator(".chart svg").first().waitFor();
    check("Analytics (timeline) loads by direct URL", true);

    const missing = await page.request.get(`${BASE}/api/no-such-endpoint`);
    check("Unknown /api path is a JSON 404", missing.status() === 404 && (missing.headers()["content-type"] || "").includes("json"),
      `HTTP ${missing.status()}`);
  } catch (err) {
    check("Flow completed without error", false, err.message.split("\n")[0]);
  }

  check("Browser contacted no other origin or port", foreign.size === 0, [...foreign].join(", ") || "only " + origin);
  check("No console or page errors", consoleErrors.length === 0, consoleErrors.slice(0, 3).join(" | "));
  await browser.close();

  for (const r of results) console.log(`${r.ok ? "PASS" : "FAIL"} | ${r.name.padEnd(92)} | ${r.detail}`);
  const passed = results.filter((r) => r.ok).length;
  console.log(`\nTOTAL: ${passed}/${results.length} passed  (${BASE})`);
  process.exit(passed === results.length ? 0 : 1);
})();
