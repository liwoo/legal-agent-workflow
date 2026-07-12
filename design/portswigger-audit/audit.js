const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const PAGES = [
  { name: 'home',        url: 'https://portswigger.net/' },
  { name: 'burp',        url: 'https://portswigger.net/burp' },
  { name: 'burp-pro',    url: 'https://portswigger.net/burp/pro' },
  { name: 'enterprise',  url: 'https://portswigger.net/burp/enterprise' },
  { name: 'academy',     url: 'https://portswigger.net/web-security' },
  { name: 'research',    url: 'https://portswigger.net/research' },
  { name: 'solutions',   url: 'https://portswigger.net/solutions' },
  { name: 'pricing',     url: 'https://portswigger.net/burp/pro#pricing' },
  { name: 'about',       url: 'https://portswigger.net/about' },
  { name: 'support',     url: 'https://portswigger.net/support' },
];

const OUT = __dirname;
const SHOTS = path.join(OUT, 'screenshots');

// Extraction executed in the page context
function extractInPage() {
  const data = {
    url: location.href,
    title: document.title,
    cssVars: {},
    fonts: {},          // fontFamily -> count
    fontSizes: {},      // px -> count
    fontWeights: {},    // weight -> count
    lineHeights: {},
    letterSpacings: {},
    textColors: {},     // color -> count
    bgColors: {},       // bg color -> count
    borderColors: {},
    borderRadii: {},
    boxShadows: {},
    spacing: {},        // margin/padding px buckets -> count
    headings: {},       // h1..h6 -> {size, weight, family, color, lineHeight}
    buttons: [],        // sampled button styles
    links: [],          // sampled link styles
    breakpoints: [],    // from stylesheet media queries
    gradients: {},
    transitions: {},
    zIndexes: {},
    containerWidths: {},
  };

  const bump = (obj, key) => { if (key == null || key === '') return; obj[key] = (obj[key] || 0) + 1; };

  // 1) CSS custom properties from :root
  const rootStyle = getComputedStyle(document.documentElement);
  for (let i = 0; i < rootStyle.length; i++) {
    const prop = rootStyle[i];
    if (prop.startsWith('--')) data.cssVars[prop] = rootStyle.getPropertyValue(prop).trim();
  }

  // 2) media query breakpoints from stylesheets
  const bps = new Set();
  for (const sheet of document.styleSheets) {
    let rules;
    try { rules = sheet.cssRules; } catch (e) { continue; }
    if (!rules) continue;
    for (const rule of rules) {
      if (rule.media && rule.conditionText) {
        const m = rule.conditionText.match(/(\d+(?:\.\d+)?)(px|em|rem)/g);
        if (m) m.forEach(x => bps.add(x));
      }
    }
  }
  data.breakpoints = [...bps];

  // 3) walk elements (cap to keep it fast)
  const els = document.querySelectorAll('body *');
  const MAX = 6000;
  let n = 0;
  for (const el of els) {
    if (n++ > MAX) break;
    const cs = getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    const visible = rect.width > 0 && rect.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none';

    bump(data.fonts, cs.fontFamily);
    bump(data.fontSizes, cs.fontSize);
    bump(data.fontWeights, cs.fontWeight);
    bump(data.lineHeights, cs.lineHeight);
    if (cs.letterSpacing !== 'normal') bump(data.letterSpacings, cs.letterSpacing);

    // colors — only count where text actually present
    if (el.textContent && el.textContent.trim().length > 0) bump(data.textColors, cs.color);
    if (cs.backgroundColor && cs.backgroundColor !== 'rgba(0, 0, 0, 0)') bump(data.bgColors, cs.backgroundColor);
    if (cs.backgroundImage && cs.backgroundImage.includes('gradient')) bump(data.gradients, cs.backgroundImage);
    if (cs.borderTopWidth !== '0px' || cs.borderBottomWidth !== '0px') bump(data.borderColors, cs.borderTopColor);
    if (cs.borderTopLeftRadius !== '0px') bump(data.borderRadii, cs.borderTopLeftRadius);
    if (cs.boxShadow && cs.boxShadow !== 'none') bump(data.boxShadows, cs.boxShadow);
    if (cs.transition && cs.transition !== 'all 0s ease 0s') bump(data.transitions, cs.transition);
    if (cs.zIndex !== 'auto') bump(data.zIndexes, cs.zIndex);

    ['marginTop','marginBottom','paddingTop','paddingBottom','paddingLeft','paddingRight','gap'].forEach(p => {
      const v = cs[p];
      if (v && v !== '0px' && v !== 'normal') bump(data.spacing, v);
    });

    // container widths for max-width containers
    if (visible && cs.maxWidth !== 'none') bump(data.containerWidths, cs.maxWidth);

    // buttons
    const tag = el.tagName.toLowerCase();
    const cls = (el.className && el.className.toString) ? el.className.toString() : '';
    const looksButton = tag === 'button' || (tag === 'a' && /btn|button|cta/i.test(cls)) || el.getAttribute('role') === 'button';
    if (looksButton && visible && data.buttons.length < 40) {
      data.buttons.push({
        text: (el.textContent || '').trim().slice(0, 40),
        tag, cls: cls.slice(0, 80),
        color: cs.color, bg: cs.backgroundColor, gradient: cs.backgroundImage.includes('gradient') ? cs.backgroundImage : '',
        border: `${cs.borderTopWidth} ${cs.borderTopStyle} ${cs.borderTopColor}`,
        radius: cs.borderTopLeftRadius, padding: `${cs.paddingTop} ${cs.paddingRight} ${cs.paddingBottom} ${cs.paddingLeft}`,
        fontSize: cs.fontSize, fontWeight: cs.fontWeight, textTransform: cs.textTransform,
        letterSpacing: cs.letterSpacing, boxShadow: cs.boxShadow,
      });
    }

    if (tag === 'a' && visible && data.links.length < 20 && el.textContent.trim()) {
      data.links.push({ color: cs.color, decoration: cs.textDecorationLine, weight: cs.fontWeight });
    }
  }

  // 4) headings representative styles
  ['h1','h2','h3','h4','h5','h6'].forEach(h => {
    const el = document.querySelector(h);
    if (el) {
      const cs = getComputedStyle(el);
      data.headings[h] = {
        fontSize: cs.fontSize, fontWeight: cs.fontWeight, fontFamily: cs.fontFamily,
        color: cs.color, lineHeight: cs.lineHeight, letterSpacing: cs.letterSpacing,
        textTransform: cs.textTransform, marginBottom: cs.marginBottom,
      };
    }
  });

  // body base
  const b = getComputedStyle(document.body);
  data.body = { fontFamily: b.fontFamily, fontSize: b.fontSize, lineHeight: b.lineHeight, color: b.color, bg: b.backgroundColor };

  return data;
}

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  const results = [];

  for (const p of PAGES) {
    try {
      console.log('visiting', p.url);
      await page.goto(p.url, { waitUntil: 'networkidle', timeout: 45000 });
      await page.waitForTimeout(1200);
      // dismiss cookie banner if present
      try {
        const btn = await page.$('button:has-text("Accept"), button:has-text("accept all"), #onetrust-accept-btn-handler');
        if (btn) { await btn.click({ timeout: 3000 }); await page.waitForTimeout(500); }
      } catch (e) {}
      const data = await page.evaluate(extractInPage);
      data._name = p.name;
      results.push(data);
      // screenshot: above-the-fold + full page
      await page.screenshot({ path: path.join(SHOTS, `${p.name}-fold.png`) });
      await page.screenshot({ path: path.join(SHOTS, `${p.name}-full.png`), fullPage: true });
    } catch (e) {
      console.log('ERROR on', p.url, e.message);
      results.push({ _name: p.name, url: p.url, error: e.message });
    }
  }

  fs.writeFileSync(path.join(OUT, 'raw-audit.json'), JSON.stringify(results, null, 2));
  console.log('wrote raw-audit.json with', results.length, 'pages');
  await browser.close();
})();
