# Zapuza FactoryOps QC — Working Django Prototype

A running web application that demonstrates the **Factory Operations & Quality Control System** from the Zapuza Technologies LLP BRD v5.0 (Oct 2026).
Two experiences share one database and one rule engine:

- **Management web portal** — 14 screens for supervisors, quality engineers and plant management.
- **Shopfloor tablet app** — the operator / inspector flow, sized for gloves and a 10-inch industrial tablet.

This is not a clickable mock-up. Every screen is a Django view, every button posts to the server, every decision is written to the database and to an append-only audit ledger. Where the prototype says a rule is enforced, the rule is enforced **server-side** — you can try to break it in front of the client.

---
## Quick start

```bash
cd zapuza
python3 -m pip install -r requirements.txt      # Django 6.1.2
python3 manage.py migrate
python3 manage.py seed_demo                     # loads the demo factory
python3 manage.py runserver 0.0.0.0:8000
```

Open **http://localhost:8000/**.

The cover page offers two doors: *Enter Management Portal* and *Open Shopfloor Tablet*.
Both land on a demo-login screen — pick a user, no password typing needed (the password for every account is `zapuza`).

---

## Demo users

| User | Role | Use them for |
|---|---|---|
| **S. Ravi** | Shift Supervisor | approvals, concessions, rejections, MRB disposition, gate passes |
| **R. Karthik** | QA Floor Inspector | the tablet flow, submitting checklists |
| **N. Devi** | Quality Engineer | material intake, MTC release, template studio edits |
| **V. Sundaram** | Quality Manager | releasing template revisions, full override authority |
| **P. Anandan** | Plant Manager | everything, including the dispatch gate |
| **A. Murugan / K. Vel** | Machine Operators | seeing what a role *cannot* do |

Role permissions are real Django groups checked by the views — signing in as an operator and trying to approve an inspection produces a refusal, not a hidden button.

---

## The ten-minute demo path

A printable, click-by-click version with role switches, exact button names and fallbacks lives in **`DEMO-RUNSHEET.md`** next to this file.


1. **Dashboard** — live floor, hourly output, the hold countdown, the approval queue.
2. **Approvals → WO-1049** — shaft OD is six microns over. Approve is disabled, concession is refused because it is a CTQ dimension. Reject → the lot moves to **Quality Holds** with an MRB disposition.
3. **Dispatch Gates** — three interlocks computed live. SHIP-2288 is clear, the other three name exactly which rule failed (incomplete operations, mandatory cure hold, PDI pending).
4. **Material Intake** — INT-8839's mill certificate says 0.47 % carbon against an EN19 maximum of 0.44. Release is refused; rejecting raises an SNCR and freezes the stock.
5. **Template Studio** — a draft revision, a pin dropped on the drawing, submit → Quality Manager approve → the revision becomes read-only with an append-only history.
6. **Traceability** — pick heat H-8042 and follow raw material → two work orders → inspection with the instruments used → crate → customer.
7. **Shopfloor Tablet** — sign the shift handover, scan station CNC-L4, open WO-1052, pass the first-piece gate, then measure: an expired gauge (DTI-011) refuses the reading, and an out-of-tolerance value demands two defect photos. Submit, then switch back to the portal — the new checklist is waiting in the supervisor's queue.
8. **Client Demo Script** — the same walkthrough on one screen with what to say, what to click and a checkbox per section.

---

## Management portal — 14 screens

| Screen | What it demonstrates |
|---|---|
| **Dashboard** | 12-station floor, hourly output vs target, cooling-hold countdown, approval queue, dispatch readiness, lineage snapshot, audit-linked activity feed |
| **Flow & Bottlenecks** | Nine-stage WIP board, queue-age colouring, automatic escalation above 4 h, stage cycle efficiency |
| **Job Travelers** | 14 work orders with nine-operation travelers, filters and a full traveler drawer (heat, operator, machine, gauge record) |
| **Approvals** | Supervisor queue with real measurements and defect photos. Approve blocked on any out-of-tolerance value; CTQ failures can never be conceded; concessions need a ≥ 12-character justification |
| **Quality Holds (MRB)** | Rejection Holding Area and the four dispositions — rework, scrap, return to vendor, customer concession — each with a written containment note |
| **Dispatch Gates** | The three interlocks (all operations signed / holds satisfied / PDI approved), gate-pass lockout naming the failing rule, printable gate pass |
| **Material Intake & MTC** | Dock receiving → MTC → heat-number cross-check → lab sample → release or **reject with SNCR into supplier quarantine**. Chemistry is checked against grade specs |
| **Template Studio** | Revision workflow: draft → pending → released, blueprint pins, tolerances, CTQ flags, QM-only approval, immutable released revisions |
| **Traceability** | Heat → MTC → work orders → inspection (with instruments) → crate → customer, plus a forward **recall simulation** |
| **Master Data & Calibration** | Machines with PM locks, gauge register with expired/expiring tools, PDI templates, heat lots, parts |
| **Audit Trail** | Append-only ledger with user, role, device, IP and hash; searchable |
| **Team & Roles** | Six role presets, who is on shift, the role-safeguard matrix, digital handover log |
| **Rollout Plan** | Eight-week / four-phase Gantt, exit criteria, go-live gate, risks |
| **Client Demo Script** | Ten-minute guided walkthrough with live jump buttons and saved progress |

## Shopfloor tablet app

Home (turn lock, hold timer, job list) → station QR → job traveler QR → first-piece gate → inspection checklist with the engineering drawing → submit → **hourly in-process sample** (three parts, live countdown, pass/fail history) → shift handover.

The tablet walks the operator through this sequence, and enforces each step:

1. **Handover signed** before job entry.
2. **Station QR scanned** before the job list — and a PM-overdue machine (HT-01) refuses to open.
3. **Traveler QR scanned** before measurements — the two-scan rule proves presence.
4. **First piece measured and signed off** before the counter unlocks for WO-1052.
5. **Every checklist field mandatory**, every reading tied to a **calibrated gauge**; an expired gauge is refused by the server.
6. **Out-of-tolerance readings require two defect photos**, otherwise the submit is rejected.
7. An **hourly sample** is three parts measured against the drawing, with the last samples kept on screen for the next operator.
8. A submitted checklist becomes a **pending inspection** in the portal and moves the work order to *Awaiting approval* — with an audit entry.

---

## Business rules that live in code

| Rule | Where | Try it |
|---|---|---|
| Approve locked while any dimension is out of tolerance | `views/portal.py · approve_inspection` | Approve WO-1049 |
| CTQ failures can never be conceded | `concession_inspection` | Concede WO-1049 |
| Concession requires a real justification (≥ 12 chars) | `concession_inspection` | Type "ok" |
| Reject → hold + MRB, work order quarantined | `services.quarantine_lot` | Reject WO-1049 |
| Gauge calibration gates measurement | `views/tablet.py · inspect` | Select DTI-011 in the checklist |
| MTC + heat-number cross-check before release | `views/intake.py · verify_lot` | Release INT-8839 |
| Chemistry versus grade spec, SNCR on failure | `services` + `intake` | Lab-fail INT-8840 |
| Quarantined stock is not issuable | `IntakeLot.Status` | — |
| Template revisions: QM approval, released = read-only | `views/studio.py` | Add a field to a released template |
| Three dispatch interlocks, every open hold blocks | `services.gate_checks` | Open SHIP-2290 / 2291 / 2292 |
| Append-only hash-chained audit log | `services.log_audit` | Every decision above writes a row |
| Shift handover, station lock, traveler lock, first piece | `views/tablet.py` | Walk the tablet flow out of order |

---

## Tests

```bash
python3 manage.py test factoryops
```

31 tests run against the same seeded dataset the client sees: approvals, concessions, dispatch interlocks, intake chemistry, template lifecycle, the tablet gates (handover, station lock, traveler lock, first piece, gauge, photos, hourly sample), the audit ledger, and a render check of every portal screen and master-data tab.

```
Ran 31 tests — OK
```

---

## Reset between demos

```bash
python3 manage.py seed_demo
```

Rebuilds every table to the opening state: 14 work orders, 5 inspections (one approvable, one CTQ-locked, one conceded, one rejected, one approved), 5 intake lots, 5 templates, 4 shipments (one clear, three interlocked), 2 open holds plus 1 dispositioned, a signed first piece and one hourly sample, 7 users.

---

## Project layout

```
zapuza/
├── manage.py
├── requirements.txt              Django 6.1.2
├── db.sqlite3                    demo database
├── zapuza/                       settings + root URLs
├── factoryops/
│   ├── models.py                 WorkOrder, Operation, Inspection, Measurement, Hold,
│   │                             Shipment, IntakeLot, SNCR, Template, TemplateField,
│   │                             Gauge, Machine, Heat, Part, Employee, AuditLog, Handover…
│   ├── services.py               the rules: gate checks, quarantine, audit chaining
│   ├── context.py                navigation, shift clock, counters
│   ├── views/                    auth · portal · tablet · intake · studio
│   ├── templatetags/ui.py        icons and small template helpers
│   ├── management/commands/seed_demo.py
│   ├── migrations/
│   └── tests.py                  31 business-rule tests
├── templates/                    portal/, tablet/, partials/
└── static/css, static/js         the dark operations UI
```

---

## Scope and status

Built for demonstration, not for production:

- SQLite database, one process, `DEBUG=1`, no HTTPS — by design, so it runs anywhere in one command.
- File uploads are modelled (MTC filenames, defect photo counts), not stored as binaries.
- Push notifications, e-mail and ERP integration are out of scope; the UI shows where they would attach.
- Production hardening (Postgres, real authentication provider, object storage, backups, HTTPS) is a deployment task, not a redesign — the rules already live on the server.

### Known caveat — X-Frame-Options

`django.middleware.clickjacking.XFrameOptionsMiddleware` has been **removed** from `settings.py` so the Arena live preview works inside an iframe. Before deploying to any real network, restore it by adding it back to the `MIDDLEWARE` list. Without it, the app is vulnerable to clickjacking. This is a standard Django security default, not a custom code change.

### Demo dry-run status

The full 22-step scripted dry run (the path the client will walk) passes end-to-end:

```
PASS  0 · cover → portal door
PASS  0 · dashboard live hold timer
PASS  1 · approvals: approve + concession locked on CTQ fail
PASS  1 · approvals: reject quarantines WO-1049
PASS  2 · holds: MRB disposition closes the hold
PASS  3 · dispatch: one clear gate, three interlocked
PASS  3 · dispatch: locked gate pass names the failing rule
PASS  3 · dispatch: cleared gate pass renders
PASS  6a · flow board bottleneck
PASS  6b · traceability recall
PASS  4 · intake: release H-8101 as Quality Engineer
PASS  4 · intake: reject H-8097 → SNCR
PASS  5 · studio: add a pinned field to the draft
PASS  5 · studio: submit revision to Quality Manager
PASS  5 · studio: QM approves and releases
PASS  8 · tablet: sign shift handover
PASS  7 · tablet: station scan unlocks the job list
PASS  7 · tablet: first-piece gate
PASS  7 · tablet: traveler scan unlocks checklist
PASS  7 · tablet: expired gauge refused
PASS  7 · tablet: full checklist submits
PASS  8 · submitted checklist lands in the queue
22/22 steps passed — 0 console errors
```

The earlier single-file click-through (`zapuza-qc-prototype.html`) is kept only as design reference; this Django application supersedes it.
.

🎥 Project Demo Video

Watch the Demo Video: "Click here to watch the project demo" (https://drive.google.com/file/d/16SUId61j8e0DMQ48UZvwizhZK8v9CF3f/view?usp=drivesdk)
