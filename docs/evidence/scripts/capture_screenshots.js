// Captures the report screenshots from the running UI. Read-only: it logs in,
// switches tabs and opens dialogs, but never clicks Apply, Save, Close drive or
// any other button that changes data.
//
// Needs: backend on :5000, ML service on :6000, `npm run dev` in frontend/,
// and playwright installed (npm install playwright). Inputs via env vars so the
// script carries no data of its own:
//   SHOT_STUDENT_EMAIL  a seeded student with applications in several states
//   SHOT_DRIVE_ID       a drive with many applicants
//   SHOT_DIR            output folder (default docs/evidence/screenshots)
//   CHROMIUM_PATH       optional local Chromium
const path = require("path");
const { chromium } = require("playwright");

const BASE = process.env.SHOT_BASE || "http://localhost:5173";
const EMAIL = process.env.SHOT_STUDENT_EMAIL;
const DRIVE_ID = process.env.SHOT_DRIVE_ID;
const DIR = process.env.SHOT_DIR || path.join(__dirname, "..", "screenshots");
if (!EMAIL || !DRIVE_ID) throw new Error("set SHOT_STUDENT_EMAIL and SHOT_DRIVE_ID");

(async () => {
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH });
  const page = await browser.newPage({ viewport: { width: 1366, height: 820 }, deviceScaleFactor: 1.5 });
  page.setDefaultTimeout(15000);
  const settle = () => page.waitForTimeout(600); // let entrance transitions finish
  const shot = async (name, target = page, fullPage = true) => {
    await settle();
    const file = path.join(DIR, `${name}.png`);
    await (target === page ? page.screenshot({ path: file, fullPage }) : target.screenshot({ path: file }));
    console.log(`saved ${name}.png`);
  };

  // --- Login ---------------------------------------------------------------
  await page.goto(`${BASE}/login`, { waitUntil: "networkidle" });
  await page.getByRole("heading", { name: "Sign in" }).waitFor();
  await shot("01-login", page, false);

  // --- Student -------------------------------------------------------------
  await page.locator("#login-email").fill(EMAIL);
  await page.locator("#login-password").fill("Student@123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.getByRole("heading", { name: /Welcome,/ }).waitFor();
  await page.getByText("How this is worked out").waitFor();
  await page.getByText(/CGPA standing in your department/).waitFor();
  // Every dashboard request must have answered: the Eligible Drives tab shows
  // its count only once the drive list has loaded.
  await page.getByRole("tab", { name: /Eligible Drives\s*\d+/ }).waitFor();
  await shot("02-student-dashboard");

  const probability = page.locator(".card").filter({ hasText: "Placement probability" }).first();
  await shot("03-probability-widget", probability);

  await page.getByRole("tab", { name: /Eligible Drives/ }).click();
  await page.locator("table tbody tr").first().waitFor();
  await shot("04-eligible-drives");

  await page.getByRole("tab", { name: /My Applications/ }).click();
  await page.locator("table tbody tr").first().waitFor();
  await shot("05-application-tracker");

  // Open the application that reached an offer: rounds, offer and history.
  const offerRow = page.locator("table tbody tr", { hasText: "Offer made" }).first();
  await offerRow.getByRole("button").first().click();
  const dialog = page.getByRole("dialog");
  await dialog.getByText("Status history").waitFor();
  await shot("06-application-detail", dialog);
  await page.keyboard.press("Escape");
  await dialog.waitFor({ state: "detached" });

  await page.getByRole("button", { name: "Logout" }).click();

  // --- Admin ---------------------------------------------------------------
  await page.getByRole("button", { name: "Admin / TPO" }).click();
  await page.locator("#login-email").fill("tpo@campus.edu");
  await page.locator("#login-password").fill("Admin@123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.getByRole("heading", { name: "Placement drives" }).waitFor();
  await page.locator("table tbody tr").first().waitFor();
  await shot("07-admin-dashboard", page, false);

  await page.goto(`${BASE}/admin/drives/${DRIVE_ID}`, { waitUntil: "networkidle" });
  await page.locator("table tbody tr").first().waitFor();
  // Viewport only: 37 applicant rows would make a page-long image.
  await shot("08-drive-detail-applicants", page, false);

  await page.goto(`${BASE}/admin/students`, { waitUntil: "networkidle" });
  await page.locator("table tbody tr").first().waitFor();
  await shot("09-admin-students", page, false);

  const tabs = [
    ["overview", "Overview"],
    ["recruiters", "Recruiters & packages"],
    ["rankings", "Top offers"],
    ["timeline", "Timeline"],
    ["matrix", "Company × department"],
  ];
  for (const [i, [id, label]] of tabs.entries()) {
    await page.goto(`${BASE}/admin/analytics?tab=${id}`, { waitUntil: "networkidle" });
    await page.getByRole("tab", { name: label, selected: true }).waitFor();
    await page.locator(".chart svg, table").filter({ visible: true }).first().waitFor();
    await shot(`1${i}-analytics-${id}`);
  }

  await browser.close();
})().catch((err) => { console.error(err); process.exit(1); });
