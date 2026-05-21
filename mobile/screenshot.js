const puppeteer = require('puppeteer-core');
const path = require('path');
const fs = require('fs');

const OUT = path.join(__dirname, 'screenshots');
if (!fs.existsSync(OUT)) fs.mkdirSync(OUT);

const MOBILE = { width: 390, height: 844, deviceScaleFactor: 2 };

async function shot(page, name) {
  await page.screenshot({ path: path.join(OUT, `${name}.png`), fullPage: false });
  console.log(`captured: ${name}.png`);
}

async function wait(ms) {
  return new Promise(r => setTimeout(r, ms));
}

async function fillInput(page, placeholder, value) {
  const sel = `input[placeholder="${placeholder}"]`;
  await page.waitForSelector(sel, { timeout: 5000 });
  // page.focus() skips clickability checks — works for RN Web TextInputs
  await page.focus(sel);
  await wait(200);
  // Select all + delete, then type
  await page.keyboard.down('Control');
  await page.keyboard.press('KeyA');
  await page.keyboard.up('Control');
  await page.keyboard.press('Backspace');
  await page.keyboard.type(value, { delay: 30 });
  await wait(150);
}

// Resolve Chrome/Chromium path:
//   1. CHROME_PATH env var wins on every platform
//   2. otherwise fall back to a common per-OS default
function resolveChromePath() {
  if (process.env.CHROME_PATH) return process.env.CHROME_PATH;
  switch (process.platform) {
    case 'win32':
      return 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
    case 'darwin':
      return '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
    default:
      return '/usr/bin/google-chrome';
  }
}

(async () => {
  const browser = await puppeteer.launch({
    headless: 'new',
    executablePath: resolveChromePath(),
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  });
  const page = await browser.newPage();
  await page.setViewport(MOBILE);

  // ── 1. Onboarding ─────────────────────────────────────────────────────────
  await page.goto('http://localhost:8081', { waitUntil: 'networkidle2', timeout: 30000 });
  await wait(2000);
  await shot(page, '01_onboarding');

  // Next slide
  await page.click('text=Next').catch(() => {});
  await wait(800);
  await shot(page, '02_onboarding_slide2');

  // Third slide / Get Started
  await page.click('text=Next').catch(() => {});
  await wait(800);
  await shot(page, '03_onboarding_slide3');

  await page.click('text=Get Started').catch(() => {});
  await wait(1200);
  await shot(page, '04_login');

  // ── 2. Register ───────────────────────────────────────────────────────────
  await page.click('text=Create one').catch(() => {});
  await wait(1000);
  await shot(page, '05_register');

  // Fill form — Tab between fields to avoid duplicate selector issue
  // (Login screen is still mounted in the nav stack, also has "you@example.com")
  const ts = Date.now();
  await page.focus('input[placeholder="Your name"]');
  await wait(150);
  await page.keyboard.type('Aman Agrawal', { delay: 30 });
  await wait(150);

  await page.keyboard.press('Tab');   // → email
  await wait(150);
  await page.keyboard.type(`aman${ts}@sleepsense.app`, { delay: 30 });
  await wait(150);

  await page.keyboard.press('Tab');   // → password
  await wait(150);
  await page.keyboard.type('Test1234!', { delay: 30 });
  await wait(150);

  await page.keyboard.press('Tab');   // → eye-icon button (skip it)
  await wait(100);
  await page.keyboard.press('Tab');   // → confirm password
  await wait(150);
  await page.keyboard.type('Test1234!', { delay: 30 });
  await wait(400);
  await shot(page, '06_register_filled');

  // Tab past confirm's eye-icon, then to the Create Account button, press Enter
  await page.keyboard.press('Tab');   // → eye-icon on confirm (skip)
  await page.keyboard.press('Tab');   // → Create Account button
  await wait(200);
  await page.keyboard.press('Enter');
  await wait(5000);  // wait for API + navigation
  await shot(page, '07_home');

  // ── 3. Main tabs ──────────────────────────────────────────────────────────
  // Use coordinates for tab bar (390px wide / 5 tabs = 78px each, tab bar y≈812)
  // Tab centres (x): Home=39, Record=117, Log=195, History=273, Profile=351
  const TAB_Y = 812;
  const tapTab = async (x) => { await page.mouse.click(x, TAB_Y); };

  await tapTab(273);   // History
  await wait(1800);
  await shot(page, '08_history');

  await tapTab(195);   // Log
  await wait(1200);
  await shot(page, '09_lifestyle_log');

  await tapTab(117);   // Record
  await wait(1000);
  await shot(page, '10_record');

  await tapTab(351);   // Profile
  await wait(1000);
  await shot(page, '11_profile');

  // ── 4. Session detail ─────────────────────────────────────────────────────
  await tapTab(273);   // History
  await wait(1800);
  const rows = await page.$$('[style*="border-radius: 14px"]');
  if (rows.length > 0) {
    await rows[0].click();
    await wait(1800);
    await shot(page, '12_session_detail');
  }

  await browser.close();
  console.log('\nAll screenshots saved to ./screenshots/');
})().catch(e => { console.error(e); process.exit(1); });
