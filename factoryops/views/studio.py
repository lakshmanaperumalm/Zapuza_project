"""PDI template studio: revisions, blueprint pins, CTQ flags and release control."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from ..models import RevisionLog, Template, TemplateField
from ..services import current_employee, log_audit

REV_LETTERS = "ABCDEFGHJKLMN"


@login_required
def studio(request):
    templates = Template.objects.all().prefetch_related("fields")
    selected = templates.filter(pk=request.GET.get("tpl")).first() or templates.first()
    ctx = {
        "page_title": "PDI Template Studio",
        "nav_group": "Quality Engineering",
        "active": "studio",
        "templates": templates,
        "tpl": selected,
        "fields": selected.fields.all() if selected else [],
        "kinds": TemplateField.KINDS,
        "can_edit": bool(current_employee(request) and current_employee(request).can_edit_template),
        "can_approve": bool(current_employee(request) and current_employee(request).can_approve_template),
    }
    return render(request, "portal/studio.html", ctx)


@login_required
def new_revision(request, pk):
    tpl = get_object_or_404(Template, pk=pk)
    emp = current_employee(request)
    if request.method != "POST":
        return redirect(f"/portal/studio/?tpl={tpl.pk}")
    if not emp or not emp.can_edit_template:
        messages.error(request, "Only a Quality Engineer or Quality Manager can create a template revision.")
        return redirect(f"/portal/studio/?tpl={tpl.pk}")
    if tpl.status == Template.Status.DRAFT:
        messages.error(request, "This template is already an editable draft.")
        return redirect(f"/portal/studio/?tpl={tpl.pk}")
    letter = REV_LETTERS[min(REV_LETTERS.index(tpl.rev) + 1 if tpl.rev in REV_LETTERS else 0,
                            len(REV_LETTERS) - 1)]
    new = Template.objects.create(
        code=tpl.code, name=tpl.name, part_no=tpl.part_no, status=Template.Status.DRAFT,
        rev=letter, owner=emp.name,
    )
    for f in tpl.fields.all():
        TemplateField.objects.create(
            template=new, seq=f.seq, name=f.name, kind=f.kind, nominal=f.nominal, up=f.up,
            dn=f.dn, unit=f.unit, ctq=f.ctq, pin_x=f.pin_x, pin_y=f.pin_y,
        )
    tpl.status = Template.Status.PENDING  # superseded but kept for history
    tpl.save(update_fields=["status"])
    RevisionLog.objects.create(template=new, rev=letter, note=f"Created from {tpl.code} Rev {tpl.rev} — awaiting Quality Manager approval",
                               user=emp.name)
    log_audit(request, "Template revision created", f"{new.code} Rev {letter}", f"Cloned from Rev {tpl.rev}")
    messages.success(request, f"{new.code} Rev {letter} created as a draft — add pins, then submit for Quality Manager approval.")
    return redirect(f"/portal/studio/?tpl={new.pk}")


@login_required
def add_field(request, pk):
    tpl = get_object_or_404(Template, pk=pk)
    emp = current_employee(request)
    if request.method != "POST":
        return redirect(f"/portal/studio/?tpl={tpl.pk}")
    if not emp or not emp.can_edit_template:
        messages.error(request, "Only a Quality Engineer or Quality Manager can edit a template.")
        return redirect(f"/portal/studio/?tpl={tpl.pk}")
    if not tpl.is_editable:
        messages.error(request, "Released and pending templates are immutable — create a new revision to change this form.")
        return redirect(f"/portal/studio/?tpl={tpl.pk}")
    name = request.POST.get("name", "").strip()
    if not name:
        messages.error(request, "Give the inspection field a name.")
        return redirect(f"/portal/studio/?tpl={tpl.pk}")
    kind = request.POST.get("kind", "dim")
    try:
        nominal = float(request.POST.get("nominal") or 0)
        up = float(request.POST.get("up") or 0)
        dn = float(request.POST.get("dn") or 0)
        pin_x = float(request.POST.get("pin_x") or 50)
        pin_y = float(request.POST.get("pin_y") or 40)
    except ValueError:
        messages.error(request, "Tolerances must be numeric.")
        return redirect(f"/portal/studio/?tpl={tpl.pk}")
    field = TemplateField.objects.create(
        template=tpl, seq=tpl.fields.count() + 1, name=name, kind=kind,
        nominal=nominal, up=up, dn=dn, unit=request.POST.get("unit") or "mm",
        ctq=bool(request.POST.get("ctq")), pin_x=pin_x, pin_y=pin_y,
    )
    log_audit(request, "Template field added", f"{tpl.code} Rev {tpl.rev} · {field.name}",
              f"{kind} · {field.spec_text} {'· CTQ' if field.ctq else ''}")
    messages.success(request, f"Field '{field.name}' added and pinned to the drawing.")
    return redirect(f"/portal/studio/?tpl={tpl.pk}")


@login_required
def delete_field(request, pk, field_id):
    tpl = get_object_or_404(Template, pk=pk)
    field = get_object_or_404(TemplateField, pk=field_id, template=tpl)
    emp = current_employee(request)
    if request.method != "POST":
        return redirect(f"/portal/studio/?tpl={tpl.pk}")
    if not emp or not emp.can_edit_template or not tpl.is_editable:
        messages.error(request, "This form is not editable — released revisions are immutable.")
        return redirect(f"/portal/studio/?tpl={tpl.pk}")
    name = field.name
    field.delete()
    log_audit(request, "Template field removed", f"{tpl.code} Rev {tpl.rev}", name)
    messages.success(request, f"Field '{name}' removed from the draft.")
    return redirect(f"/portal/studio/?tpl={tpl.pk}")


@login_required
def submit_template(request, pk):
    tpl = get_object_or_404(Template, pk=pk)
    emp = current_employee(request)
    if request.method != "POST":
        return redirect(f"/portal/studio/?tpl={tpl.pk}")
    if not emp or not emp.can_edit_template:
        messages.error(request, "Only a Quality Engineer or Quality Manager can submit a revision.")
        return redirect(f"/portal/studio/?tpl={tpl.pk}")
    if tpl.status != Template.Status.DRAFT:
        messages.error(request, "Only a draft can be submitted for approval.")
        return redirect(f"/portal/studio/?tpl={tpl.pk}")
    if not tpl.fields.exists():
        messages.error(request, "At least one inspection field is required before submitting.")
        return redirect(f"/portal/studio/?tpl={tpl.pk}")
    tpl.status = Template.Status.PENDING
    tpl.save(update_fields=["status"])
    RevisionLog.objects.create(template=tpl, rev=tpl.rev, user=emp.name,
                               note=f"Submitted for Quality Manager approval — {tpl.fields.count()} fields, {tpl.ctq_count} CTQ")
    log_audit(request, "Template submitted for approval", f"{tpl.code} Rev {tpl.rev}",
              f"{tpl.fields.count()} fields · {tpl.ctq_count} CTQ")
    messages.success(request, f"{tpl.code} Rev {tpl.rev} submitted — the Quality Manager must approve it before the floor sees it.")
    return redirect(f"/portal/studio/?tpl={tpl.pk}")


@login_required
def approve_template(request, pk):
    tpl = get_object_or_404(Template, pk=pk)
    emp = current_employee(request)
    if request.method != "POST":
        return redirect(f"/portal/studio/?tpl={tpl.pk}")
    if not emp or not emp.can_approve_template:
        messages.error(request, "Only the Quality Manager or Plant Manager can release a template revision.")
        return redirect(f"/portal/studio/?tpl={tpl.pk}")
    if tpl.status != Template.Status.PENDING:
        messages.error(request, "Only a submitted revision can be approved.")
        return redirect(f"/portal/studio/?tpl={tpl.pk}")
    tpl.status = Template.Status.RELEASED
    tpl.approved_by = f"Quality Manager · {timezone.now():%d %b %Y}"
    tpl.approved_at = timezone.now()
    tpl.save(update_fields=["status", "approved_by", "approved_at"])
    RevisionLog.objects.create(template=tpl, rev=tpl.rev, user=emp.name,
                               note=f"Approved and released to shopfloor tablets — {tpl.fields.count()} fields")
    log_audit(request, "Template released", f"{tpl.code} Rev {tpl.rev}",
              "Approved by Quality Manager · now read-only on the floor")
    messages.success(request, f"{tpl.code} Rev {tpl.rev} released — shopfloor tablets now use this revision.")
    return redirect(f"/portal/studio/?tpl={tpl.pk}")


@login_required
def return_template(request, pk):
    tpl = get_object_or_404(Template, pk=pk)
    emp = current_employee(request)
    if request.method != "POST":
        return redirect(f"/portal/studio/?tpl={tpl.pk}")
    if not emp or not emp.can_approve_template:
        messages.error(request, "Only the Quality Manager can return a revision to the engineer.")
        return redirect(f"/portal/studio/?tpl={tpl.pk}")
    if tpl.status != Template.Status.PENDING:
        messages.error(request, "Only a submitted revision can be returned.")
        return redirect(f"/portal/studio/?tpl={tpl.pk}")
    note = request.POST.get("note", "").strip() or "Returned for correction"
    tpl.status = Template.Status.DRAFT
    tpl.save(update_fields=["status"])
    RevisionLog.objects.create(template=tpl, rev=tpl.rev, user=emp.name, note=f"Returned to engineer — {note}")
    log_audit(request, "Template returned", f"{tpl.code} Rev {tpl.rev}", note[:150])
    messages.warning(request, f"{tpl.code} Rev {tpl.rev} returned to the Quality Engineer for correction.")
    return redirect(f"/portal/studio/?tpl={tpl.pk}")
