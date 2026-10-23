// UI walkthrough of both roles in headless Chromium (Playwright).
//
// It WRITES data (an application, a new drive, an offer), so run it before
// re-seeding, not against data you want to keep.
//
// Setup (once, anywhere outside the repo):  npm install playwright && npx playwright install chromium
// Run (frontend on :5173, backend + ML service running):
//   WT_EMAIL=... WT_REG=... WT_NAME=... WT_DRIVE_ID=... WT_COMPANY=... WT_ROLE="Walkthrough Role" //   node tests/ui_walkthrough.js
// WT_* = a Not Placed student and the first drive in their eligible list.
// Screenshots go to ./wt (or WT_SHOTS). CHROMIUM_PATH selects a Chromium build.
const { chromium } = require('playwright');
const fs = require('fs');

const BASE = 'http://localhost:5173';
// Student + the first drive in their eligible list, passed in by the caller
// (WT_EMAIL, WT_REG, WT_NAME, WT_DRIVE_ID, WT_COMPANY, WT_ROLE).
const STUDENT = { email: process.env.WT_EMAIL, reg: process.env.WT_REG, name: process.env.WT_NAME };
const DRIVE_ID = Number(process.env.WT_DRIVE_ID);
const COMPANY = process.env.WT_COMPANY;
const NEW_ROLE = process.env.WT_ROLE;
const FIRST = STUDENT.name.split(' ')[0];
const SHOTS = process.env.WT_SHOTS || 'wt';
fs.mkdirSync(SHOTS, { recursive: true });

const results = [];
const consoleErrors = [];
function check(name, ok, detail = '') {
  results.push(`${ok ? 'PASS' : 'FAIL'} | ${name}${detail ? ' | ' + detail : ''}`);
}
async function step(name, fn) {
  try { await fn(); check(name, true); console.log("PASS | " + name); }
  catch (e) { const m = String(e.message || e).split('\n')[0].slice(0, 200); check(name, false, m); console.log("FAIL | " + name + " | " + m); }
}

(async () => {
  const browser = await chromium.launch(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {});
  const ctx = await browser.newContext({ viewport: { width: 1366, height: 860 } });
  const page = await ctx.newPage();
  page.setDefaultTimeout(15000);
  page.on('pageerror', (e) => consoleErrors.push(`pageerror: ${e.message}`));
  page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(`console: ${m.text()}`); });
  page.on('response', (r) => { if (r.status() >= 400) consoleErrors.push(`HTTP ${r.status()} ${r.request().method()} ${r.url()}`); });
  const shot = (n, opts = {}) => page.screenshot({ path: `${SHOTS}/${n}.png`, fullPage: true, ...opts });
  const alertText = async () => (await page.locator('.alert').first().innerText()).trim();

  // ------------------------------------------------------------- student
  await step('Login page renders', async () => {
    await page.goto(`${BASE}/login`, { waitUntil: 'networkidle' });
    await page.getByRole('heading', { name: 'Sign in' }).waitFor();
    await shot('01-login');
  });

  await step('Login form validation shows field errors', async () => {
    await page.getByRole('button', { name: 'Sign in' }).click();
    await page.getByText('Enter your email address.').waitFor({ timeout: 3000 });
  });

  await step('Student logs in -> dashboard overview', async () => {
    await page.locator('#login-email').fill(STUDENT.email);
    await page.locator('#login-password').fill('Student@123');
    await page.getByRole('button', { name: 'Sign in' }).click();
    await page.waitForURL('**/student**');
    await page.getByRole('heading', { name: new RegExp(`Welcome, ${FIRST}`) }).waitFor();
  });

  await step('Placement probability widget shows a % and explanation', async () => {
    await page.getByText('How this is worked out').waitFor({ timeout: 10000 });
    const pct = await page.locator('[role="meter"]').getAttribute('aria-valuenow');
    if (pct === null) throw new Error('no meter value');
    check('...probability value', true, `${pct}%`);
    await page.getByText(/CGPA standing in your department/).waitFor();
    await shot('02-student-overview');
  });

  await step('Eligible Drives tab lists drives with Apply buttons', async () => {
    await page.getByRole('tab', { name: /Eligible Drives/ }).click();
    await page.getByRole('button', { name: 'Apply' }).first().waitFor();
    const rows = await page.locator('table tbody tr').count();
    check('...eligible drive rows', rows > 0, `${rows} rows`);
    await shot('03-student-eligible-drives');
  });

  await step('Student applies to the first drive', async () => {
    const firstRow = page.locator('table tbody tr').first();
    const company = await firstRow.locator('td').first().innerText();
    await firstRow.getByRole('button', { name: 'Apply' }).click();
    await page.locator('.alert-success').waitFor();
    const msg = await alertText();
    if (!msg.includes(COMPANY)) throw new Error(`unexpected: ${msg} (row ${company})`);
    await firstRow.getByText('Applied', { exact: true }).waitFor();
    await shot('04-student-applied');
  });

  await step('My Applications tab shows the tracker; detail opens with history', async () => {
    await page.getByRole('tab', { name: /My Applications/ }).click();
    await page.getByRole('cell', { name: new RegExp(COMPANY) }).first().waitFor();
    await shot('05-student-applications');
    await page.locator('table tbody tr').first().getByRole('button').click();
    await page.getByRole('dialog').getByText('Status history').waitFor();
    await shot('06-student-application-detail', { fullPage: false });
    await page.keyboard.press('Escape');
    await page.getByRole('dialog').waitFor({ state: 'detached' });
  });

  await step('Student logs out', async () => {
    await page.getByRole('button', { name: 'Logout' }).click();
    await page.waitForURL('**/login');
  });

  // ------------------------------------------------------------- admin
  await step('Admin logs in -> drives list', async () => {
    await page.getByRole('button', { name: 'Admin / TPO' }).click();
    await page.locator('#login-email').fill('tpo@campus.edu');
    await page.locator('#login-password').fill('Admin@123');
    await page.getByRole('button', { name: 'Sign in' }).click();
    await page.waitForURL('**/admin**');
    await page.getByRole('heading', { name: 'Placement drives' }).waitFor();
    await page.locator('table tbody tr').first().waitFor();
    await shot('07-admin-drives');
  });

  let newDriveUrl = '';
  await step('New drive form validates, then creates a drive', async () => {
    await page.getByRole('button', { name: 'New drive' }).click();
    const dlg = page.getByRole('dialog');
    await dlg.getByRole('button', { name: 'Create drive' }).click();
    await dlg.getByText('Choose the company.').waitFor();
    await dlg.getByLabel('Company').selectOption({ index: 1 });
    await dlg.getByLabel('Job role').fill(NEW_ROLE);
    await dlg.getByLabel('Drive date').fill('2026-03-15');
    await dlg.getByLabel('Package (LPA)').fill('9.5');
    await dlg.getByLabel('Minimum CGPA').fill('6.5');
    await dlg.getByLabel('Maximum backlogs').fill('2');
    await shot('08-admin-new-drive-form', { fullPage: false });
    await dlg.getByRole('button', { name: 'Create drive' }).click();
    await page.waitForURL(/\/admin\/drives\/\d+$/);
    await page.getByRole('heading', { name: NEW_ROLE }).waitFor();
    newDriveUrl = page.url();
  });

  await step('Edit drive updates the package', async () => {
    await page.getByRole('button', { name: 'Edit drive' }).click();
    const dlg = page.getByRole('dialog');
    await dlg.getByLabel('Package (LPA)').fill('10.25');
    await dlg.getByRole('button', { name: 'Save changes' }).click();
    await page.getByText('Drive updated.').waitFor();
    await page.getByText(/₹10\.25 LPA/).first().waitFor();
  });

  await step('Close drive runs the procedure and reports rejections', async () => {
    await page.getByRole('button', { name: 'Close drive' }).click();
    const dlg = page.getByRole('dialog');
    await dlg.getByText(/will be marked/).waitFor();
    await shot('09-admin-close-drive-confirm', { fullPage: false });
    await dlg.getByRole('button', { name: 'Close drive' }).click();
    await page.getByText(/Drive closed\. 0 pending applicants were rejected/).waitFor();
    // The page reloads the drive after closing it; wait for the button to turn disabled.
    await page.locator('button:has-text("Close drive"):disabled').waitFor({ timeout: 10000 });
  });

  await step('Drive detail lists applicants; shortlist the student', async () => {
    await page.goto(`${BASE}/admin/drives/${DRIVE_ID}`, { waitUntil: 'networkidle' });
    await page.getByPlaceholder('Search name or reg. no.').fill(STUDENT.reg);
    const row = page.locator('table tbody tr', { hasText: STUDENT.name });
    await row.waitFor();
    await row.getByLabel(`Move ${STUDENT.name} to`).selectOption('Shortlisted');
    await page.getByText(`${STUDENT.name}: Applied → Shortlisted.`).waitFor();
  });

  await step('Record an interview round', async () => {
    const row = page.locator('table tbody tr', { hasText: STUDENT.name });
    await row.getByRole('button', { name: 'Round' }).click();
    const dlg = page.getByRole('dialog');
    await dlg.getByLabel('Round type').selectOption('Technical');
    await dlg.getByLabel('Result').selectOption('Pass');
    await dlg.getByRole('button', { name: 'Save round' }).click();
    await page.getByText(`Round recorded for ${STUDENT.name}.`).waitFor();
  });

  await step('Select the student, then record an offer', async () => {
    const row = page.locator('table tbody tr', { hasText: STUDENT.name });
    await row.getByLabel(`Move ${STUDENT.name} to`).selectOption('Selected');
    await page.getByText(`${STUDENT.name}: Shortlisted → Selected.`).waitFor();
    await row.getByRole('button', { name: 'Offer' }).click();
    const dlg = page.getByRole('dialog');
    await shot('10-admin-record-offer', { fullPage: false });
    await dlg.getByRole('button', { name: 'Record offer' }).click();
    await page.getByText(new RegExp(`Offer recorded for ${STUDENT.name}`)).waitFor();
    await row.getByText('Offer Made').waitFor();
    await page.getByPlaceholder('Search name or reg. no.').fill('');
    await shot('11-admin-drive-detail');
  });

  await step('View application: offer detail + status history', async () => {
    await page.getByPlaceholder('Search name or reg. no.').fill(STUDENT.reg);
    const row = page.locator('table tbody tr', { hasText: STUDENT.name });
    await row.getByRole('button', { name: /View/ }).click();
    const dlg = page.getByRole('dialog');
    await dlg.getByText('Package offered').waitFor();
    const history = await dlg.locator('.timeline li').count();
    check('...status history entries', history >= 3, `${history} entries`);
    await shot('12-admin-application-detail', { fullPage: false });
    await page.keyboard.press('Escape');
  });

  await step('Students page: filters and profile with CGPA percentile', async () => {
    await page.getByRole('link', { name: 'Students' }).click();
    await page.getByRole('heading', { name: 'Students' }).waitFor();
    await page.locator('table tbody tr').first().waitFor();
    await page.getByLabel('Placement status').selectOption('Placed');
    await page.waitForTimeout(800);
    await shot('13-admin-students');
    await page.locator('table tbody tr').first().click();
    await page.getByRole('dialog').getByText('CGPA percentile').waitFor();
    await shot('14-admin-student-profile', { fullPage: false });
    await page.keyboard.press('Escape');
  });

  await step('Analytics overview: bars + CGPA scatter with tooltip', async () => {
    await page.getByRole('link', { name: 'Analytics' }).click();
    await page.getByRole('heading', { name: 'Placement analytics' }).waitFor();
    await page.locator('.bar-row').first().waitFor();
    const svg = page.locator('svg[aria-label^="Scatter plot"]');
    await svg.waitFor();
    const dot = svg.locator('circle').nth(40);
    const box = await dot.boundingBox();
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await page.locator('.chart-tooltip').waitFor({ timeout: 3000 });
    await shot('15-admin-analytics-overview');
  });

  for (const [tab, name, check_] of [
    ['Recruiters & packages', '16-admin-analytics-recruiters', 'Top recruiters'],
    ['Top offers', '17-admin-analytics-rankings', 'Top offers in each department'],
    ['Timeline', '18-admin-analytics-timeline', 'Offers per month'],
    ['Company × department', '19-admin-analytics-matrix', 'Offers by company and department'],
  ]) {
    await step(`Analytics tab: ${tab}`, async () => {
      await page.getByRole('tab', { name: tab }).click();
      await page.getByRole('heading', { name: check_ }).waitFor();
      if (tab === 'Timeline') {
        await page.locator('rect.hit').first().hover();
        await page.locator('.chart-tooltip').waitFor({ timeout: 3000 });
      }
      if (tab === 'Company × department') {
        await page.locator('table.heatmap tbody tr').first().waitFor();
        await page.getByRole('button', { name: 'Rebuild snapshot' }).click();
        await page.getByText(/Snapshot rebuilt at/).waitFor();
      }
      await shot(name);
    });
  }

  // ------------------------------------------------------------- student accepts
  await step('Student sees the offer and accepts it', async () => {
    await page.getByRole('button', { name: 'Logout' }).click();
    await page.waitForURL('**/login');
    await page.locator('#login-email').fill(STUDENT.email);
    await page.locator('#login-password').fill('Student@123');
    await page.getByRole('button', { name: 'Sign in' }).click();
    await page.waitForURL('**/student**');
    await page.getByRole('tab', { name: /My Applications/ }).click();
    const row = page.locator('table tbody tr', { hasText: COMPANY }).first();
    await row.getByRole('button', { name: 'View offer' }).click();
    const dlg = page.getByRole('dialog');
    await dlg.getByRole('button', { name: 'Accept offer' }).click();
    await dlg.getByText('Offer accepted. Congratulations!').waitFor();
    await dlg.getByText('Accepted', { exact: true }).first().waitFor();
    await shot('20-student-offer-accepted', { fullPage: false });
    await page.keyboard.press('Escape');
  });

  // ------------------------------------------------------------- responsive
  await step('Phone width: sidebar becomes a drawer', async () => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.getByRole('tab', { name: 'Overview' }).click();
    const toggle = page.getByRole('button', { name: 'Open navigation' });
    await toggle.waitFor();
    await shot('21-mobile-student', { fullPage: false });
    await toggle.click();
    await page.locator('.app-shell.nav-open').waitFor();
    await page.waitForTimeout(500); // let the 0.2s slide-in finish before the screenshot
    await shot('22-mobile-nav-open', { fullPage: false });
  });

  check('No console or page errors', consoleErrors.length === 0, consoleErrors.join(' || ').slice(0, 600));
  console.log(results.join('\n'));
  console.log(`\nTOTAL: ${results.filter((r) => r.startsWith('PASS')).length}/${results.length} passed`);
  await browser.close();
})();
