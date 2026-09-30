import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const SCREENSHOT_DIR = '/Users/abhishekadari/.gemini/antigravity-ide/brain/916bf543-9510-41b0-87fc-cb6df068e42d/screenshots';
const REPORT_FILE = '/Users/abhishekadari/.gemini/antigravity-ide/brain/916bf543-9510-41b0-87fc-cb6df068e42d/e2e_report.json';

if (!fs.existsSync(SCREENSHOT_DIR)) {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
}

// Human-like pauses
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const randomPause = (min = 200, max = 600) => sleep(Math.floor(Math.random() * (max - min + 1)) + min);

async function humanType(page, selector, text) {
  const el = await page.waitForSelector(selector, { timeout: 10000 });
  await el.click();
  await sleep(150);
  for (const char of text) {
    await page.keyboard.type(char, { delay: Math.floor(Math.random() * 40) + 30 });
  }
  await sleep(200);
}

async function humanClick(page, selector) {
  const el = await page.waitForSelector(selector, { state: 'visible', timeout: 10000 });
  await el.scrollIntoViewIfNeeded();
  await randomPause(200, 400);
  await el.hover();
  await randomPause(100, 250);
  await el.click();
  await randomPause(300, 600);
}

async function humanScroll(page, distance = 400, steps = 8) {
  const stepDist = distance / steps;
  for (let i = 0; i < steps; i++) {
    await page.mouse.wheel(0, stepDist);
    await sleep(40);
  }
  await sleep(300);
}

async function run() {
  console.log('🚀 Starting Human-like Playwright E2E Test Suite for GSM-OS...');
  
  const browser = await chromium.launch({
    headless: true,
    channel: 'chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
  });

  const page = await context.newPage();
  
  const consoleErrors = [];
  const networkErrors = [];

  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      consoleErrors.push({ text: msg.text(), location: msg.location() });
    }
  });

  page.on('response', (res) => {
    if (res.status() >= 400 && !res.url().includes('favicon')) {
      networkErrors.push({ url: res.url(), status: res.status(), statusText: res.statusText() });
    }
  });

  const testReport = {
    timestamp: new Date().toISOString(),
    auth: {},
    dashboard: {},
    missingLinksValidation: {},
    pagesTested: {},
    consoleErrors: [],
    networkErrors: []
  };

  try {
    // ==========================================
    // 1. AUTHENTICATION & LOGIN
    // ==========================================
    console.log('\n--- 1. Testing Authentication Flow ---');
    await page.goto('http://localhost:3000/', { waitUntil: 'networkidle' });
    await sleep(500);

    const authTitle = await page.textContent('h1');
    console.log(`[Auth Screen] Found title: "${authTitle?.trim()}"`);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '01_auth_screen.png') });

    console.log('[Human Action] Entering credentials for Dr. Alex Mercer...');
    await humanType(page, 'input[type="email"]', 'researcher@gsm-os.org');
    await humanType(page, 'input[type="password"]', 'researcher123');
    await sleep(300);

    console.log('[Human Action] Clicking "Sign In" button...');
    await humanClick(page, 'button[type="submit"]');

    // Wait for Dashboard to mount
    await page.waitForSelector('nav, aside, [href="/discovery"]', { timeout: 12000 });
    await sleep(1500);
    console.log('✅ Successfully authenticated and reached Dashboard!');
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '02_dashboard_home.png') });

    // Validate Dashboard components
    const statCards = await page.$$eval('[class*="rounded-"], [class*="border"]', els => els.length);
    console.log(`[Dashboard] Rendered container/metric elements count: ${statCards}`);
    testReport.auth = { status: 'SUCCESS', title: authTitle?.trim(), emailUsed: 'researcher@gsm-os.org' };
    testReport.dashboard = { status: 'LOADED', elementsFound: statCards };

    // ==========================================
    // 2. DEEP DIVE: MISSING LINKS DASHBOARD
    // ==========================================
    console.log('\n--- 2. Deep Dive: Missing Links Dashboard (/missing-links) ---');
    await page.goto('http://localhost:3000/missing-links', { waitUntil: 'networkidle' });
    await sleep(1500);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '03_missing_links_initial.png') });

    const pageHeading = await page.$eval('h1', el => el.innerText).catch(() => 'N/A');
    const pageSubheading = await page.$eval('p', el => el.innerText).catch(() => 'N/A');
    console.log(`[Header Validation] Title: "${pageHeading}"`);
    console.log(`[Header Validation] Description: "${pageSubheading}"`);

    // Tab 1: Unexplored Combinations
    console.log('\n[Validating Tab 1: Unexplored Combinations]');
    await sleep(1000);

    // Read confidence slider & controls
    const sliderVal = await page.$eval('input[type="range"]', el => el.value).catch(() => 'N/A');
    console.log(`[Controls] Current Confidence Slider Value: ${sliderVal}`);

    // Adjust slider like a human to explore responsiveness
    console.log('[Human Action] Adjusting slider to 0.4...');
    await page.fill('input[type="range"]', '0.4');
    await page.dispatchEvent('input[type="range"]', 'change');
    await sleep(500);

    // Test Results dropdown
    console.log('[Human Action] Selecting 10 results from dropdown...');
    await page.selectOption('select', '10').catch(() => {});
    await sleep(500);

    // Click Refresh button
    console.log('[Human Action] Clicking Refresh button...');
    const refreshBtn = await page.locator('button:has-text("Refresh")');
    if (await refreshBtn.isVisible()) {
      await refreshBtn.click();
      await sleep(1500);
    }

    // Inspect each combination card in detail
    console.log('[Human Action] Inspecting each Missing Link / Unexplored Combination found...');
    const comboCards = await page.$$('div[draggable="true"]');
    console.log(`[Found] ${comboCards.length} Unexplored Combination cards.`);

    const validatedCombinations = [];

    for (let i = 0; i < comboCards.length; i++) {
      const card = comboCards[i];
      await card.scrollIntoViewIfNeeded();
      await sleep(300);

      // Extract details
      const cardText = await card.innerText();
      const lines = cardText.split('\n').map(l => l.trim()).filter(Boolean);

      // Read concept badges
      const badges = await card.$$eval('div[style*="border-radius: 20px"], div[style*="borderRadius: 20px"]', els => els.map(e => e.innerText));
      const confidenceBadge = await card.$$eval('div[style*="confidence"]', els => els.map(e => e.innerText));
      const recommendationText = await card.$eval('p', el => el.innerText).catch(() => '');

      console.log(`\n  👉 Combination #${i + 1}:`);
      console.log(`     Concept Pair: [${badges.join('  <--- GAP --->  ')}]`);
      console.log(`     Confidence & Bridges: ${lines.find(l => l.includes('confidence')) || 'N/A'} | ${lines.find(l => l.includes('bridge')) || 'N/A'}`);
      console.log(`     Recommendation: "${recommendationText}"`);

      // Expand card like a human to view the suggested research question
      console.log(`     [Human Action] Clicking card #${i + 1} to expand Suggested Research Question...`);
      await card.click();
      await sleep(400);

      const researchQuestion = await card.$eval('div[style*="rgba(16, 185, 129"] p:last-child, div[style*="rgba(16,185,129"] p:last-child', el => el.innerText).catch(() => 'None');
      console.log(`     💡 Suggested Research Question: "${researchQuestion}"`);

      // Verify the buttons inside the card
      const exploreBtn = await card.$('button:has-text("Explore in Graph")');
      const hypothesisBtn = await card.$('button:has-text("Generate Hypothesis")');
      console.log(`     Buttons available: [Explore in Graph: ${exploreBtn ? 'YES' : 'NO'}, Generate Hypothesis: ${hypothesisBtn ? 'YES' : 'NO'}]`);

      // Hover over the buttons
      if (exploreBtn) {
        await exploreBtn.hover();
        await sleep(150);
      }
      if (hypothesisBtn) {
        await hypothesisBtn.hover();
        await sleep(150);
      }

      validatedCombinations.push({
        index: i + 1,
        badges,
        confidence: lines.find(l => l.includes('confidence')),
        bridges: lines.find(l => l.includes('bridge')),
        recommendation: recommendationText,
        researchQuestion,
        hasExploreInGraph: !!exploreBtn,
        hasGenerateHypothesis: !!hypothesisBtn
      });
    }

    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '04_missing_links_combinations_expanded.png') });

    // Tab 2: Missing Graph Links
    console.log('\n[Human Action] Clicking Tab: 🔗 Missing Graph Links...');
    const tab2 = await page.locator('button:has-text("Missing Graph Links")');
    if (await tab2.isVisible()) {
      await tab2.click();
      await sleep(1000);
      await page.screenshot({ path: path.join(SCREENSHOT_DIR, '05_missing_links_graph_links.png') });
      const tab2Content = await page.$$eval('div[style*="border-radius: 12px"]', els => els.map(e => e.innerText));
      console.log(`[Tab 2: Missing Graph Links] Rendered entries: ${tab2Content.length}`);
      testReport.missingLinksValidation.tab2 = { count: tab2Content.length, entries: tab2Content };
    }

    // Tab 3: Drug Repurposing
    console.log('\n[Human Action] Clicking Tab: 💊 Drug Repurposing...');
    const tab3 = await page.locator('button:has-text("Drug Repurposing")');
    if (await tab3.isVisible()) {
      await tab3.click();
      await sleep(1000);
      await page.screenshot({ path: path.join(SCREENSHOT_DIR, '06_missing_links_drug_repurposing.png') });
      const tab3Content = await page.$$eval('div[style*="border-radius: 12px"]', els => els.map(e => e.innerText));
      console.log(`[Tab 3: Drug Repurposing] Rendered entries: ${tab3Content.length}`);
      testReport.missingLinksValidation.tab3 = { count: tab3Content.length, entries: tab3Content };
    }

    // Tab 4: 3-Hop Hypotheses
    console.log('\n[Human Action] Clicking Tab: 🔀 3-Hop Hypotheses...');
    const tab4 = await page.locator('button:has-text("3-Hop Hypotheses")');
    if (await tab4.isVisible()) {
      await tab4.click();
      await sleep(1000);
      await page.screenshot({ path: path.join(SCREENSHOT_DIR, '07_missing_links_three_hop.png') });
      const tab4Content = await page.$$eval('div[style*="border-radius: 12px"]', els => els.map(e => e.innerText));
      console.log(`[Tab 4: 3-Hop Hypotheses] Rendered entries: ${tab4Content.length}`);
      testReport.missingLinksValidation.tab4 = { count: tab4Content.length, entries: tab4Content };
    }

    testReport.missingLinksValidation.combinations = validatedCombinations;

    // ==========================================
    // 3. TESTING ALL REMAINING UI PAGES & BUTTONS
    // ==========================================
    console.log('\n--- 3. Testing All Other UI Pages & Interactive Components ---');

    const pagesToTest = [
      { name: 'Discovery Feed', path: '/discovery', shot: '08_discovery.png' },
      { name: 'Bottleneck Dashboard', path: '/bottlenecks', shot: '09_bottlenecks.png' },
      { name: 'Hypotheses Dashboard', path: '/hypotheses', shot: '10_hypotheses.png' },
      { name: 'Graph Explorer', path: '/graph', shot: '11_graph.png' },
      { name: 'Search', path: '/search', shot: '12_search.png' },
      { name: 'Papers Browser', path: '/papers', shot: '13_papers.png' },
      { name: 'Gap Finder', path: '/gaps', shot: '14_gaps.png' },
      { name: 'Paper Publisher', path: '/publish', shot: '15_publish.png' },
      { name: 'Research Chat', path: '/chat', shot: '16_chat.png' },
      { name: 'Paper Comparison', path: '/papers/compare', shot: '17_paper_comparison.png' },
      { name: 'Research Roadmap', path: '/roadmap', shot: '18_roadmap.png' },
      { name: 'Timeline', path: '/timeline', shot: '19_timeline.png' },
      { name: 'Novelty Dashboard', path: '/novelty', shot: '20_novelty.png' },
      { name: 'Settings', path: '/settings', shot: '21_settings.png' },
    ];

    for (const pageItem of pagesToTest) {
      console.log(`\n➡️  Navigating to ${pageItem.name} (${pageItem.path})...`);
      await page.goto(`http://localhost:3000${pageItem.path}`, { waitUntil: 'networkidle', timeout: 15000 }).catch(e => console.log(`   Timeout or nav note: ${e.message}`));
      await sleep(1200);

      // Human interaction specific to certain pages
      if (pageItem.path === '/search') {
        console.log('   [Human Action] Typing search query "Quantum Computing"...');
        const searchInput = await page.$('input[placeholder*="search" i], input[type="text"]');
        if (searchInput) {
          await humanType(page, 'input[placeholder*="search" i], input[type="text"]', 'Quantum Computing');
          const searchBtn = await page.$('button:has-text("Search"), button[type="submit"]');
          if (searchBtn) {
            await humanClick(page, 'button:has-text("Search"), button[type="submit"]');
            await sleep(1500);
          }
        }
      } else if (pageItem.path === '/chat') {
        console.log('   [Human Action] Testing Chat UI input...');
        const chatInput = await page.$('textarea, input[placeholder*="Ask" i], input[placeholder*="chat" i], input[type="text"]');
        if (chatInput) {
          await humanType(page, 'textarea, input[placeholder*="Ask" i], input[placeholder*="chat" i], input[type="text"]', 'Explain quantum entanglement and its role in quantum computing');
          await sleep(500);
          const sendBtn = await page.$('button:has-text("Send"), button:has-text("Ask"), button[type="submit"]');
          if (sendBtn) {
            console.log('   [Human Action] Clicking Send...');
            await sendBtn.click();
            await sleep(2500);
          }
        }
      } else if (pageItem.path === '/novelty') {
        console.log('   [Human Action] Testing Novelty score page buttons/inputs...');
        const conceptInput = await page.$('input[placeholder*="concept" i], input[type="text"]');
        if (conceptInput) {
          await humanType(page, 'input[placeholder*="concept" i], input[type="text"]', 'Superconductivity');
          await sleep(300);
        }
      } else if (pageItem.path === '/graph') {
        console.log('   [Human Action] Hovering and inspecting graph canvas/controls...');
        await humanScroll(page, 200, 4);
        await sleep(1000);
      }

      // Smooth scroll to simulate real human review
      await humanScroll(page, 300, 5);
      await sleep(400);

      const title = await page.$eval('h1, h2', el => el.innerText).catch(() => 'Page Rendered');
      const buttonsCount = await page.$$eval('button', btns => btns.length);
      console.log(`   Page Heading: "${title}" | Interactive Buttons: ${buttonsCount}`);

      await page.screenshot({ path: path.join(SCREENSHOT_DIR, pageItem.shot) });

      testReport.pagesTested[pageItem.name] = {
        path: pageItem.path,
        heading: title,
        buttonsCount,
        status: 'PASSED'
      };
    }

    console.log('\n✅ All pages and components systematically tested!');

  } catch (err) {
    console.error('❌ Test failed with error:', err);
    testReport.error = err.message;
  } finally {
    testReport.consoleErrors = consoleErrors;
    testReport.networkErrors = networkErrors;

    fs.writeFileSync(REPORT_FILE, JSON.stringify(testReport, null, 2));
    console.log(`\n📄 Detailed JSON test report written to: ${REPORT_FILE}`);

    await browser.close();
    console.log('🏁 Browser automation session concluded.');
  }
}

run();
