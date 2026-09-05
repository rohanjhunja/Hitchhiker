const { chromium } = require('playwright');

(async () => {
  console.log('Launching browser to test /gallery/ ...');
  const browser = await chromium.launch({
    headless: true,
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
  });
  const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  const page = await context.newPage();

  const errors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') {
      console.error('[Browser Error]', msg.text());
      errors.push(msg.text());
    } else {
      console.log('[Browser Log]', msg.text());
    }
  });

  page.on('pageerror', err => {
    console.error('[Page Error]', err);
    errors.push(err.message);
  });

  console.log('Navigating to http://localhost:8000/gallery/ ...');
  await page.goto('http://localhost:8000/gallery/', { waitUntil: 'networkidle' });

  // 1. Check title and active book
  const title = await page.title();
  console.log('Page Title:', title);

  const activeTitle = await page.textContent('#active-book-title-short');
  console.log('Active Book:', activeTitle);

  // 2. Check SVG rects
  await page.waitForSelector('#poster-container svg rect');
  const rectCount = await page.locator('#poster-container svg rect').count();
  console.log('Rendered poster rect count:', rectCount);

  // 3. Test Interactive Mode Quote Hover
  console.log('Testing block hover in Interactive mode...');
  const firstRect = page.locator('#poster-container svg rect').first();
  await firstRect.hover();
  await page.waitForTimeout(300);

  const quoteCardOpacity = await page.locator('#quote-card').evaluate(el => getComputedStyle(el).opacity);
  const quoteText = await page.textContent('#quote-text');
  const quoteColor = await page.textContent('#quote-color-name');
  console.log(`Quote Card Opacity: ${quoteCardOpacity} | Color: ${quoteColor} | Excerpt: "${quoteText.slice(0, 60)}..."`);

  // 4. Test Bookmarking
  console.log('Testing quote bookmarking...');
  await page.click('#quote-bookmark-btn');
  const starText = await page.textContent('#bookmark-star-icon');
  console.log('Bookmark Star Icon after click:', starText);

  // 5. Test Room Switcher
  console.log('Testing gallery room switching...');
  await page.click('button[data-room="2"]');
  const room2Active = await page.locator('button[data-room="2"]').evaluate(el => el.classList.contains('active'));
  console.log('Room 2 active:', room2Active);

  // 6. Test Replay Mode
  console.log('Testing Replay Mode...');
  await page.click('#btn-mode-replay');
  await page.waitForTimeout(1000);
  const isReplaying = await page.evaluate(() => document.body.classList.contains('mode-replay'));
  const timelineTicks = await page.locator('#timeline-track .timeline-tick').count();
  const timeText = await page.textContent('#timeline-time');
  console.log(`Replay mode active: ${isReplaying} | Timeline Ticks: ${timelineTicks} | Time: ${timeText}`);

  // 7. Test Navigation to Next Poster
  console.log('Testing poster navigation (Next Poster)...');
  await page.click('#btn-next-poster');
  await page.waitForTimeout(800);
  const nextTitle = await page.textContent('#active-book-title-short');
  const nextRectCount = await page.locator('#poster-container svg rect').count();
  console.log(`Navigated to: ${nextTitle} | Rect Count: ${nextRectCount}`);

  // 8. Test Index Drawer
  console.log('Testing Collection Index Drawer...');
  await page.click('#open-index-btn');
  await page.waitForTimeout(500);
  const drawerOpen = await page.locator('#index-drawer').evaluate(el => el.classList.contains('open'));
  const bookCardsCount = await page.locator('.index-book-card').count();
  console.log(`Index Drawer Open: ${drawerOpen} | Total Books in Index: ${bookCardsCount}`);

  // Close Index
  await page.click('#close-index-btn');
  await page.waitForTimeout(300);

  // 9. Take Desktop and Mobile Screenshots
  console.log('Capturing screenshots for visual review...');
  await page.screenshot({ path: 'gallery/test_desktop.png' });

  // Test Mobile Viewport (iPhone 14 / 390x844)
  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForTimeout(500);
  await page.screenshot({ path: 'gallery/test_mobile.png' });

  await browser.close();

  if (errors.length > 0) {
    console.error('FAILED with browser errors:', errors);
    process.exit(1);
  } else {
    console.log('ALL TESTS PASSED SUCCESSFULLY!');
  }
})();
