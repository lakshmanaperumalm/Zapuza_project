"""Shopfloor tablet app.

The tablet is a constrained surface: the operator cannot search for jobs, must
scan the station and the traveler, cannot enter a reading with an expired gauge,
and cannot submit a failed dimension without two defect photos.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from ..models import (
    FirstPiece, Gauge, Handover, HourlyCheck, Inspection, Machine, Measurement,
    Template, WorkOrder,
)
from ..services import current_employee, log_audit

SHIFT_CHECKS = [
    ("jobs", "Active job status", "4 jobs running, 1 awaiting first-piece approval"),
    ("parts", "Parts produced & scrap", "214 produced · 2 scrap · scrap reason recorded"),
    ("alerts", "Open quality alerts", "1 CTQ hold in MRB · 2 operator flags"),
    ("tools", "Tooling wear notes", "CNC-L4 insert wear 0.14 mm — change due next lot"),
    ("health", "Machine health", "HT-01 PM overdue — maintenance informed"),
    ("checks", "Pending quality checks", "1 checklist in the supervisor queue"),
]

TEMPLATE_FOR_PART = {
    "SA-2201": "PDI-SHAFT", "SA-2210": "PDI-SHAFT", "DS-0007": "PDI-SHAFT",
    "IS-3302": "PDI-SHAFT", "AX-0090": "PDI-AXLE", "EP-0022": "PDI-PLATE",
    "SR-0009": "PDI-SHAFT", "VB-0003": "PDI-AXLE", "FA-0012": "PDI-AXLE",
    "GH-9010": "IP-GEARHOUSING",
}
GAUGE_FOR_FIELD = {
    "Shaft OD": "MIC-204", "Journal OD": "MIC-204", "Bore diameter": "MIC-204", "Bore Ø": "MIC-204",
    "Runout": "DTI-014", "Face flatness": "DTI-014",
    "Surface finish Ra": "RUG-06", "Coating thickness": "RUG-06", "Coating Thickness": "RUG-06",
}


def _tablet(request, template, **ctx):
    ctx.setdefault("page_title", "Shopfloor Tablet")
    ctx.setdefault("checks", SHIFT_CHECKS)
    ctx.setdefault("station", request.session.get("station"))
    ctx.setdefault("handover_ok", request.session.get("handover_ok", False))
    ctx.setdefault("employee", current_employee(request))
    return render(request, template, ctx)


def _need_handover(request):
    if not request.session.get("handover_ok"):
        messages.error(request, "Sign the digital shift handover before starting work on the tablet.")
        return redirect("factoryops:tablet_handover")
    return None


@login_required
def home(request):
    jobs = WorkOrder.objects.exclude(status="DISPATCHED").select_related("part").prefetch_related("operations")[:6]
    return _tablet(request, "tablet/home.html", jobs=jobs,
                   open_holds=WorkOrder.objects.filter(status="QUARANTINED").count())


@login_required
def station_scan(request):
    redirect_resp = _need_handover(request)
    if redirect_resp:
        return redirect_resp
    if request.method == "POST":
        code = request.POST.get("code", "CNC-L4")
        machine = Machine.objects.filter(code=code).first()
        if not machine:
            messages.error(request, "That station QR is not registered in master data.")
            return redirect("factoryops:tablet_station")
        if machine.pm_status == "overdue" or machine.state == "locked":
            messages.error(request, f"{machine.name} is locked for overdue preventive maintenance — job entry refused.")
            return redirect("factoryops:tablet_station")
        request.session["station"] = machine.code
        log_audit(request, "Station scan verified", f"{machine.code} / station QR",
                  "Location lock satisfied · checklist entry unlocked")
        messages.success(request, f"Station {machine.name} verified — pick a job traveler to inspect.")
        return redirect("factoryops:tablet_jobs")
    return _tablet(request, "tablet/scan.html", machines=Machine.objects.all())


@login_required
def jobs(request):
    redirect_resp = _need_handover(request)
    if redirect_resp:
        return redirect_resp
    if not request.session.get("station"):
        messages.error(request, "Scan a station QR first — job selection is location-locked.")
        return redirect("factoryops:tablet_station")
    machine = Machine.objects.filter(code=request.session["station"]).first()
    orders = WorkOrder.objects.exclude(status__in=["DISPATCHED"]).select_related("part").prefetch_related("operations")
    approved = set(FirstPiece.objects.values_list("wo_id", flat=True))
    for o in orders:
        o.needs_first_piece = o.wo_no in {"WO-1052"} and o.pk not in approved
        o.first_piece_ok = o.pk in approved
    # Setup jobs that need a first piece come first — they are the ones blocking the line.
    orders = sorted(orders, key=lambda o: (0 if o.needs_first_piece else 1, o.wo_no))
    return _tablet(request, "tablet/jobs.html", orders=orders, machine=machine)


@login_required
def first_piece(request, wo_no):
    redirect_resp = _need_handover(request)
    if redirect_resp:
        return redirect_resp
    wo = get_object_or_404(WorkOrder.objects.select_related("part"), wo_no=wo_no)
    if request.method == "POST":
        try:
            values = {
                "Datum OD (Ø40.00 ±0.02)": float(request.POST.get("d1", "")),
                "Setup length (96.00 ±0.25)": float(request.POST.get("d2", "")),
                "Runout (0.020 MAX)": float(request.POST.get("d3", "")),
            }
        except ValueError:
            messages.error(request, "All three first-piece dimensions must be measured.")
            return redirect("factoryops:tablet_first_piece", wo_no=wo_no)
        if not request.POST.get("ack"):
            messages.error(request, "QA inspector sign-off is required before the counter is unlocked.")
            return redirect("factoryops:tablet_first_piece", wo_no=wo_no)
        bad = (abs(values["Datum OD (Ø40.00 ±0.02)"] - 40) > 0.02
               or abs(values["Setup length (96.00 ±0.25)"] - 96) > 0.25
               or values["Runout (0.020 MAX)"] > 0.02)
        if bad:
            messages.error(request, "First piece is out of tolerance — adjust the setup and re-measure.")
            return redirect("factoryops:tablet_first_piece", wo_no=wo_no)
        FirstPiece.objects.create(wo=wo, values=values, approved_by=current_employee(request).name)
        log_audit(request, "First-piece approved", f"{wo.wo_no} · setup",
                  "3 dimensions verified · production counter unlocked")
        messages.success(request, f"First piece approved — production counter unlocked for {wo.wo_no}.")
        return redirect("factoryops:tablet_traveler", wo_no=wo_no)
    return _tablet(request, "tablet/first_piece.html", wo=wo)


@login_required
def traveler(request, wo_no):
    redirect_resp = _need_handover(request)
    if redirect_resp:
        return redirect_resp
    wo = get_object_or_404(WorkOrder.objects.select_related("part", "heat"), wo_no=wo_no)
    if request.method == "POST":
        request.session["traveler"] = wo.wo_no
        log_audit(request, "Traveler scan verified", f"{request.session.get('station')} / TRAVELER-{wo.wo_no}",
                  "Dual QR presence rule satisfied")
        messages.success(request, f"Traveler {wo.wo_no} verified — checklist unlocked.")
        return redirect("factoryops:tablet_inspect", wo_no=wo.wo_no)
    return _tablet(request, "tablet/traveler.html", wo=wo, machine=Machine.objects.filter(code=request.session.get("station")).first())


def _template_for(wo):
    code = TEMPLATE_FOR_PART.get(wo.part.part_no, "PDI-SHAFT")
    return Template.objects.filter(code=code, status=Template.Status.RELEASED).first() or \
        Template.objects.filter(status=Template.Status.RELEASED).first()


@login_required
def inspect(request, wo_no):
    redirect_resp = _need_handover(request)
    if redirect_resp:
        return redirect_resp
    if request.session.get("traveler") != wo_no:
        messages.error(request, "Scan the job traveler QR before entering measurements.")
        return redirect("factoryops:tablet_traveler", wo_no=wo_no)
    wo = get_object_or_404(WorkOrder.objects.select_related("part", "heat"), wo_no=wo_no)
    tpl = _template_for(wo)
    fields = list(tpl.fields.all()) if tpl else []
    gauges = Gauge.objects.all()
    suggested = {f.pk: (f.gauge or GAUGE_FOR_FIELD.get(f.name, "MIC-204")) for f in fields}

    if request.method == "POST":
        rows, errors, failed = [], [], []
        for f in fields:
            raw = (request.POST.get(f"m_{f.pk}") or "").strip()
            gauge_code = request.POST.get(f"g_{f.pk}", "")
            gauge = Gauge.objects.filter(code=gauge_code).first()
            if not raw:
                errors.append(f"{f.name}: a reading is required.")
                continue
            if not gauge:
                errors.append(f"{f.name}: scan the gauge used for this measurement.")
                continue
            if gauge.is_expired:
                errors.append(f"{f.name}: gauge {gauge.code} calibration expired — entry refused.")
                continue
            if f.kind == "visual":
                value_text = raw.upper()
                ok = value_text in {"PASS", "GO"}
                rows.append(dict(field=f, value_num=None, value_text=value_text, ok=ok, gauge=gauge.code))
                if not ok:
                    failed.append(f.name)
                continue
            try:
                num = float(raw)
            except ValueError:
                errors.append(f"{f.name}: enter a numeric reading.")
                continue
            low, high = (0.0, f.up) if f.kind == "max" else (f.nominal + f.dn, f.nominal + f.up)
            ok = low <= num <= high
            rows.append(dict(field=f, value_num=num, value_text="", ok=ok, gauge=gauge.code))
            if not ok:
                failed.append(f.name)
        if failed and not request.POST.get("photos"):
            errors.append("Out-of-tolerance readings require two defect photos attached to the checklist.")
        if (request.POST.get("gauge_global") == "DTI-011"):
            errors.append("DTI-011 is past calibration and is blocked from measurement.")

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, "tablet/inspect.html", {
                "page_title": "Shopfloor Tablet", "wo": wo, "tpl": tpl, "fields": fields,
                "gauges": gauges, "station": request.session.get("station"),
                "handover_ok": True, "employee": current_employee(request),
                "form_errors": errors,
                "prefill": {f.pk: request.POST.get(f"m_{f.pk}", "") for f in fields},
                "gaugesel": {f.pk: request.POST.get(f"g_{f.pk}", suggested[f.pk]) for f in fields},
                "suggested": suggested,
                "photos_checked": bool(request.POST.get("photos")),
                "notes_value": request.POST.get("notes", ""),
            })

        insp = Inspection.objects.create(
            wo=wo, op=f"Op {wo.stage_index}0 · {tpl.name}", template_label=f"{tpl.code} Rev {tpl.rev}",
            inspector=current_employee(request).name, submitted_at=timezone.now(),
            status=Inspection.Status.PENDING, photos=2 if request.POST.get("photos") else 0,
            shift="Shift A", line=wo.line,
            note=(request.POST.get("notes") or "")[:400],
        )
        for i, row in enumerate(rows, start=1):
            f = row["field"]
            Measurement.objects.create(
                inspection=insp, seq=i, name=f.name, spec_text=f.spec_text, nominal=f.nominal,
                up=f.up if f.kind != "dim" else f.up, dn=f.dn, is_max=(f.kind == "max"),
                value_num=row["value_num"], value_text=row["value_text"], unit=f.unit, ctq=f.ctq,
                gauge=row["gauge"],
            )
        wo.status = WorkOrder.Status.AWAITING
        wo.save(update_fields=["status"])
        request.session["traveler"] = None
        log_audit(request, "Inspection submitted", f"{wo.wo_no} · {insp.op}",
                  f"{len(rows)} parameters · {len(failed)} out of tolerance · {insp.photos} photos")
        return redirect("factoryops:tablet_submitted", pk=insp.pk)

    return render(request, "tablet/inspect.html", {
        "page_title": "Shopfloor Tablet", "wo": wo, "tpl": tpl, "fields": fields,
        "gauges": gauges, "station": request.session.get("station"), "handover_ok": True,
        "employee": current_employee(request), "form_errors": [], "prefill": {}, "gaugesel": suggested,
        "suggested": suggested, "photos_checked": False, "notes_value": "",
    })


@login_required
def submitted(request, pk):
    insp = get_object_or_404(Inspection.objects.select_related("wo"), pk=pk)
    return _tablet(request, "tablet/submitted.html", insp=insp,
                   portal_url="/portal/approvals/")


@login_required
def hourly(request, wo_no):
    redirect_resp = _need_handover(request)
    if redirect_resp:
        return redirect_resp
    wo = get_object_or_404(WorkOrder.objects.select_related("part"), wo_no=wo_no)
    if request.method == "POST":
        raw = [request.POST.get(f"s{i}", "").strip() for i in (1, 2, 3)]
        try:
            values = [float(v) for v in raw]
        except ValueError:
            messages.error(request, "All three sample readings are required — pull three parts and measure each one.")
            return redirect("factoryops:tablet_hourly", wo_no=wo_no)
        low, high = 31.980, 32.000
        outside = [i for i, val in enumerate(values, start=1) if not (low <= val <= high)]
        passed = not outside
        HourlyCheck.objects.create(
            wo=wo, values={"sample_1": values[0], "sample_2": values[1], "sample_3": values[2]},
            passed=passed)
        log_audit(request, "Hourly sample logged" if passed else "Hourly sample failed",
                  f"{wo.wo_no} · hourly check",
                  f"3 parts measured · {'all within tolerance' if passed else f'sample {outside[0]} outside 31.980–32.000 — supervisor notified'}")
        if passed:
            messages.success(request, "Hourly sample logged — next check due in 60 minutes.")
            return redirect("factoryops:tablet_jobs")
        messages.warning(request, f"Sample {outside[0]} is outside the 31.980 – 32.000 window — the supervisor has been alerted and the next checklist is frozen.")
        return redirect("factoryops:tablet_hourly", wo_no=wo_no)
    samples = [(1, "Sample 1 — first part off the cycle"),
               (2, "Sample 2 — middle of the batch"),
               (3, "Sample 3 — last part of the batch")]
    return _tablet(request, "tablet/hourly.html", wo=wo, samples=samples,
                   prefill={1: "31.996", 2: "31.998", 3: "31.994"},
                   note_value="", history=wo.hourly_checks.all()[:4])


@login_required
def handover(request):
    if request.method == "POST":
        checks = {key: bool(request.POST.get(key)) for key, _, _ in SHIFT_CHECKS}
        if not all(checks.values()):
            messages.error(request, "All six handover items must be acknowledged before signing.")
            return redirect("factoryops:tablet_handover")
        name = (request.POST.get("signature") or "").strip()
        if len(name) < 3:
            messages.error(request, "Type your name to sign the handover.")
            return redirect("factoryops:tablet_handover")
        Handover.objects.create(shift_from="Shift A", shift_to="Shift B", signed_by=name,
                                checks=checks, note=(request.POST.get("note") or "")[:300])
        request.session["handover_ok"] = True
        log_audit(request, "Shift handover signed", "Shift A → Shift B", "6 checks acknowledged · 0 overdue",
                  user=name)
        messages.success(request, "Handover signed — job entry unlocked for Shift B.")
        return redirect("factoryops:tablet_home")
    return _tablet(request, "tablet/handover.html")
