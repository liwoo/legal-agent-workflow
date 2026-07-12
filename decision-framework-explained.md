# The Contract Robot, Explained Like You're 10 🤖📄

This file explains `decision-framework.mmd`. That diagram is basically a set of
**"choose your own adventure"** rules for a company (Northgate Systems Ltd) that
receives lots of contracts and has to decide what to do with each one.

Think of it like a **big flowchart game**: a contract comes in the door, and it
walks through a maze of questions. At each question you go one way or another,
until the contract reaches a finish line.

---

## The colors (the "legend")

Every box has a color that tells you what *kind* of box it is:

| Color | Shape | What it means |
|-------|-------|----------------|
| 🔵 Blue | box | **Intake** — a new thing arriving and getting sorted |
| 🟡 Yellow | diamond | **Decision** — a yes/no question |
| 🟣 Purple | box | **Policy gate** — a rule-check you must pass (the "grown-up rules") |
| ⚪ Gray | box | **Action** — someone does some work |
| 🟢 Green | flag | **Done** — the contract is signed! 🎉 |
| 🔴 Red | flag | **Escalation** — "Uh oh, call the bosses!" |
| 🟠 Orange | flag | **Waiting** — stop and wait for something before you can go on |

The whole game is about getting a contract safely to a **green flag** (signed),
while catching any problems and sending them to a **red** or **orange** flag.

---

## The steps, one at a time

### 1. A contract shows up 🔵
An **Inbox item** arrives. First we **classify** it — that just means we write
down some basic facts: what family it belongs to, whose paper it's on, which
direction it's going, whether it has personal data, if we've seen it before, and
how much money it's worth.

> Like sorting your mail: "This is a birthday card, from Grandma, worth a hug."

### 2. Is there actually a contract to read? 🟡
**"Draft attached?"**
- **No** → 🟠 *MORE INFO NEEDED*. You can't review something you don't have.
  Stop and ask for it.
- **Yes** → keep going.

### 3. Have we seen this one before? 🟡
**"Prior file?"**
- **Yes** → ⚪ Pull up the old file and its notes ("inherited flags").
  - Then: **"Blocking flag?"** Is there an old problem that must be fixed first?
    - **Yes** → 🟠 *BLOCKED*. Fix that first before doing anything else.
    - **No** → keep going.
- **No** → keep going.

### 4. The fast path (the easy contracts) 🟡
**"Our template, no redlines?"** ("Redlines" = the other side crossed things out
and rewrote them. No redlines = nobody messed with our version.)
- **Yes** → 🟢 *SIGN-READY*. It's our own clean form, so auto-approve and just
  do a quick spot-check. Easy!
- **It's a SOW or amendment** (an add-on to an existing deal) → ask
  **"Within framework or stated scope?"**
  - **Yes** → 🟢 *SIGN-READY* too.
  - **No** → go to the policy gates.
- **It's redlined or their paper** → go to the policy gates (needs more care).

### 5. The policy gates (the grown-up safety rules) 🟣
These are checks you **must** pass. Three gates in a row:

- **Gate 1 — "Personal data?"** Does it handle people's private info?
  - If yes, check the data-protection terms, breach-notice window, and how data
    moves across borders. Then ask: **"High-risk data, no DPIA?"** (A DPIA is a
    safety report for risky data.)
    - **Yes** (risky and no report) → 🟠 *BLOCKED*. Can't continue.
    - **No** → next gate.

- **Gate 2 — "Their paper?"** Is it written on the other company's form?
  - If yes, run the **statutory checklist** — legal must-haves like anti-bribery,
    anti-slavery, tax, third-party, and unfair-terms (UCTA) rules.

- **Gate 3 — "Ask beyond insured cover?"** Are they asking us to promise more
  than our insurance covers?
  - If yes → get **Finance sign-off** before continuing.

### 6. The big fork: can we even negotiate? 🟡
**"Non-negotiable paper?"** Some companies say "take it or leave it."
- **Yes (can't change it)** → ⚪ do a **gap analysis** (compare it to our rulebook,
  the "playbook"). Then: **"Refusal point hit?"** Did it break one of our
  absolute deal-breaker rules?
  - **Yes** → 🟠 *BUSINESS DECISION* — a boss must choose: accept it as-is, or
    walk away.
  - **No** → go to signing.

- **No (we can negotiate)** → the **redline loop** (next step).

### 7. The redline loop (fixing the crossed-out parts) 🔁
For each change the other side made, ⚪ **map it to a section of our playbook**,
then ask **"Where does it land?"**:
- **Standard** → ⚪ Hold our position (say "no, keep it our way").
- **Fallback tier** → ⚪ Use our backup wording and write it down.
- **Banned clause** → ⚪ Strike it out and offer a replacement.
- **Refusal point or something brand-new** → 🔴 *ESCALATE!* Send it up the chain
  (Legal Director → COO → CFO) with a 2-day deadline.

Then: **"All points resolved?"**
- **No** → loop back and keep working through the changes. 🔁
- **Yes** → go to signing.

### 8. Signing and cleanup 🟣🟢
- ⚪ **Signature routing by value band** — bigger money needs a more senior
  signer.
- ⚪ **Post-signature**: mark the calendar for renewal, record any changes we
  agreed to, and set flags for next time.
- Finish at a green flag: 🟢 *SIGNED (desk edits)* or 🟢 *SIGNED (recorded deviation)*.

🎉 **The contract is done!**

---

## A full example: "Bright Kids Toy Shop" wants to buy our software

Let's walk one contract through the whole maze.

1. **Inbox item** 🔵 — An email arrives with a contract from *Bright Kids Toy Shop*.
   We **classify** it: it's a software sale, on *their* paper, worth £40,000, and
   it collects customers' names and emails (personal data). We've never dealt
   with them before.

2. **Draft attached?** 🟡 — Yes, the contract is attached. ✅ Keep going.

3. **Prior file?** 🟡 — No, first time. Keep going.

4. **Our template, no redlines?** 🟡 — No — it's *their* paper. So we head to the
   **policy gates**.

5. **Gate 1 — Personal data?** 🟣 — Yes (names + emails). We check the
   data-protection terms. **High-risk data, no DPIA?** It's just basic contact
   info, not risky, so → No. ✅ Move on.

6. **Gate 2 — Their paper?** 🟣 — Yes. We run the statutory checklist
   (bribery, slavery, tax, etc.). Looks fine. ✅

7. **Gate 3 — Beyond insured cover?** 🟣 — They want us to promise up to
   £5 million, but our insurance only covers £2 million. Uh oh → **Finance
   sign-off** needed. Finance looks at it and says "okay, approved." ✅

8. **Non-negotiable paper?** 🟡 — No, they're happy to negotiate. So we enter the
   **redline loop**. 🔁

9. **Redlines:**
   - They crossed out our late-payment fee → lands in **fallback tier**, so we
     use our backup wording and write it down. ⚪
   - They added a clause making *us* responsible for *their* mistakes → that's a
     **banned clause**, so we strike it and offer a fair replacement. ⚪
   - Everything else is **standard**, so we hold our position. ⚪

10. **All points resolved?** 🟡 — Yes! ✅

11. **Signature routing** 🟣 — £40,000 is a mid-size deal, so a manager (not the
    CEO) signs it.

12. **Post-signature** ⚪ — We set a calendar reminder for renewal next year and
    record the two changes we made.

13. 🟢 **SIGNED (recorded deviation)** — Done! 🎉

---

## The one-sentence version

> A contract comes in, answers a bunch of yes/no questions, passes some safety
> checks, gets its crossed-out bits fixed (or sent to the bosses if it's too
> tricky), and then gets signed — with a note on the calendar for next time.
