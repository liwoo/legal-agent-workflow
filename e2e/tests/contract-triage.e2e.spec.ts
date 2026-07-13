import { test, expect, type Page } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";

/**
 * End-to-end walkthrough of the Contract Triage console.
 *
 * Mirrors the exact journey a reviewer takes:
 *   1. Open the console — queues are already warm (10 seeded contracts).
 *   2. Click "New Contract" and fill the intake form.
 *   3. Attach the sample intake PDF.
 *   4. Submit — the "Triaging…" loading state shows while the agent runs.
 *   5. The agent classifies → gates → dispositions the contract.
 *   6. The page hydrates: the new contract appears in the queue it was
 *      triaged to, and its detail view shows the outcome + journey.
 *
 * Each stage writes a screenshot to e2e/artifacts/screenshots so the run is
 * auditable and can be embedded in the tester how-to guide.
 *
 * Prereq: the stack (frontend :3000, API :8000, Langfuse :3001) is already up.
 */

const SHOTS = path.join(__dirname, "..", "artifacts", "screenshots");
fs.mkdirSync(SHOTS, { recursive: true });

// A unique counterparty per run so we can find our row unambiguously.
const RUN_TAG = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
const COUNTERPARTY = `Meridian Freight Solutions Ltd [E2E ${RUN_TAG}]`;
const SAMPLE_PDF = path.join(__dirname, "..", "fixtures", "sample-contract.pdf");

// Same mapping the frontend uses (src/lib/utils.ts + state-badge.tsx).
const SIGNED = ["signed_no_edits", "signed_desk_edits", "signed_with_deviation"];
const REVIEW = ["escalated", "blocked", "declined", "business_decision"];
const END_STATE_LABEL: Record<string, string> = {
  signed_no_edits: "Signed — no edits",
  signed_desk_edits: "Signed — desk edits",
  signed_with_deviation: "Signed — deviation",
  escalated: "Escalated",
  blocked: "Blocked",
  more_info_needed: "More info needed",
  business_decision: "Business decision",
  declined: "Declined",
};
function queueFor(endState: string | null): "signed" | "review" | "inbox" {
  if (endState && SIGNED.includes(endState)) return "signed";
  if (endState && REVIEW.includes(endState)) return "review";
  return "inbox";
}

const shot = (page: Page, name: string) =>
  page.screenshot({ path: path.join(SHOTS, name), fullPage: true });

test("create a contract, triage it, and see where it lands", async ({ page }) => {
  // ── Stage 1 — open the console; queues are warm ──────────────────────────
  await test.step("open the review console", async () => {
    await page.goto("/contracts/inbox");
    await expect(page.getByRole("heading", { name: "Inbox" })).toBeVisible();
    // Queue tabs render counts once the API responds.
    await expect(page.getByRole("button", { name: "New Contract" })).toBeVisible();
    await shot(page, "01-console-loaded.png");
  });

  // ── Stage 2 — open the New Contract modal and fill the intake form ───────
  await test.step("fill the New Contract form", async () => {
    await page.getByRole("button", { name: "New Contract" }).click();
    const dialog = page.getByRole("dialog");
    await expect(dialog.getByText("New contract", { exact: true })).toBeVisible();

    await dialog.locator("#counterparty").fill(COUNTERPARTY);
    await dialog.locator("#received_from").fill("AE (sales)");
    await dialog
      .locator("#summary")
      .fill("Counterparty's own mutual NDA paper (5 pages, PDF), unsigned. Prospective logistics customer ahead of a platform demo.");
    await dialog.locator("#senders_ask").fill("Can we sign their NDA as-is so we can book the demo next week?");
    await dialog.locator("#sector").fill("logistics");

    // ── Stage 3 — attach the intake PDF ───────────────────────────────────
    await dialog.locator("#file").setInputFiles(SAMPLE_PDF);
    await shot(page, "02-form-filled.png");
  });

  // ── Stage 4 — submit; capture the loading state; capture the result ──────
  // Arm the response listener BEFORE clicking so we never miss it.
  const createResponse = page.waitForResponse(
    (r) => r.url().includes("/api/contracts") && r.request().method() === "POST",
    { timeout: 150_000 }
  );

  await test.step("submit and observe the Triaging… loading state", async () => {
    await page.getByRole("button", { name: /Create & triage/i }).click();
    // The submit button flips to a spinner + "Triaging…" while the agent runs.
    await expect(page.getByRole("button", { name: /Triaging/i })).toBeVisible();
    await shot(page, "03-triaging-loading.png");
  });

  // ── Stage 5 — the agent finishes; read the disposition off the response ──
  const response = await createResponse;
  expect(response.ok(), `POST /api/contracts failed: ${response.status()}`).toBeTruthy();
  const created = await response.json();
  const contractId: string = created.id;
  const endState: string | null = created.end_state ?? null;
  const landedQueue = queueFor(endState);
  const disposition = endState ? END_STATE_LABEL[endState] ?? endState : "(pending)";
  console.log(`\n➡  Triaged ${contractId} → end_state=${endState} → queue=${landedQueue} (${disposition})\n`);

  // The dialog closes on success.
  await expect(page.getByRole("dialog")).toBeHidden();

  // ── Stage 6 — the page hydrates: find the contract in the queue it landed in
  await test.step("find the triaged contract in its queue", async () => {
    await page.goto(`/contracts/${landedQueue}`);
    const row = page.getByRole("row", { name: new RegExp(contractId) });
    await expect(row).toBeVisible();
    // The row shows the disposition badge (unless it stayed in the inbox).
    if (endState) {
      await expect(row.getByText(disposition, { exact: false })).toBeVisible();
    }
    await shot(page, "04-queue-hydrated.png");

    // ── Open the detail view — the full triage outcome + journey ──────────
    await row.click();
    const modal = page.getByRole("dialog");
    await expect(modal.getByText(COUNTERPARTY)).toBeVisible();
    await page.waitForTimeout(500); // let the modal open-animation settle
    await shot(page, "05-detail-summary.png");

    // The Decision tab spells out the outcome badge explicitly.
    await modal.getByRole("tab", { name: "Decision" }).click();
    await expect(modal.getByText("Outcome")).toBeVisible();
    await page.waitForTimeout(300); // let the tab switch settle
    if (endState) {
      await expect(modal.getByText(disposition, { exact: false }).first()).toBeVisible();
    }
    await shot(page, "06-detail-decision.png");
  });

  // Record the outcome for the report / how-to guide.
  fs.writeFileSync(
    path.join(SHOTS, "..", "outcome.json"),
    JSON.stringify({ contractId, counterparty: COUNTERPARTY, endState, landedQueue, disposition }, null, 2)
  );
});
