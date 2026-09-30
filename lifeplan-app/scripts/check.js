// 表示確認用スクリプト:スマホ幅(390px)で開き、結果画面の各タブをスクリーンショットに撮る。
// 使い方: node scripts/check.js [dist/index.html] [出力フォルダ]
// ・CDN に届かない環境では、node_modules の react / react-dom / htm を差し込んで表示する
// ・横スクロールが出ていないか(scrollWidth)とページのエラーを表示する
const path = require("path");
const fs = require("fs");
const { chromium } = require("playwright");

const file = path.resolve(process.argv[2] || path.join(__dirname, "..", "dist", "index.html"));
const out = path.resolve(process.argv[3] || path.join(__dirname, "..", "screenshots"));
fs.mkdirSync(out, { recursive: true });

// package.json の exports でサブパスが読めないことがあるので、node_modules を直接探す
function localLib(pkg, rel) {
  const dirs = [...module.paths, ...(process.env.NODE_PATH || "").split(path.delimiter).filter(Boolean)];
  for (const dir of dirs) {
    const f = path.join(dir, pkg, rel);
    if (fs.existsSync(f)) return f;
  }
  return null;
}
const LIBS = {
  "**/react.production.min.js": localLib("react", "umd/react.production.min.js"),
  "**/react-dom.production.min.js": localLib("react-dom", "umd/react-dom.production.min.js"),
  "**/htm.umd.js": localLib("htm", "dist/htm.umd.js"),
};

(async () => {
  const browser = await chromium.launch(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {});
  for (const colorScheme of ["light", "dark"]) {
    const page = await browser.newPage({ viewport: { width: 390, height: 860 }, colorScheme });
    for (const [pattern, local] of Object.entries(LIBS)) if (local) await page.route(pattern, (r) => r.fulfill({ path: local }));
    page.on("pageerror", (e) => console.log(`[${colorScheme}] pageerror:`, e.message));
    await page.goto("file://" + file);
    await page.waitForTimeout(800);
    await page.screenshot({ path: path.join(out, `${colorScheme}-intro.png`), fullPage: true });
    await page.click('button:has-text("入力例の結果を見る")');
    await page.waitForTimeout(800);
    for (const tab of ["ライフプラン", "ライフイベント", "もしも比較", "キャッシュフロー表"]) {
      await page.click(`button[role=tab]:has-text("${tab}")`);
      await page.waitForTimeout(300);
      await page.screenshot({ path: path.join(out, `${colorScheme}-result-${tab}.png`), fullPage: true });
    }
    const sw = await page.evaluate(() => document.documentElement.scrollWidth);
    console.log(`[${colorScheme}] scrollWidth=${sw} (390 なら横スクロールなし)`);
    await page.close();
  }
  await browser.close();
  console.log("スクリーンショット:", out);
})();
