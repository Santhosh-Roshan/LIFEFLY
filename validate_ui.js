
const puppeteer = require('puppeteer');
(async () => {
  const browser = await puppeteer.launch();
  const page = await browser.newPage();
  page.on('console', msg => console.log('PAGE LOG:', msg.text()));
  page.on('pageerror', err => console.log('PAGE ERROR:', err.toString()));
  await page.goto('file:///' + __dirname.replace(/\\\\/g, '/') + '/index.html', {waitUntil: 'networkidle2'});
  await browser.close();
})();
