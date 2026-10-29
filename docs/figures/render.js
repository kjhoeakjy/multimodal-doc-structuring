const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const svg = fs.readFileSync(process.argv[2], 'utf8');
  const m = svg.match(/<svg[^>]*\swidth="(\d+)"[^>]*\sheight="(\d+)"/);
  const W = m ? +m[1] : 1600, H = m ? +m[2] : 1000;
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 2 });
  await p.setContent(`<html><body style="margin:0">${svg}</body></html>`);
  await p.waitForTimeout(300);
  await p.screenshot({ path: process.argv[3], clip: { x: 0, y: 0, width: W, height: H } });
  await b.close();
})();
