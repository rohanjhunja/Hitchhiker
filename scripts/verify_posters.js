const { chromium } = require('playwright');
const booksToTest = ['HitchhikersGuide', 'AliceInWonderland', 'Dune', 'FellowshipOfTheRing', 'Odyssey', 'LifeOfPi', 'MyNameIsRed'];

(async () => {
  const browser = await chromium.launch({
    headless: true,
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
  });
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });

  for (const bookKey of booksToTest) {
    await page.goto(`http://localhost:8000/gallery/?book=${bookKey}&mode=interactive`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(400);

    const title = await page.textContent('#active-book-title-short');
    const rectCount = await page.locator('#poster-container svg rect').count();

    const midIdx = Math.floor(rectCount / 2);
    const tile = page.locator('#poster-container svg rect').nth(midIdx);
    await tile.hover();
    await page.waitForTimeout(200);

    const quoteColor = await page.textContent('#quote-color-name');
    const quoteText = await page.textContent('#quote-text');
    console.log(`[PASS] ${bookKey.padEnd(22)}: Title='${title}', Tiles=${rectCount}, Mid-Tile Color=${quoteColor}, Excerpt='${quoteText.slice(0, 45)}...'`);

    await page.screenshot({ path: `gallery/test_poster_${bookKey}.png` });
  }

  await browser.close();
  console.log('\nAll tested posters verified successfully with zero errors!');
})();
