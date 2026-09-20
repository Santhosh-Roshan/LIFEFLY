
const puppeteer = require('puppeteer');
(async () => {
  const browser = await puppeteer.launch();
  const page = await browser.newPage();
  await page.setContent('<script src="https://unpkg.com/three@0.161.0/build/three.min.js"></script><script>console.log(typeof THREE);</script>');
  page.on('console', msg => console.log('LOG:', msg.text()));
  await page.close();
  await browser.close();
})();
