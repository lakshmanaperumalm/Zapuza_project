"""Business rules: the quality interlocks that make the system defensible.

Every rule here is enforced on the server. Templates only *reflect* the result —
they are never the source of truth.
"""
from __future__ import annotations

import hashlib
from datetime import datetime

from django.contrib import messages
from django.shortcuts import redirect

from .models import AuditLog, Employee, Hold, Inspection, Shipment, WorkOrder

# ---------------------------------------------------------------- specs
GRADE_SPECS = {
    "EN8D": {"C": (0.36, 0.44), "Mn": (0.60, 1.00), "Si": (0.10, 0.40), "S": (0.0, 0.05), "P": (0.0, 0.05)},
    "EN19": {"C": (0.36, 0.44), "Mn": (0.50, 0.80), "Cr": (0.90, 1.20), "Mo": (0.25, 0.35)},
    "20MnCr5": {"C": (0.17, 0.22), "Mn": (1.10, 1.40), "Cr": (1.00, 1.30)},
    "C45": {"C": (0.42, 0.50), "Mn": (0.50, 0.80), "Si": (0.10, 0.40)},
    "42CrMo4": {"C": (0.38, 0.45), "Mn": (0.60, 0.90), "Cr": (0.90, 1.20), "Mo": (0.15, 0.30)},
}


def current_employee(request) -> Employee | None:
    if not request.user.is_authenticated:
        return None
    return getattr(request.user, "employee", None)


def log_audit(request, action: str, entity: str, detail: str = "", *, user: str | None = None,
             role: str | None = None, device: str | None = None) -> AuditLog:
    emp = current_employee(request)
    name = user or (emp.name if emp else "System")
    role_label = role or (emp.get_role_display() if emp else "Interlock Engine")
    ip = emp.ip if emp else "—"
    dev = device or (emp.device if emp else "SERVER")
    seed = f"{datetime.now().isoformat()}{action}{entity}{name}"
    return AuditLog.objects.create(
        user=name, role=role_label, action=action, entity=entity,
        detail=detail, ip=ip, device=dev,
        hash=hashlib.sha1(seed.encode()).hexdigest()[:6],
    )


# ---------------------------------------------------------------- inspection
def inspection_blockers(inspection: Inspection) -> list[str]:
    """Every reason approval is impossible right now."""
    blockers: list[str] = []
    if inspection.ctq_failed:
        names = ", ".join(m.name for m in inspection.ctq_failed)
        blockers.append(f"CTQ out of tolerance: {names}. Approve and concession are both locked.")
    if inspection.status != Inspection.Status.PENDING:
        blockers.append("This checklist has already been decided.")
    return blockers


def concession_blockers(inspection: Inspection) -> list[str]:
    blockers: list[str] = []
    if inspection.ctq_failed:
        blockers.append("A CTQ failure can never be conceded — reject the lot to MRB instead.")
    if not inspection.failed:
        blockers.append("Nothing is out of tolerance — approve normally, no concession needed.")
    if inspection.status != Inspection.Status.PENDING:
        blockers.append("This checklist has already been decided.")
    return blockers


def quarantine_lot(request, inspection: Inspection, reason: str, note: str = "") -> Hold:
    wo = inspection.wo
    wo.status = WorkOrder.Status.QUARANTINED
    wo.save(update_fields=["status"])
    hold = Hold.objects.create(
        wo=wo, reason=reason, qty=wo.qty, since=datetime.now().strftime("%H:%M"),
        status="open", inspector=inspection.inspector, op=inspection.op,
        photos=inspection.photos,
    )
    log_audit(request, "Lot quarantined", f"{hold.wo.wo_no} · {wo.part.name}",
              detail=(note or reason)[:160])
    log_audit(request, "Rejection Holding Area", f"{wo.wo_no}", "Moved to QUA holding · MRB required")
    return hold


# ---------------------------------------------------------------- dispatch
def gate_checks(shipment: Shipment) -> list[dict]:
    """Rule a · b · c — computed from live data, never stored as truth."""
    wo = shipment.wo
    ops = list(wo.operations.all())
    ops_done = [o for o in ops if o.status == "done"]
    ops_ok = len(ops_done) == len(ops) and len(ops) > 0

    open_holds = list(wo.holds.filter(status="open"))
    # Every open hold stops the truck; a cure hold names the minutes still to run,
    # a quality hold names the MRB disposition that has to happen first.
    hold_ok = not open_holds
    if hold_ok:
        hold_sub = "No open quality holds on this routing"
    else:
        h = open_holds[0]
        hold_sub = (f"Mandatory cure hold active · {h.dispatch_block_minutes} min remaining"
                    if h.dispatch_block_minutes else
                    f"{h.reason[:70]} — MRB disposition required")

    pdi = wo.inspections.filter(status__in=[Inspection.Status.APPROVED, Inspection.Status.CONCEDED]).first()
    pending = wo.inspections.filter(status=Inspection.Status.PENDING).first()
    pdi_ok = pdi is not None
    if pdi_ok:
        pdi_sub = f"{pdi.template_label} · {'concession ' + (pdi.note[:24] if pdi.note else '') if pdi.status == 'conceded' else 'approved'}"
    elif pending:
        pdi_sub = "Checklist submitted — awaiting Shift Supervisor approval"
    else:
        pdi_sub = "PDI checklist not started"

    return [
        {"ok": ops_ok, "label": "All operations signed off",
         "sub": f"{len(ops_done)} of {len(ops)} traveler operations complete" if not ops_ok else
                f"{len(ops)} of {len(ops)} traveler operations complete"},
        {"ok": hold_ok, "label": "Process hold times satisfied", "sub": hold_sub},
        {"ok": pdi_ok, "label": "Final PDI approved by Quality", "sub": pdi_sub},
    ]


def shipment_is_clear(shipment: Shipment) -> bool:
    return all(c["ok"] for c in gate_checks(shipment))


# ---------------------------------------------------------------- roles
def require_role(request, predicate: str, message: str):
    """Return a redirect when the acting role is not allowed, else None."""
    emp = current_employee(request)
    if emp is None or not getattr(emp, predicate):
        messages.error(request, message)
        return redirect(request.path)
    return None
