from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from ..models import (
    AuditLog, Employee, Gauge, Handover, Hold, Inspection, Machine,
    Operation, Part, Shipment, Template, WorkOrder,
)
from ..services import current_employee, gate_checks, log_audit

STAGES = [
    "Raw Material Sawing", "CNC Rough Turning", "CNC Finish Turning", "Heat Treatment",
    "Precision Grinding", "Surface Coating", "Final Assembly", "Final PDI & Wash", "Packing",
]


def _page(request, template, title, group="Operations", **extra):
    ctx = {
        "page_title": title,
        "nav_group": group,
        "active": extra.pop("active", request.resolver_match.url_name),
    }
    ctx.update(extra)
    return render(request, template, ctx)


# ---------------------------------------------------------------- dashboard
@login_required
def dashboard(request):
    machines = list(Machine.objects.all())
    pending = Inspection.objects.filter(status=Inspection.Status.PENDING).select_related("wo", "wo__part")
    open_holds = Hold.objects.filter(status="open").select_related("wo", "wo__part")
    shipments = [s for s in Shipment.objects.select_related("wo", "wo__part")]
    for s in shipments:
        s.checks = gate_checks(s)
        s.clear = all(c["ok"] for c in s.checks)
    active_orders = WorkOrder.objects.exclude(status__in=["DISPATCHED"]).count()
    feed = AuditLog.objects.all()[:7]
    lineage_wo = WorkOrder.objects.filter(wo_no="WO-1042").select_related("heat", "part").first()

    ctx = {
        "machines": machines,
        "pending": pending,
        "pending_count": pending.count(),
        "open_holds": open_holds,
        "shipments": shipments[:4],
        "active_orders": active_orders,
        "feed": feed,
        "lineage_wo": lineage_wo,
        "hourly": [
            {"t": "06:00", "v": 62, "state": "behind"},
            {"t": "07:00", "v": 74, "state": "behind"},
            {"t": "08:00", "v": 81, "state": "good"},
            {"t": "09:00", "v": 68, "state": "behind"},
            {"t": "10:00", "v": 55, "state": "blocked"},
            {"t": "11:00", "v": 41, "state": "blocked"},
        ],
        "running": sum(1 for m in machines if m.state == "running"),
        "idle": sum(1 for m in machines if m.state == "idle"),
        "kpis": [
            ("Active work orders", f"{active_orders}", "3 kicked off this shift · 2 due today", "1,2,3,4,5,6,7", "#16D3A8"),
            ("First-pass yield", "97.8<small>%</small>", "▲ 0.4% vs 7-day average", "1,2,3,4,5,6,7", "#5B95FF"),
            ("On-time dispatch", "94.2<small>%</small>", "▲ 1.8% · target 95%", "2,3,4,5,6,7,7", "#A78BFA"),
            ("Open quality holds", f"{open_holds.count()}", "MRB disposition required", "2,2,3,2,2,2,3", "#F6B33C"),
            ("Pending approvals", f"{pending.count()}", "Oldest waiting 1h 31m · SLA 2h", "1,1,2,2,2,2,3", "#FF5D6C"),
        ],
    }
    return _page(request, "portal/dashboard.html", "Operations Dashboard", **ctx)


# ---------------------------------------------------------------- flow
@login_required
def flow(request):
    orders = list(WorkOrder.objects.select_related("part").prefetch_related("operations", "holds"))
    stages = []
    for i, name in enumerate(STAGES):
        jobs = [o for o in orders if o.stage_index == i and o.status not in ("DISPATCHED",)]
        jobs.sort(key=lambda o: -o.queue_hours)
        stages.append({"index": i, "name": name, "jobs": jobs,
                       "count": len(jobs),
                       "avg": round(sum(j.queue_hours for j in jobs) / len(jobs), 1) if jobs else 0})
    longest = sorted([o for o in orders if o.queue_hours], key=lambda o: -o.queue_hours)[:4]
    active = [o for o in orders if o.status not in ("DISPATCHED",)]
    avg_queue = round(sum(o.queue_hours for o in active) / len(active), 1) if active else 0
    ctx = {
        "stages": stages,
        "longest": longest,
        "over4": sum(1 for o in active if o.queue_hours > 4),
        "avg_queue": avg_queue,
        "stage_avg": [(s["name"], s["avg"]) for s in stages],
        "wip_total": sum(len(s["jobs"]) for s in stages),
        "machine_eff": [
            ("CNC Lathe #04", 89), ("VMC Station #02", 87), ("Surface Grinder #01", 83), ("CMM Inspection Cell", 95),
        ],
    }
    return _page(request, "portal/flow.html", "Flow & Bottlenecks", **ctx)


# ---------------------------------------------------------------- jobs
@login_required
def jobs(request):
    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    qs = WorkOrder.objects.select_related("part", "heat").prefetch_related("operations")
    if q:
        qs = qs.filter(Q(wo_no__icontains=q) | Q(part__name__icontains=q) | Q(part__customer__icontains=q))
    if status:
        qs = qs.filter(status=status)
    ctx = {"orders": qs, "q": q, "status": status,
           "statuses": WorkOrder.Status.choices,
           "counts": {k: WorkOrder.objects.filter(status=k).count() for k, _ in WorkOrder.Status.choices}}
    return _page(request, "portal/jobs.html", "Job Travelers", **ctx)


@login_required
def job_detail(request, wo_no):
    wo = get_object_or_404(
        WorkOrder.objects.select_related("part", "heat").prefetch_related(
            Prefetch("operations", queryset=Operation.objects.order_by("seq")),
            "inspections__measurements", "holds", "shipments",
            "first_pieces", "hourly_checks",
        ),
        wo_no=wo_no,
    )
    return _page(request, "portal/job_detail.html", f"Traveler {wo.wo_no}",
                 wo=wo, ops=list(wo.operations.all()))


# ---------------------------------------------------------------- approvals
@login_required
def approvals(request):
    pending = Inspection.objects.filter(status=Inspection.Status.PENDING).select_related("wo", "wo__part").prefetch_related("measurements")
    decided = Inspection.objects.exclude(status=Inspection.Status.PENDING).select_related("wo", "wo__part")[:6]
    return _page(request, "portal/approvals.html", "Supervisor Approval Queue",
                 pending=pending, decided=decided,
                 can_approve=bool(current_employee(request) and current_employee(request).can_approve_inspection))


@login_required
def approve_inspection(request, pk):
    insp = get_object_or_404(Inspection, pk=pk)
    emp = current_employee(request)
    if request.method != "POST":
        return redirect("factoryops:approvals")
    if not emp.can_approve_inspection:
        messages.error(request, "Only a Shift Supervisor or Plant Manager can approve an inspection.")
        return redirect("factoryops:approvals")
    if insp.ctq_failed:
        messages.error(request, "Approve is locked: a CTQ dimension is out of tolerance. Reject the lot to MRB.")
        return redirect("factoryops:approvals")
    if insp.failed:
        messages.error(request, "Non-CTQ dimensions are out of tolerance — use a concession with justification.")
        return redirect("factoryops:approvals")
    insp.status = Inspection.Status.APPROVED
    insp.decided_at = timezone.now()
    insp.decided_by = emp.name
    insp.save(update_fields=["status", "decided_at", "decided_by"])
    wo = insp.wo
    if wo.status == WorkOrder.Status.AWAITING:
        wo.status = WorkOrder.Status.READY
        wo.save(update_fields=["status"])
    for op in wo.operations.filter(status="active"):
        op.status = "done"
        op.save(update_fields=["status"])
    nxt = wo.operations.filter(status="pending").order_by("seq", "id").first()
    if nxt:
        nxt.status = "active"
        nxt.save(update_fields=["status"])
    log_audit(request, "Inspection approved", f"{wo.wo_no} · {insp.op}",
              "All parameters within tolerance · traveler signed")
    messages.success(request, f"{insp.wo.wo_no} approved — traveler signed and dispatch unlocked.")
    return redirect("factoryops:approvals")


@login_required
def concession_inspection(request, pk):
    insp = get_object_or_404(Inspection, pk=pk)
    emp = current_employee(request)
    if request.method != "POST":
        return redirect("factoryops:approvals")
    if not emp.can_approve_inspection:
        messages.error(request, "Only a Shift Supervisor or Plant Manager can issue a concession.")
        return redirect("factoryops:approvals")
    justification = request.POST.get("justification", "").strip()
    if insp.ctq_failed:
        messages.error(request, "A CTQ failure can never be conceded. Reject the lot to MRB instead.")
        return redirect("factoryops:approvals")
    if not insp.failed:
        messages.error(request, "Nothing is out of tolerance — approve normally, no concession needed.")
        return redirect("factoryops:approvals")
    if len(justification) < 12:
        messages.error(request, "A written justification of at least 12 characters is required for a concession.")
        return redirect("factoryops:approvals")
    insp.status = Inspection.Status.CONCEDED
    insp.decided_at = timezone.now()
    insp.decided_by = emp.name
    insp.note = justification
    insp.save(update_fields=["status", "decided_at", "decided_by", "note"])
    wo = insp.wo
    wo.status = WorkOrder.Status.CONCESSION
    wo.save(update_fields=["status"])
    log_audit(request, "Concession issued", f"CC-{insp.pk:04d} · {wo.wo_no}", justification[:150])
    messages.warning(request, f"Concession recorded for {wo.wo_no} — lot permanently flagged in quality history.")
    return redirect("factoryops:approvals")


@login_required
def reject_inspection(request, pk):
    insp = get_object_or_404(Inspection, pk=pk)
    emp = current_employee(request)
    if request.method != "POST":
        return redirect("factoryops:approvals")
    if not emp.can_approve_inspection:
        messages.error(request, "Only a Shift Supervisor or Plant Manager can quarantine a lot.")
        return redirect("factoryops:approvals")
    reason = request.POST.get("reason", "CTQ dimension out of tolerance")
    note = request.POST.get("note", "").strip()
    fault = insp.failed[0] if insp.failed else None
    insp.status = Inspection.Status.REJECTED
    insp.decided_at = timezone.now()
    insp.decided_by = emp.name
    insp.note = note or reason
    insp.save(update_fields=["status", "decided_at", "decided_by", "note"])

    from ..services import quarantine_lot
    hold = quarantine_lot(request, insp, reason if not fault else
                          f"{fault.name} {fault.formatted_value} outside {fault.spec_text}", note)
    messages.error(request, f"{insp.wo.wo_no} quarantined as {hold.id and 'QUA-' + str(hold.id).zfill(4)} — MRB disposition required.")
    return redirect("factoryops:holds")


# ---------------------------------------------------------------- holds
@login_required
def holds(request):
    open_holds = Hold.objects.filter(status="open").select_related("wo", "wo__part", "wo__heat")
    disposed = Hold.objects.exclude(status="open").select_related("wo", "wo__part")[:6]
    return _page(request, "portal/holds.html", "Quality Holds & MRB",
                 open_holds=open_holds, disposed=disposed,
                 dispositions=Hold.DISPOSITIONS,
                 can_dispose=bool(current_employee(request) and current_employee(request).can_dispose_hold))


@login_required
def dispose_hold(request, pk):
    hold = get_object_or_404(Hold, pk=pk)
    emp = current_employee(request)
    if request.method != "POST":
        return redirect("factoryops:holds")
    if not emp.can_dispose_hold:
        messages.error(request, "Only the Shift Supervisor, Quality Manager or Plant Manager can dispose a hold.")
        return redirect("factoryops:holds")
    disposition = request.POST.get("disposition")
    note = request.POST.get("note", "").strip()
    if disposition not in dict(Hold.DISPOSITIONS):
        messages.error(request, "Choose one of the four MRB dispositions.")
        return redirect("factoryops:holds")
    if len(note) < 10:
        messages.error(request, "Record the containment / disposition note before closing the hold.")
        return redirect("factoryops:holds")
    hold.status = "dispositioned"
    hold.disposition = disposition
    hold.disposition_note = note
    hold.disposition_by = emp.name
    hold.disposition_at = timezone.now()
    hold.save()
    wo = hold.wo
    wo.status = WorkOrder.Status.IN_PROGRESS if disposition in ("rework", "rtv") else WorkOrder.Status.QUARANTINED
    if disposition == "scrap":
        wo.status = WorkOrder.Status.QUARANTINED
    wo.save(update_fields=["status"])
    log_audit(request, "MRB disposition recorded", f"{wo.wo_no} · {hold.get_disposition_display()}",
              note[:150])
    messages.success(request, f"MRB disposition recorded — {wo.wo_no} marked {hold.get_disposition_display()}.")
    return redirect("factoryops:holds")


# ---------------------------------------------------------------- dispatch
@login_required
def dispatch(request):
    shipments = list(Shipment.objects.select_related("wo", "wo__part"))
    for s in shipments:
        s.checks = gate_checks(s)
        s.clear = all(c["ok"] for c in s.checks)
    return _page(request, "portal/dispatch.html", "Dispatch Gates", shipments=shipments)


@login_required
def gate_pass(request, pk):
    ship = get_object_or_404(Shipment.objects.select_related("wo", "wo__part", "wo__heat"), pk=pk)
    checks = gate_checks(ship)
    clear = all(c["ok"] for c in checks)
    if request.method == "POST" and clear:
        ship.status = "shipped"
        ship.save(update_fields=["status"])
        log_audit(request, "Gate pass printed", f"{ship.no} · {ship.customer}",
                  f"Crate {ship.crate} · vehicle {ship.vehicle}")
        messages.success(request, f"Gate pass for {ship.no} printed — dispatch cleared.")
        return redirect("factoryops:dispatch")
    if not clear:
        log_audit(request, "Shipping gate blocked", f"{ship.no} · {ship.wo.wo_no}",
                  "; ".join(c["label"] for c in checks if not c["ok"]), user="System",
                  role="Interlock Engine", device="SERVER")
    return _page(request, "portal/gate_pass.html", f"Gate Pass {ship.no}",
                 ship=ship, checks=checks, clear=clear)


# ---------------------------------------------------------------- traceability
@login_required
def trace(request):
    from ..models import Heat
    heats = Heat.objects.all()
    default = (heats.filter(orders__shipments__isnull=False).first() or heats.first())
    heat_no = request.GET.get("heat") or (default.heat_no if default else None)
    heat = heats.filter(heat_no=heat_no).first()
    orders = []
    if heat:
        for wo in (WorkOrder.objects.filter(heat=heat).select_related("part")
                   .prefetch_related("operations", "shipments", "inspections__measurements")):
            insp = next(iter(wo.inspections.all()), None)
            seen = []
            for m in (insp.measurements.all() if insp else []):
                if m.gauge and m.gauge not in seen:
                    seen.append(m.gauge)
            wo.insp = insp
            wo.gauge_codes = seen
            orders.append(wo)
    claimed = request.GET.get("recall")
    return _page(request, "portal/trace.html", "Heat-Lot Traceability",
                 heats=heats, heat=heat, orders=orders, recall=claimed == "1")


# ---------------------------------------------------------------- master data
@login_required
def master(request):
    from ..models import Heat
    tab = request.GET.get("tab", "machines")
    machines = Machine.objects.all()
    return _page(request, "portal/master.html", "Master Data & Calibration", tab=tab,
                 machines=machines, gauges=Gauge.objects.all(),
                 templates=Template.objects.all(), heats=Heat.objects.all(),
                 parts=Part.objects.all(), bays=machines.values("dept").distinct().count(),
                 expired_gauges=sum(1 for g in Gauge.objects.all() if g.is_expired),
                 pm_overdue=sum(1 for m in machines if m.pm_status != "ok"))


# ---------------------------------------------------------------- audit
@login_required
def audit(request):
    q = request.GET.get("q", "").strip()
    qs = AuditLog.objects.all()
    if q:
        qs = qs.filter(Q(action__icontains=q) | Q(user__icontains=q) | Q(entity__icontains=q))
    return _page(request, "portal/audit.html", "Audit Trail", entries=qs[:80], q=q)


# ---------------------------------------------------------------- team
@login_required
def team(request):
    matrix = [
        {"role": "Machine Operator", "cells": ["Full", "—", "—", "—", "—"]},
        {"role": "QA Floor Inspector", "cells": ["Full", "View", "—", "—", "—"]},
        {"role": "Shift Supervisor", "cells": ["Full", "Full", "View", "—", "View"]},
        {"role": "Quality Engineer", "cells": ["View", "View", "Full", "Full", "—"]},
        {"role": "Quality Manager", "cells": ["View", "Full", "Approve", "Full", "Full"]},
        {"role": "Plant Manager", "cells": ["View", "Full", "View", "Full", "Full"]},
    ]
    return _page(request, "portal/team.html", "Team & Roles",
                 people=Employee.objects.select_related("user"),
                 handovers=Handover.objects.all()[:4],
                 matrix=matrix,
                 on_shift=Employee.objects.filter(online=True))


# ---------------------------------------------------------------- rollout / demo
@login_required
def rollout(request):
    risks = [
        ("Shopfloor adoption / glove UI", "High", "Champion-led training, side-by-side paper running"),
        ("Wi-Fi dead zones on the floor", "Medium", "Pre-deployment survey + offline tablet caching"),
        ("Gauge discipline at the station", "Medium", "Calibration lockout enforced by the server"),
        ("Pilot slowing production", "Low", "Parallel run on one line only; rollback plan ready"),
    ]
    return _page(request, "portal/rollout.html", "Implementation Rollout Plan", phases=PHASES, risks=risks)


@login_required
def demo(request):
    return _page(request, "portal/demo.html", "Client Demo Script", steps=DEMO_STEPS)


PHASES = [
    {"n": 1, "name": "Infrastructure & Master Data", "weeks": "Weeks 1–2", "start": 1, "span": 2,
     "status": "done", "progress": 100, "owner": "Zapuza implementation lead · Plant IT",
     "focus": "Get the plant digitally mirrored before a single inspection is recorded.",
     "work": ["Industrial Wi-Fi survey + access points installed on both shopfloors",
              "Workstation QR plates mounted and verified at 12 stations",
              "Central web portal provisioned, SSO and role presets configured",
              "12 machines, 9 gauges and shift patterns registered",
              "Part templates + blueprints configured with Quality Engineering"],
     "exit": "Master data signed off by the Plant Manager; every QR plate scans correctly from a tablet."},
    {"n": 2, "name": "Champion Training & Dry Run", "weeks": "Weeks 3–4", "start": 3, "span": 2,
     "status": "active", "progress": 65, "owner": "Quality Manager · Zapuza trainer",
     "focus": "Train the people who will train the floor, and rehearse on sample work orders.",
     "work": ["Hands-on training for Quality Engineers, Supervisors and 6 shopfloor champions",
              "Sample work orders run end-to-end in a controlled lab environment",
              "Blueprint pinning and template revision workflow drilled with QE team",
              "Glove-friendly UI practice session on the actual industrial tablets",
              "Shift handover and MRB disposition role-plays"],
     "exit": "All champions certified; dry-run checklists completed with zero blocking defects."},
    {"n": 3, "name": "Pilot Line Parallel Run", "weeks": "Weeks 5–6", "start": 5, "span": 2,
     "status": "todo", "progress": 0, "owner": "Production Lead · Quality Manager",
     "focus": "Prove measurement accuracy and operator speed on one live line.",
     "work": ["Deploy tablets to CNC Machining Line #1 only",
              "Run paper travelers and digital tablets side-by-side for two weeks",
              "Compare inspection cycle times and first-pass yield daily",
              "Tune inspection frequencies and tolerance defaults with real data",
              "Fix ergonomics issues reported by operators"],
     "exit": "Digital inspection within 10% of paper cycle time; measurement variance below 1%; pilot sign-off."},
    {"n": 4, "name": "Full Go-Live & Paper Decommissioning", "weeks": "Weeks 7–8", "start": 7, "span": 2,
     "status": "todo", "progress": 0, "owner": "Plant Manager · Zapuza",
     "focus": "Roll out everywhere, switch on the interlocks and remove paper for good.",
     "work": ["Tablets deployed across machining, heat treatment, grinding, assembly and dispatch",
              "Shipping clearance interlocks activated on all dispatch lanes",
              "Customer QR labels and inspection certificates enabled",
              "All paper inspection clipboards and traveler cards removed",
              "Hypercare: on-site support for two weeks, daily stand-up"],
     "exit": "100% of work orders running digitally; gate-pass interlock live; paper decommissioning witnessed by Quality."},
]

DEMO_STEPS = [
    {"n": 0, "title": "Opening frame", "minutes": "0:00 – 0:30", "script": True,
     "say": "This is the question the whole BRD answers: does any part move without a digital lock? "
            "On this dashboard everything you see is live shopfloor state — twelve stations, throughput "
            "against target, a cooling hold counting down, and the approval queue. There is no clipboard "
            "anywhere in this picture.",
     "check": "Point out the process-hold timer ticking down in the right column.",
     "url": "/portal/", "label": "Open Dashboard"},
    {"n": 1, "title": "The quality lock — approvals", "minutes": "0:30 – 2:00",
     "say": "Here is WO-1049, an Input Shaft at final PDI. One CTQ dimension — the shaft OD — is six "
            "microns over. Watch what the system does. Approve is disabled. Concession is disabled, because "
            "CTQ failures can never be conceded. The only path is to quarantine the lot, which moves it into "
            "the MRB holding area. That single rule is what stops a bad part being shipped because someone "
            "was in a hurry.",
     "check": "Try to approve WO-1049 — the server refuses. Then reject the lot.",
     "url": "/portal/approvals/", "label": "Open Approvals"},
    {"n": 2, "title": "Rejection Holding Area & MRB", "minutes": "2:00 – 3:00",
     "say": "The lot is now physically and digitally frozen. Production cannot scan it into any downstream "
            "machine, and the warehouse cannot issue the stock. The Material Review Board has exactly four "
            "dispositions — rework, scrap, return to vendor, or a customer concession — and whichever they "
            "choose is written to the audit ledger with a timestamp and a name.",
     "check": "Record a disposition and watch the hold leave the active list.",
     "url": "/portal/holds/", "label": "Open Quality Holds"},
    {"n": 3, "title": "Dispatch interlocks", "minutes": "3:00 – 4:00",
     "say": "Shipping is where most factories leak defects, so the gate pass is not a document you fill in — "
            "it is a set of three conditions the system checks automatically: every operation signed off, "
            "every hold time satisfied, and the final PDI approved. If any one fails, the warehouse sees a "
            "lockout instead of a gate pass, and it names the exact rule that is failing.",
     "check": "Open the locked gate pass on SHIP-2290, then the cleared one on SHIP-2288.",
     "url": "/portal/dispatch/", "label": "Open Dispatch Gates"},
    {"n": 4, "title": "Raw material intake & MTC", "minutes": "4:00 – 5:00",
     "say": "The quality trail starts at the dock. Every intake needs a readable mill test certificate and a "
            "verified heat number before it can even be saved. The certified chemistry is cross-checked "
            "against the engineering specification — H-8101 passes, H-8097 is out on carbon and is rejected "
            "into supplier quarantine with a non-conformance report.",
     "check": "Verify and release H-8101, then reject H-8097 and see the SNCR appear.",
     "url": "/portal/intake/", "label": "Open Material Intake"},
    {"n": 5, "title": "Template studio & blueprint pins", "minutes": "5:00 – 6:00",
     "say": "Quality engineers build the inspection form once and pin each measurement onto the actual "
            "drawing — so an inspector can never confuse which dimension they are measuring. Mark a "
            "dimension CTQ and it becomes visually different on the tablet and cannot be conceded. Nothing "
            "reaches the floor until the Quality Manager approves the revision.",
     "check": "Add a field, submit rev D, then approve it as Quality Manager.",
     "url": "/portal/studio/", "label": "Open Template Studio"},
    {"n": 6, "title": "Flow, bottlenecks and traceability", "minutes": "6:00 – 7:00",
     "say": "Because every operator scans in and out, the portal can show exactly where lots are sitting "
            "between stations. Heat treatment is the bottleneck at over five hours of average queue — a "
            "conversation for the production meeting, not a guess. And on traceability: if a supplier flags "
            "a heat lot, one query finds every part, crate and customer involved.",
     "check": "Highlight the heat-treatment column, then run the recall simulation.",
     "url": "/portal/flow/", "label": "Open Flow & Bottlenecks"},
    {"n": 7, "title": "The floor — tablet inspection", "minutes": "7:00 – 9:00",
     "say": "This is what the operator actually touches. Glove-friendly, high contrast, and locked to the "
            "station. Two scans are required: the machine plate and the job traveler. Each measurement turns "
            "green or red instantly, an expired gauge blocks the entry until a calibrated tool is scanned, and "
            "an out-of-tolerance reading forces photos of the defect.",
     "check": "Scan the station, approve the first piece on WO-1052, then submit a checklist.",
     "url": "/tablet/", "label": "Open Shopfloor Tablet"},
    {"n": 8, "title": "Handover and the close", "minutes": "9:00 – 10:00",
     "say": "Shift change is where paper systems quietly break, so the handover is a signed digital log — open "
            "jobs, scrap, alerts, tool wear, machine health — and the incoming operator cannot start work "
            "until they acknowledge it. The inspection you just submitted is already in the supervisor queue, "
            "with an immutable audit record behind it.",
     "check": "Sign the shift handover, then show the submitted checklist in the supervisor queue.",
     "url": "/tablet/handover/", "label": "Open Shift Handover"},
]
