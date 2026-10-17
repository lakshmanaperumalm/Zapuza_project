# Zapuza FactoryOps — 10-Minute Demo Run Sheet

Everything below was dry-run end to end against the running app: 22 checks, 22 passed, zero browser errors.
Keep this open on a second screen, or print it.

---

## Before they walk in (2 minutes)

```bash
cd zapuza
python3 manage.py seed_demo                 # resets to the opening state
python3 manage.py runserver 0.0.0.0:8000
```

- Open **http://localhost:8000/** in full screen (F11), zoom 100 %.
- Have a terminal in the `zapuza` folder — `seed_demo` takes about 3 seconds if you need a mid-demo reset.
- Four login switches are built into the story. The **Switch user** button sits top-right, inside the user chip.

### Who to be, and when

| Step | Sign in as | Role |
|---|---|---|
| 0 – 3 | **S. Ravi** | Shift Supervisor |
| 4 – 5 (first half) | **N. Devi** | Quality Engineer |
| 5 (second half) | **V. Sundaram** | Quality Manager |
| 7 – 8 | **R. Karthik** | QA Floor Inspector |
| back in 8 | **S. Ravi** | Shift Supervisor |

---

## 0:00 — The opening frame

**Click:** *Enter Management Portal* → **S. Ravi**.

**They see:** the operations dashboard — twelve stations, hourly output, a process-hold counting down.

**Say:** *"This is the question the BRD answers: does any part move without a digital lock? Everything on this screen is live shopfloor state. There is no clipboard in this picture."*

**Point at:** the **Process hold active 01:22:14** timer in the right column, and **2 waiting** in the supervisor approval queue.

---

## 0:30 — The quality lock (Approvals)

**Click:** *Approvals* in the sidebar.

**They see:** two checklists. WO-1053 is all in tolerance with **Approve & release** live. WO-1049 — Input Shaft IS-3302 — has a red **CTQ failure** on the shaft OD: 32.006 against a 31.980–32.000 window.

**Click:** press **Approve & release** on WO-1049 — nothing happens, it's disabled. Press **Concession** — also disabled.

**Say:** *"Six microns over on a CTQ dimension and there is no path to approve or concede. This is the rule that stops a bad part shipping because somebody was in a hurry."*

**Click:** **Reject → hold** → pick the reason → **Quarantine lot**.

**They see:** a red toast naming the quarantine, and the page moves to the Material Review Board.

---

## 2:00 — The Rejection Holding Area (Holds)

**They see:** WO-1049 parked next to the seeded cure hold (WO-1045) and the open CTQ hold (WO-1051).

**Click:** on the WO-1049 card → **Record MRB disposition** → choose **Rework** → the note is pre-filled (edit it if you like) → **Record disposition**.

**They see:** the hold leaves the active list and appears under **Dispositioned**, with the name and the time.

**Say:** *"Four dispositions, no fifth option. Whichever the board chooses is written to the audit ledger with a name and a timestamp — and until one is recorded the lot cannot be scanned into any machine."*

---

## 3:00 — The dispatch interlocks

**Click:** *Dispatch Gates*.

**They see:** four shipments — **1 Gate open**, **3 Interlocked**.

**Click:** the locked one, **SHIP-2290**.

**They see:** a lockout page, not a document. It names the exact condition that failed — *all operations signed off* — instead of "documents not ready".

**Click:** back → **SHIP-2288** → the printable gate pass for Bosch India.

**Say:** *"The gate pass is computed, not filled in. Three conditions, evaluated live. The warehouse cannot print their way past a red rule."*

---

## 4:00 — Raw material at the dock (switch user)

**Click:** **Switch user** (top right) → **N. Devi**, Quality Engineer → *Material Intake*.

**Click:** on **INT-8841** (JSW, H-8101) → **Review MTC** → tick both verification statements → **Release to stores**.

**They see:** the lot flips to *Released to stores*, barcode labels issued, store bin assigned.

**Click:** on **INT-8839** (Mukand, H-8097) → **Reject intake** → choose *Chemistry outside the grade specification* → tick the quarantine acknowledgement → **Reject & raise SNCR**.

**They see:** the lot drops into supplier quarantine and an SNCR appears in the panel on the right.

**Say:** *"Carbon is 0.47 against a 0.44 maximum for EN19. The certificate is cross-checked against the engineering spec before anything is booked in — and the rejection is a supplier non-conformance, not an email."*

---

## 5:00 — Template studio (same user, then the QM)

**Click:** *Template Studio* → open the draft template **In-Process — Gear Housing G2** (grey *Draft* chip).

**Click:** **Add field** → name `Keyway width`, nominal `8`, upper `+0.1`, lower `−0.1`, pin at 60 % / 55 % → save.

**They see:** the new field appears in the list *and* as a new pin on the drawing.

**Click:** **Submit to Quality Manager**.

**They see:** the status becomes **QM approval** — the engineer cannot release it.

**Click:** **Switch user** → **V. Sundaram**, Quality Manager → *Template Studio* → open the same template (amber **QM approval** chip) → **Approve & release**.

**They see:** **Released**, plus an append-only revision-history entry with the approver's name.

**Say:** *"The form is built once and pinned to the drawing, so an inspector cannot confuse which dimension they are measuring. Nothing reaches the floor until Quality signs the revision — and released revisions are read-only."*

---

## 7:00 — The floor (switch user)

**Click:** **Switch user** → **R. Karthik**, QA Floor Inspector → then **Shopfloor Tablet** in the sidebar footer (bottom-left). The tablet opens with the handover pending.

**Click:** tick all six handover items → type `R. Karthik` → **Sign & start shift**.

**Click:** *Scan* → **Verify station** (CNC-L4 is preselected).

**They see:** the job list, with **WO-1052 · Drive Sleeve DS-7** at the top carrying a **First-piece gate** badge.

**Click:** **Open** on WO-1052 → enter `40.004`, `96.02`, `0.008` (already pre-filled) → tick the QA sign-off → **Approve & unlock counter**.

**Click:** **Simulate traveler scan — unlock checklist**.

**They see:** the checklist with the drawing and six pins.

**Click:** on the first field's gauge dropdown choose **DTI-011 · EXPIRED**, then **Submit for approval**.

**They see:** the server refuses — *gauge DTI-011 calibration expired*.

**Click:** set the gauges back to the suggested tools, fill the readings (they are pre-filled), tick the **two defect photos** box, **Submit for approval**.

**They see:** the confirmation page with the inspection ID.

**Say:** *"Two scans prove presence, an expired gauge is refused by the server rather than trusted to the operator, and an out-of-tolerance reading cannot be submitted without photos. The checklist you just signed is already in the supervisor queue."*

---

## 9:00 — Handover and the close

**Click:** **Portal** (top-left of the tablet) → **Switch user** → **S. Ravi** → *Approvals*.

**They see:** the WO-1052 checklist at the top of the queue, submitted seconds ago — and the audit trail behind it.

**Click:** *Audit Trail* → point at the newest rows: user, role, device, hash.

**Say:** *"Every action you saw today — the rejection, the MRB disposition, the release, the template approval, the checklist — is an append-only entry with a name, a device and a hash. That is the record a customer quality engineer will ask for."*

**Close on:** *Rollout Plan* (8 weeks, four phases, go-live gate) — or *Client Demo Script*, which repeats this path on one screen with tick boxes.

---

## If something goes sideways

| Situation | What to do |
|---|---|
| A demo action already ran (lot already quarantined, template already released) | Run `python3 manage.py seed_demo`, reload the tab, sign back in — about 15 seconds. |
| A red toast appears where you expected success | Read it aloud — it is the rule working. Every refusal names the exact condition. |
| A button looks disabled | That is the role model: sign in as the role that owns the decision. The matrix on **Team & Roles** shows who can do what. |
| Client asks "is this a mock?" | Press **Approve** on WO-1049, or select DTI-011 on the tablet — the server refuses both. Then open **Audit Trail**. |
| Client asks about deployment | *Rollout Plan*: 8 weeks, pilot line parallel run in weeks 5–6, paper decommissioned at phase 4. |

---

## Numbers to have ready

- **14** portal screens, **9** tablet screens
- **12** machines, **9** gauges (2 past calibration), **14** work orders, **5** intake lots, **5** templates, **4** shipments
- **3** dispatch interlocks, **6** handover checks, **4** MRB dispositions
- **31** automated business-rule tests, all passing
