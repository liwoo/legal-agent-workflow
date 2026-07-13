const fs = require('fs');
const path = require('path');
const raw = JSON.parse(fs.readFileSync(path.join(__dirname, 'raw-audit.json')));

function mergeCounts(key) {
  const m = {};
  for (const p of raw) {
    if (!p[key]) continue;
    for (const [k, v] of Object.entries(p[key])) m[k] = (m[k] || 0) + v;
  }
  return Object.entries(m).sort((a, b) => b[1] - a[1]);
}
const top = (key, n = 25) => mergeCounts(key).slice(0, n);

const out = {};
out.pagesCrawled = raw.map(p => ({ name: p._name, title: p.title, error: p.error || null }));
out.body = raw.find(p => p.body)?.body;
out.cssVars = raw.reduce((acc, p) => ({ ...acc, ...(p.cssVars || {}) }), {});
out.fonts = top('fonts', 15);
out.fontSizes = top('fontSizes', 30);
out.fontWeights = top('fontWeights');
out.lineHeights = top('lineHeights', 20);
out.letterSpacings = top('letterSpacings', 15);
out.textColors = top('textColors', 30);
out.bgColors = top('bgColors', 30);
out.borderColors = top('borderColors', 20);
out.borderRadii = top('borderRadii', 15);
out.boxShadows = top('boxShadows', 15);
out.gradients = top('gradients', 15);
out.spacing = top('spacing', 30);
out.transitions = top('transitions', 12);
out.zIndexes = top('zIndexes', 15);
out.containerWidths = top('containerWidths', 15);

// breakpoints union
const bp = new Set();
raw.forEach(p => (p.breakpoints || []).forEach(x => bp.add(x)));
out.breakpoints = [...bp];

// headings — take home page then burp
out.headings = {};
const hpages = ['home', 'burp', 'academy'];
hpages.forEach(nm => { const pg = raw.find(p => p._name === nm); if (pg) out.headings[nm] = pg.headings; });

// buttons — dedupe by bg+color+radius signature
const btnSig = new Map();
raw.forEach(p => (p.buttons || []).forEach(b => {
  const sig = `${b.bg}|${b.gradient}|${b.color}|${b.radius}|${b.border}`;
  if (!btnSig.has(sig)) btnSig.set(sig, b);
}));
out.buttonStyles = [...btnSig.values()];

// links dedupe
const linkSig = new Map();
raw.forEach(p => (p.links || []).forEach(l => {
  const sig = `${l.color}|${l.decoration}|${l.weight}`;
  linkSig.set(sig, (linkSig.get(sig) || 0) + 1);
}));
out.linkStyles = [...linkSig.entries()].sort((a,b)=>b[1]-a[1]);

fs.writeFileSync(path.join(__dirname, 'summary.json'), JSON.stringify(out, null, 2));
console.log(JSON.stringify(out, null, 2));
