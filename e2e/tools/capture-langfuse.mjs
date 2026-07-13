/**
 * Log into the self-hosted Langfuse and screenshot a triage_contract trace's
 * span tree, so the tester how-to guide can show what the observability looks
 * like. Run with: node tools/capture-langfuse.mjs  (from the e2e/ folder)
 */
import { chromium } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SHOTS = path.join(__dirname, "..", "artifacts", "screenshots");
fs.mkdirSync(SHOTS, { recursive: true });

const LF = "http://localhost:3001";
const EMAIL = "admin@northgate.local";
const PASSWORD = "langfuse-admin";
const PUBLIC_KEY = "pk-lf-contract-triage";
const SECRET_KEY = "sk-lf-contract-triage";

// Grab the most recent triage_contract trace id from the public API.
async function latestTraceId() {
  const res = await fetch(`${LF}/api/public/traces?limit=1&name=triage_contract`, {
    headers: { Authorization: "Basic " + Buffer.from(`${PUBLIC_KEY}:${SECRET_KEY}`).toString("base64") },
  });
  const body = await res.json();
  return body.data?.[0]?.id;
}

const traceId = await latestTraceId();
console.log("latest triage_contract trace:", traceId);

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

// ── Sign in ────────────────────────────────────────────────────────────────
await page.goto(`${LF}/auth/sign-in`, { waitUntil: "networkidle" });
await page.getByLabel(/email/i).fill(EMAIL);
await page.getByLabel(/password/i).fill(PASSWORD);
await page.getByRole("button", { name: /sign in/i }).click();
await page.waitForLoadState("networkidle");
await page.waitForTimeout(1500);

// ── Traces list ──────────────────────────────────────────────────────────────
await page.goto(`${LF}/project/contract-triage/traces`, { waitUntil: "networkidle" });
await page.waitForTimeout(2000);
await page.screenshot({ path: path.join(SHOTS, "07-langfuse-traces.png"), fullPage: false });
console.log("wrote 07-langfuse-traces.png");

// ── One trace's span tree ─────────────────────────────────────────────────────
if (traceId) {
  await page.goto(`${LF}/project/contract-triage/traces/${traceId}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2500);
  await page.screenshot({ path: path.join(SHOTS, "08-langfuse-trace-detail.png"), fullPage: false });
  console.log("wrote 08-langfuse-trace-detail.png");
}

await browser.close();
