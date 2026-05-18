const fs = require("fs");
const path = require("path");

const puppeteerModule =
  process.env.PUPPETEER_CORE_PATH ||
  "/Users/chenjintao/.npm/_npx/73bcf459b506fa77/node_modules/puppeteer-core";
const puppeteer = require(puppeteerModule);

const fps = Number(process.env.FPS || "24");
const duration = Number(process.env.DURATION || "15");
const totalFrames = fps * duration;
const width = 1080;
const height = 1920;
const rootDir = __dirname;
const outputDir = path.join(rootDir, "dist", "frames");
const chromePath =
  process.env.CHROME_PATH ||
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const htmlUrl = `file://${path.join(rootDir, "index.html")}`;

fs.rmSync(outputDir, { recursive: true, force: true });
fs.mkdirSync(outputDir, { recursive: true });

async function main() {
  const browser = await puppeteer.launch({
    headless: true,
    executablePath: chromePath,
    defaultViewport: {
      width,
      height,
      deviceScaleFactor: 1,
    },
    args: [
      "--allow-file-access-from-files",
      "--disable-web-security",
      "--no-first-run",
      "--no-default-browser-check",
    ],
  });

  try {
    const page = await browser.newPage();
    await page.goto(htmlUrl, { waitUntil: "load" });
    await page.waitForFunction(() => window.__timelines && window.__timelines["bear-run"]);
    await page.evaluate(() => {
      const tl = window.__timelines["bear-run"];
      tl.pause(0);
      tl.time(0, false);
    });

    for (let frame = 0; frame < totalFrames; frame += 1) {
      const time = frame / fps;
      await page.evaluate((t) => {
        const tl = window.__timelines["bear-run"];
        tl.pause();
        tl.time(t, false);
      }, time);
      await page.evaluate(
        () =>
          new Promise((resolve) => {
            requestAnimationFrame(() => resolve(true));
          }),
      );
      const filename = `frame-${String(frame).padStart(4, "0")}.png`;
      await page.screenshot({
        path: path.join(outputDir, filename),
        type: "png",
      });
      if (frame % fps === 0) {
        console.log(`captured ${frame}/${totalFrames}`);
      }
    }
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
