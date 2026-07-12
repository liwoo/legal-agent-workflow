# PortSwigger — Design Language / Design System Audit

> Reverse-engineered from live computed styles + screenshots across 10 pages
> (home, burp, burp/pro, enterprise/DAST, web-security academy, research, solutions,
> pricing, about, support) via Playwright + Chromium @ 1440×900, 2026-07-12.
>
> **Terminology:** the artifact below is a *design audit* producing a *design system*
> (a.k.a. *Design Language System / DLS*) — documented *design tokens* (color, type,
> spacing, elevation) plus the *component* and *layout* conventions built on them.

---

## 0. Executive summary — the "brand feeling"

**Bold, high-contrast, engineer-credible.** Deep navy + energetic orange + lots of
white, with big, tightly-tracked bold Arial headlines. The site sells to security
professionals, so it "dogfoods" — real Burp Suite product screenshots are the primary
hero imagery rather than abstract illustration. Sections alternate rhythmically between
white, deep-navy, and pale blue-grey tint bands.

**Design-maturity note:** there are **no runtime CSS custom properties** on `:root`
(tokens are compiled from SCSS/utility classes, not exposed as `--vars`). At least
**three CSS lineages coexist**, which tells you the system has evolved in place:
1. **Legacy Academy** — square buttons (`.btn --color-orange`, radius 0, weight 700).
2. **Legacy marketing** — pill buttons `button-orange-small` / `button-outline-blue-small` (radius 40px, UPPERCASE).
3. **Modern utility system** — `button-primary`, `text-body-3`, `gap-xs`, `padding-vertical-xs`, fully-round (radius 100px) pills.

---

## 1. Color palette

### Core brand
| Token | Hex | RGB | Role |
|---|---|---|---|
| **Brand Orange** | `#FF6633` / `#FF6733` | 255,102,51 | Primary CTA, active nav, links-on-navy, logo mark. *(two near-identical values in use)* |
| **Deep Navy** | `#001350` | 0,19,80 | Hero/section backgrounds, H2/H3 headings |
| **Navy (darker)** | `#060738` | 6,7,56 | Alt dark surface / footer |
| **Ink** | `#333332` | 51,51,50 | Body text, H1 on light |
| **Slate-grey text** | `#5C5C5B` | 92,92,91 | Secondary / muted body copy |
| **White** | `#FFFFFF` | 255,255,255 | Base background, text on navy |

### Secondary accents (sub-brand / product-specific)
| Token | Hex | Role |
|---|---|---|
| **Purple** | `#6D61FF` (also `#5B4FFF`) | Enterprise/DAST "automation & scale" accent, alt primary buttons |
| **Sky blue** | `#00ACED` / `#00ACEE` | Social / "Follow us", secondary outline buttons |
| **Bright blue** | `#0094FF` / `#0594FF` | Links, DAST diagrams |
| **Teal** | `#00A2B9` | Occasional accent chips |

### Neutrals & tint surfaces (background bands)
| Hex | Role |
|---|---|
| `#FBFBFB` | Off-white sub-nav bar & subtle section fill |
| `#EBF0F2` | Pale blue-grey section band |
| `#F0F8FB` / `#F2FAFB` | Palest blue tint (hero wash) |
| `#EAEAEA`, `#CBD0D1` | Border / divider greys |
| `#4C5054` | Dark neutral surface |
| `#FFF7F5`, `#FFD9CC` | Faint orange tints (highlight chips) |

### Semantic / severity (from product UI screenshots)
Red = High · Orange = Medium · Blue = Low · Grey = Info — the classic Burp
vuln-severity ramp, echoed in marketing donut/bar charts.

---

## 2. Typography

**Family:** `Arial` is the workhorse everywhere (with `Arial, Helvetica, sans-serif`
and `Arial, Courier, sans-serif` fallback stacks). `"Droid Sans"` appears in a few
legacy spots. A custom **`ps-icons`** icon font supplies UI glyphs. No web-font
loading for body text — deliberately fast, system-native.

**Weights:** `400` regular and `700` bold do ~99% of the work; `500` is rare (Academy H1).

**Base:** 16px body · line-height 18.4px (≈1.15) · color `#333332`.

### Type scale (px, most-used first)
`13 · 14 · 16 · 18 · 22 · 24 · 32 · 40 · 60` (plus fluid/responsive interpolated
sizes like 33.2, 47.8, 68.8 on large hero breakpoints).

### Heading specs (signature: **tight negative letter-spacing**)
| Element | Size / line-height | Weight | Letter-spacing | Color |
|---|---|---|---|---|
| H1 (marketing) | 60 / 70 | 700 | **−2.4px** (≈−0.04em) | `#333332` on light · white on navy |
| H2 | 40 / 50 | 700 | **−1.6px** | `#001350` |
| H3 | 22 / 32 | 700 | −0.88px | `#001350` |
| Body | 16 / ~24 | 400 | normal | `#333332` |
| Small / caption | 13–14 | 400 | normal | `#5C5C5B` |

The tight tracking on large bold Arial is the single most recognisable type signature.
**Academy is the exception** — H1 at 28px weight **500**, *normal* tracking (a softer,
more "editorial/learning" voice that visibly departs from the marketing pages).

**Links:** default un-underlined (`text-decoration: none`), same color as body
(`#333332`) or slate — underline/orange reserved for hover & active states.

---

## 3. Spacing & layout

**Two rhythms coexist:** a dominant **5px-based** legacy scale and a newer **8px-based**
tokenised scale (named `gap-xs`, `padding-vertical-xs`, etc.).

Observed spacing values (frequency-ranked):
`5 · 10 · 15 · 20 · 30 · 40 · 60` (5-rhythm) and `8 · 16 · 24 · 32` (8-rhythm).

**Containers:** centered, max-width **1140px / 1200px** (both in use). Generous
vertical whitespace; content is comfortably narrow relative to full-bleed color bands.

**Grid:** implied 12-column; marketing sections lean on **3-up card grids**
(e.g. "What do you want to do?", Academy value props, Research featured cards).

**Section pattern:** full-bleed colored band (navy or tint) → centered container →
heading → 3-column content. Bands alternate to segment the page.

---

## 4. Elevation (box-shadow scale)

| Level | Value | Use |
|---|---|---|
| **sm** | `rgba(0,0,0,.16) 0 0 6px` | Subtle chips / inputs |
| **md** | `rgba(0,0,0,.16) 0 4px 6px` | Default card (most common) |
| **lg (soft)** | `rgba(0,0,0,.086) 0 30px 30px` | Large floating cards / product mockups |
| **xl (layered)** | `rgba(50,50,93,.25) 0 13px 27px -5px, rgba(0,0,0,.3) 0 8px 16px -8px, …` | Hero "floating screenshot" depth (Stripe-style triple shadow) |
| **glow** | `rgba(0,0,35,.2) 0 0 20px` | Navy-on-navy card separation |

---

## 5. Radius

| Token | Value | Use |
|---|---|---|
| Pill (modern) | **100px** | Primary/secondary buttons (fully round) |
| Pill (legacy) | **40px** | Older marketing buttons |
| Card | **6px** | Cards, panels, images |
| Small | **4px** | Inputs, small chips |
| Medium | 12px | Occasional larger cards |
| Square | **0px** | Legacy Academy `.btn` buttons |

---

## 6. Buttons (component inventory)

The clearest evidence of the multi-generation system. Common metrics: **14px text,
padding ~10px 20px**, most variants full-round.

| Variant | Fill | Text | Border | Radius | Notes |
|---|---|---|---|---|---|
| **Primary (orange)** | `#FF6733` bg | white | 2px `#FF6733` | 100px | Main CTA ("Find out more", "Request a demo") |
| **Primary (purple)** | `#6D61FF` bg | white | 2px `#6D61FF` | 100px | DAST/Enterprise CTA |
| **Outline-white** | transparent | white | 2px white | 100px | On navy heroes ("Buy – $499", "Pricing") |
| **Quaternary / ghost** | transparent | `#FF6733` | none | 0 | Inline text-CTA with icon gap |
| **Legacy orange-small** | `#FF6633` | white **UPPERCASE** | — | 40px | "MY ACCOUNT", "SEARCH" |
| **Legacy outline-blue-small** | transparent | `#00ACEE` | 2px `#00ACEE` | 40px | "Follow us" |
| **Academy square** | `#FF6633` or white | weight **700** | 1px | **0px** | "Sign up" / "Login" — distinct lineage |

Micro-interaction: buttons/links transition `all .3s ease`, `color .15s ease`,
`box-shadow/background .2s ease`.

---

## 7. Cards & surfaces

- White card, radius **6px**, shadow **md** (`0 4px 6px rgba(0,0,0,.16)`), sitting on
  navy or tint bands — the core content unit.
- 3-up equal-width card rows; each card = centered heading (bold, `#001350`) →
  illustration/screenshot → body copy (`#5C5C5B`) → orange CTA → fine-print qualifier.
- Product-screenshot cards float with the **xl layered shadow** and often break the
  container edge (bleeding off-canvas) to imply depth/scale.

---

## 8. Navigation & chrome

- **Top bar:** white, tall, left = PortSwigger wordmark, right = orange pill
  **MY ACCOUNT / LOGIN**. A **2–3px orange rule** underlines the whole header — a
  signature divider.
- **Primary nav:** `Products ▾ | Solutions ▾ | Research | Academy | Support ▾` with
  chevron dropdowns and thin pipe separators; a hamburger sits at the far right even on
  desktop (progressive disclosure of the full menu).
- **Section sub-nav:** a second `#FBFBFB` bar appears on product/section pages
  (e.g. Burp Pro: Overview · Features · Workflow · Burp AI · … · Buy · Get certified),
  with the **active item in orange**.
- **Footer:** dark, with outlined social pill buttons (Twitter blue, etc.).

---

## 9. Iconography & graphic motifs

- **Logo mark:** orange rounded square containing a white **lightning bolt ("flash")**
  — repeated across sub-brand lockups (Burp Suite, Web Security Academy, PortSwigger
  Research), each pairing the wordmark with the bolt.
- **Icons:** custom `ps-icons` font; on Academy, thin **line-style orange** icons
  (target, maze, book) for value props.
- **Decorative textures:** dot-grid matrices and faint **hexagon** patterns as
  background texture behind heroes; diagonal hazard stripes on some Research cards.
- **Illustration style:** flat, geometric, brand-colored spot illustrations for
  concepts, but **real UI screenshots** for the products themselves.

---

## 10. Motion

Understated, functional. Standard easing (`ease` / `ease-in-out`), durations
**0.15s–0.4s**. Most common: `all .3s ease` (399×), `color .15s ease` (293×),
`opacity .3s ease`, `transform .4s ease`. Reveal combos animate
`opacity + transform + height` together for accordion/expand.

---

## 11. Responsive

Breakpoints are **numerous and ad-hoc** (dozens of one-off px values from
310→1536px), which — like the button lineages — signals component-level responsive
tuning rather than a strict shared token set. The meaningful design tiers cluster at:
**~768px (tablet)**, **~991/992px (desktop)**, **~1200px (large)**, with `1140/1200px`
as the content ceiling.

---

## 12. If you were to codify it as tokens

```jsonc
{
  "color": {
    "brand.orange":   "#FF6633",
    "brand.navy":     "#001350",
    "brand.navy.deep":"#060738",
    "text.ink":       "#333332",
    "text.muted":     "#5C5C5B",
    "accent.purple":  "#6D61FF",
    "accent.sky":     "#00ACEE",
    "accent.blue":    "#0094FF",
    "surface.white":  "#FFFFFF",
    "surface.tint":   "#EBF0F2",
    "surface.tint.blue":"#F2FAFB",
    "border.subtle":  "#EAEAEA"
  },
  "font": { "family.base": "Arial, Helvetica, sans-serif",
            "weight.regular": 400, "weight.bold": 700 },
  "fontSize": { "xs":13,"sm":14,"base":16,"md":18,"lg":22,"xl":24,
                "2xl":32,"3xl":40,"display":60 },
  "letterSpacing": { "display":"-2.4px","h2":"-1.6px","h3":"-0.88px","base":"normal" },
  "space":  { "5-rhythm":[5,10,15,20,30,40,60], "8-rhythm":[8,16,24,32] },
  "radius": { "sm":4,"card":6,"md":12,"pill":100,"pill.legacy":40,"square":0 },
  "shadow": {
    "sm":"0 0 6px rgba(0,0,0,.16)",
    "md":"0 4px 6px rgba(0,0,0,.16)",
    "lg":"0 30px 30px rgba(0,0,0,.086)",
    "xl":"0 13px 27px -5px rgba(50,50,93,.25), 0 8px 16px -8px rgba(0,0,0,.3)"
  },
  "container": { "max": "1200px", "narrow": "1140px" },
  "motion": { "fast":"150ms","base":"300ms","slow":"400ms","ease":"ease" }
}
```

---

### Artifacts produced
- `raw-audit.json` — full per-page computed-style harvest
- `summary.json` — aggregated, frequency-ranked tokens
- `screenshots/*-fold.png` and `*-full.png` — 10 pages, above-fold + full-page
- `audit.js`, `summarize.js` — reproducible crawl + aggregation scripts
