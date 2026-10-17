# Zapuza FactoryOps — Client Handover

> **Prepared for:** Zapuza Technologies LLP
> **Scope:** FactoryOps digital-thread management portal + shopfloor tablet application
> **Framework:** Django 5 (Python), single-server, SQLite / switchable to PostgreSQL
> **Demo password for all accounts:** `zapuza`

---

## What was built

A complete, working factory-floor operations and quality-control application that directly implements every requirement in the 17-page BRD. The system has two interfaces running from the same database:

| Interface | URL | Audience |
|---|---|---|
| **Management Portal** | `/portal/` (desktop, ≥ 1280 px) | Supervisors, quality engineers, QMs, management |
| **Shopfloor Tablet** | `/tablet/` (touch, 810 × 1280) | QA inspectors, machine operators |

Every action is server-enforced — there are no client-side-only rules that a browser's developer tools could bypass.

---

## The 14 portal screens

| # | Screen | URL | What it does |
|---|---|---|---|
| 1 | **Operations Dashboard** | `/portal/` | Live stations (12), open work orders, production counts, process-hold timer, supervisor queue |
| 2 | **Supervisor Approvals** | `/portal/approvals/` | Pending inspections with dimension vs. tolerance table, approve / concession / reject (role- and CTQ-gated) |
| 3 | **Rejection Holding Area** | `/portal/holds/` | MRB cards with 4 dispositions: scrap, rework, return-to-supplier, concession |
| 4 | **Dispatch Gate** | `/portal/dispatch/` | Shipment cards with pass / interlocked status; 3 interlocks per shipment |
| 5 | **Gate Pass** | `/portal/dispatch/1/` | Printable gate pass computed from all-clear status |
| 6 | **Jobs & Routing** | `/portal/jobs/` | All work orders sorted first-piece-first, status chips, progress bars |
| 7 | **Job Detail** | `/portal/jobs/1/` | Routing with completed ops, per-operation dimensions, templates, holds |
| 8 | **Production Flow Board** | `/portal/flow/` | Bottleneck detection, station-level cards, shift targets |
| 9 | **Raw Material Intake** | `/portal/intake/` | Heat/MTC verification, release to stores, reject with SNCR trigger |
| 10 | **Template Studio** | `/portal/studio/` | 3-step lifecycle: Draft → QM approval → Released; pinned CTQ fields |
| 11 | **Master Registers** | `/portal/master/` | 5 tabs: parts, gauges (calibration tracked), stations, templates, raw-material grades |
| 12 | **Audit Trail** | `/portal/audit/` | Append-only ledger: user, role, device, timestamp, hash |
| 13 | **Team & Roles** | `/portal/team/` | 7 users, 4 roles, role-permission matrix |
| 14 | **Traceability & Recall** | `/portal/trace/` | Heat → parts → work orders → inspections; one-click recall simulation |

---

## The 9 tablet screens

| # | Screen | URL | What it does |
|---|---|---|---|
| 1 | **Shift Handover** | `/tablet/handover/` | 6-point checklist, signature capture, supervisor queue |
| 2 | **Station Scan** | `/tablet/scan/` | Machine identity locks to selected station |
| 3 | **Job List** | `/tablet/jobs/` | Pending jobs at this machine, first-piece badge |
| 4 | **Traveler Scan** | `/tablet/traveler/` | Barcode simulation, unlocks checklist |
| 5 | **First-Piece Gate** | `/tablet/first-piece/WO-1052/` | 3 critical dimensions + supervisor sign-off before production starts |
| 6 | **Inspection Checklist** | `/tablet/inspect/WO-1052/` | Drawing with pinned measurement fields, gauge tracking, photo rule |
| 7 | **Submission Confirmation** | `/tablet/submitted/` | Summary card with inspection ID |
| 8 | **Hourly Sample** | `/tablet/hourly/WO-1052/` | Three readings against 31.980–32.000 mm window; auto-fail if any one out |
| 9 | **Demo walkthrough** | `/portal/demo/` | 10-step script with says and checks, accessible in-app |

---

## Business rules enforced by the server

Every rule below has a corresponding automated test (31 total, all passing).

### Approvals gate
- Approve button: disabled unless user has `can_approve` AND no CTQ failures
- Concession button: disabled unless user has `can_concession` AND no CTQ failures
- Reject: always available; sets WO status to ON_HOLD and opens MRB card
- Approving advances the next pending operation to IN_PROGRESS

### Dispatch interlocks
A shipment gate is locked until all three are green:
1. All work orders on the shipment are COMPLETED
2. Gate pass requirements are met
3. No open holds on any work order

### Raw material intake
- Release: verifies MTC type, grade, and lot; heat must be within specification; assigns store bin
- Reject: heat out-of-spec or MTC not verified → supplier quarantine + SNCR auto-generated
- Lab hold: sends to lab for independent verification

### Template lifecycle
- Draft → only editable state; Engineer creates fields, pins to drawing coordinates
- Submitted → QM approval; Engineer cannot edit
- Released → read-only; revision history is append-only
- QM can return a submission to draft

### Tablet gates
- **Two-scan lock:** station scan + traveler scan must both complete before inspection is allowed
- **First-piece gate:** 3 critical dimensions (40 ± 0.02 / 96 ± 0.25 / runout ≤ 0.02); supervisor sign-off before production counter unlocks
- **Expired-gauge refusal:** server rejects any submission using a gauge past its calibration date
- **Photo rule:** out-of-tolerance readings require photo evidence; server blocks submission without it
- **Hourly sample:** 3 consecutive readings all within 31.980–32.000 mm; fail logs warning + supervisor alert + audit entry

---

## Seed data

Run once to populate the demo database:

```bash
cd zapuza
python3 manage.py seed_demo
```

Creates: 7 users, 12 machines, 9 gauges (2 past calibration), 15 parts, 14 work orders, 5 intake lots, 5 templates, 5 shipments, 3 SNCRs, 2 open holds, and first-piece / hourly sample records.

---

## User accounts

| Login | Name | Role | What they own in the demo |
|---|---|---|---|
| `sravi` | S. Ravi | Shift Supervisor | Approvals, holds, dispatch, flow board |
| `rkarthik` | R. Karthik | QA Floor Inspector | Tablet: handover → scan → inspect → submit |
| `ndevi` | N. Devi | Quality Engineer | Raw material intake, template drafts |
| `amurugan` | A. Murugan | Operator | Tablet: hourly sample |
| `kvel` | K. Vel | Production Manager | Dashboard, jobs, rollout plan |
| `pmanager` | P. Manager | Plant Manager | Master registers, audit trail, team |
| `qmanager` | V. Sundaram | Quality Manager | Template approvals, holds decisions |

All passwords: `zapuza`

---

## Running the app

```bash
cd zapuza
pip install -r requirements.txt
python3 manage.py migrate
python3 manage.py seed_demo
python3 manage.py runserver 0.0.0.0:8000
```

Then open http://localhost:8000/ in a browser.

---

## Known caveat: X-Frame-Options

The Django middleware `XFrameOptionsMiddleware` has been **removed** from `settings.py` for this demo environment, because the Arena preview system renders the app inside an iframe. This is the only reason the live preview works.

**Before deploying to production or exposing the app on a network**, restore the middleware by adding back:

```python
"django.middleware.clickjacking.XFrameOptionsMiddleware",
```

in `settings.py` MIDDLEWARE list. Without it, the app is vulnerable to clickjacking attacks. This is a standard Django security measure, not a custom code change.

---

## Files delivered

| Path | What |
|---|---|
| `zapuza/manage.py` | Django project entry point |
| `zapuza/requirements.txt` | Python dependencies (Django 5) |
| `zapuza/factoryops/` | All models, views, services, templates, static assets, tests, seed command |
| `README-zapuza-prototype.md` | Technical README with architecture notes |
| `DEMO-RUNSHEET.md` | Printable 10-minute click-by-click demo script |
| `zapuza/templates/` | 32 Django templates (portal + tablet + partials) |
| `zapuza/static/` | CSS (app.css, django.css) + JS (app.js for modals/clock/toasts) |

---

## What to do on presentation day

1. `python3 manage.py seed_demo` (3 seconds, resets everything)
2. `python3 manage.py runserver 0.0.0.0:8000`
3. Open `DEMO-RUNSHEET.md` on a second screen
4. Full-screen the browser (F11), zoom 100 %
5. Walk the 10 steps, switching users at the marked points
6. If anything stumbles: `seed_demo`, reload, sign back in — 15 seconds total