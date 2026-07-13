# PortSwigger Design-Language Audit

A reverse-engineered **design system** (design tokens + component/layout conventions)
for [portswigger.net](https://portswigger.net/), captured from live computed styles and
screenshots across 10 pages via Playwright + Chromium (2026-07-12).

## Contents
| File | What it is |
|---|---|
| `DESIGN-LANGUAGE.md` | The write-up: color, type, spacing, elevation, buttons, nav, motion, responsive + a `tokens.json` codification |
| `summary.json` | Aggregated, frequency-ranked tokens across all pages |
| `screenshots/*-fold.png` | Above-the-fold capture of each audited page |
| `audit.js` | Playwright crawl — harvests computed styles + screenshots |
| `summarize.js` | Aggregates the raw harvest into `summary.json` |

Pages audited: home, burp, burp/pro, enterprise (DAST), web-security academy,
research, solutions, pricing, about, support.

## Reproduce
```bash
npm init -y
npm install playwright@1.43.1     # 1.43 supports Node 16; use latest on Node 18+
npx playwright install chromium
node audit.js        # writes raw-audit.json + screenshots/
node summarize.js    # writes summary.json
```

> Note: the original run also produced `raw-audit.json` (full per-page dump) and
> full-page screenshots; both were left out of version control to keep the repo light.
> Re-run the scripts to regenerate them.
