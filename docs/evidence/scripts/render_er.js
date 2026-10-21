// Renders the ```mermaid block of docs/er-diagram.md to a PNG.
// usage: node render_er.js <er-diagram.md> <out.png>
// Needs playwright and mermaid@11.4.1 installed next to it (npm install playwright mermaid@11.4.1);
// CHROMIUM_PATH may point at a local Chromium. Output: 2x PNG of the diagram.
const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

(async () => {
  const [mdPath, outPath] = process.argv.slice(2);
  const md = fs.readFileSync(mdPath, "utf8").split("\r\n").join("\n");
  const src = md.match(/```mermaid\n([\s\S]*?)```/)[1];
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH });
  const page = await browser.newPage({ viewport: { width: 2400, height: 1600 }, deviceScaleFactor: 2 });
  await page.setContent(`<!doctype html><html><body style="margin:0;background:#fff">
    <div id="out"></div></body></html>`);
  await page.addScriptTag({ path: path.join(__dirname, "node_modules/mermaid/dist/mermaid.min.js") });
  const size = await page.evaluate(async (code) => {
    mermaid.initialize({ startOnLoad: false, theme: "neutral", er: { useMaxWidth: false, fontSize: 20 },
                         themeVariables: { fontFamily: "Arial, sans-serif", fontSize: "20px" } });
    const { svg } = await mermaid.render("er", code);
    document.getElementById("out").innerHTML = svg;
    const el = document.querySelector("#out svg");
    const b = el.getBoundingClientRect();
    return { w: Math.round(b.width), h: Math.round(b.height) };
  }, src);
  const el = await page.$("#out svg");
  await el.screenshot({ path: outPath });
  console.log(`rendered ${outPath}  css size ${size.w}x${size.h}px (PNG at 2x)`);
  await browser.close();
})();
