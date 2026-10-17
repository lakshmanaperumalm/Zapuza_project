"""
Domain model for the Zapuza FactoryOps QC system.

Sections
  1. Core      — identity, master data, audit
  2. Quality   — work orders, travelers, inspections, holds, PDI templates
  3. Intake    — raw material lots, MTC verification, supplier non-conformances
  4. Dispatch  — shipments, gate-pass interlocks
  5. Shopfloor — shift handovers, first-piece approvals, hourly checks
"""
from datetime import date

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


# ---------------------------------------------------------------- core
class Role(models.TextChoices):
    OPERATOR = "operator", "Machine Operator"
    INSPECTOR = "inspector", "QA Floor Inspector"
    SUPERVISOR = "supervisor", "Shift Supervisor"
    ENGINEER = "engineer", "Quality Engineer"
    QM = "qm", "Quality Manager"
    PLANT = "plant", "Plant Manager"


class Employee(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="employee")
    name = models.CharField(max_length=80)
    initials = models.CharField(max_length=4)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.SUPERVISOR)
    device = models.CharField(max_length=20, default="DSK-03")
    ip = models.CharField(max_length=20, default="10.8.1.12")
    shift = models.CharField(max_length=8, default="A")
    online = models.BooleanField(default=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.name} · {self.get_role_display()}"

    @property
    def can_approve_inspection(self):
        return self.role in {Role.SUPERVISOR, Role.PLANT}

    @property
    def can_dispose_hold(self):
        return self.role in {Role.SUPERVISOR, Role.QM, Role.PLANT}

    @property
    def can_release_intake(self):
        return self.role in {Role.ENGINEER, Role.QM, Role.PLANT}

    @property
    def can_edit_template(self):
        return self.role in {Role.ENGINEER, Role.QM}

    @property
    def can_approve_template(self):
        return self.role in {Role.QM, Role.PLANT}


class Machine(models.Model):
    code = models.CharField(max_length=12, unique=True)
    name = models.CharField(max_length=60)
    dept = models.CharField(max_length=40)
    state = models.CharField(max_length=12, default="idle")  # running idle locked down
    job = models.CharField(max_length=20, blank=True)
    part = models.CharField(max_length=60, blank=True)
    op = models.CharField(max_length=60, blank=True)
    progress = models.PositiveIntegerField(default=0)
    pm_status = models.CharField(max_length=10, default="ok")
    cycle = models.CharField(max_length=10, blank=True)
    target = models.CharField(max_length=12, blank=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.name} ({self.code})"


class Gauge(models.Model):
    code = models.CharField(max_length=12, unique=True)
    kind = models.CharField(max_length=40)
    range_text = models.CharField(max_length=24)
    calibrated_on = models.DateField()
    due_on = models.DateField()
    status = models.CharField(max_length=10, default="valid")  # valid expiring expired
    holder = models.CharField(max_length=40)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return self.code

    @property
    def is_expired(self):
        return self.status == "expired" or self.due_on < date.today()


class Heat(models.Model):
    heat_no = models.CharField(max_length=12, unique=True)
    grade = models.CharField(max_length=20)
    supplier = models.CharField(max_length=40)
    mtc_file = models.CharField(max_length=40, blank=True)
    qty_kg = models.PositiveIntegerField(default=0)
    received = models.DateField()
    status = models.CharField(max_length=12, default="released")  # released in-lab quarantine

    class Meta:
        ordering = ["-received"]

    def __str__(self):
        return f"{self.heat_no} · {self.grade}"


class AuditLog(models.Model):
    at = models.DateTimeField(auto_now_add=True)
    user = models.CharField(max_length=60)
    role = models.CharField(max_length=40)
    action = models.CharField(max_length=60)
    entity = models.CharField(max_length=80)
    detail = models.TextField(blank=True)
    ip = models.CharField(max_length=20, default="—")
    device = models.CharField(max_length=20, default="SERVER")
    hash = models.CharField(max_length=12, blank=True)

    class Meta:
        ordering = ["-at", "-id"]
        verbose_name = "audit entry"

    def __str__(self):
        return f"{self.at:%H:%M:%S} {self.user} · {self.action}"


# ---------------------------------------------------------------- quality
class Part(models.Model):
    part_no = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=60)
    customer = models.CharField(max_length=40)

    class Meta:
        ordering = ["part_no"]

    def __str__(self):
        return f"{self.part_no} · {self.name}"


class WorkOrder(models.Model):
    class Status(models.TextChoices):
        IN_PROGRESS = "IN_PROGRESS", "In progress"
        HOLD = "HOLD", "Process hold"
        AWAITING = "AWAITING_APPROVAL", "Awaiting approval"
        QUARANTINED = "QUARANTINED", "Quarantined"
        CONCESSION = "CONCESSION", "Concession"
        READY = "READY_DISPATCH", "Ready to dispatch"
        DISPATCHED = "DISPATCHED", "Dispatched"

    wo_no = models.CharField(max_length=12, unique=True)
    part = models.ForeignKey(Part, on_delete=models.PROTECT, related_name="orders")
    qty = models.PositiveIntegerField()
    heat = models.ForeignKey(Heat, on_delete=models.PROTECT, related_name="orders", null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.IN_PROGRESS)
    priority = models.CharField(max_length=10, default="normal")
    due_text = models.CharField(max_length=30)
    qty_done = models.PositiveIntegerField(default=0)
    qty_scrap = models.PositiveIntegerField(default=0)
    operator = models.CharField(max_length=40, blank=True)
    line = models.CharField(max_length=40, blank=True)
    queue_hours = models.FloatField(default=0.0)

    class Meta:
        ordering = ["wo_no"]

    def __str__(self):
        return f"{self.wo_no} · {self.part.name}"

    @property
    def current_op(self):
        return self.operations.filter(status__in=["active", "hold", "blocked"]).order_by("seq").first()

    @property
    def stage_index(self):
        op = self.current_op
        return op.seq if op else 9

    @property
    def ops_done(self):
        return self.operations.filter(status="done").count()

    @property
    def ops_total(self):
        return self.operations.count()

    @property
    def open_hold(self):
        return self.holds.filter(status="open").first()


class Operation(models.Model):
    wo = models.ForeignKey(WorkOrder, on_delete=models.CASCADE, related_name="operations")
    seq = models.PositiveSmallIntegerField()
    name = models.CharField(max_length=50)
    status = models.CharField(max_length=10, default="pending")  # done active pending hold blocked
    machine = models.CharField(max_length=20, blank=True)
    meta = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["seq"]

    def __str__(self):
        return f"{self.wo.wo_no} Op {self.seq * 10} {self.name}"


class Inspection(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Awaiting supervisor"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        CONCEDED = "conceded", "Concession"

    wo = models.ForeignKey(WorkOrder, on_delete=models.CASCADE, related_name="inspections")
    op = models.CharField(max_length=50)
    template_label = models.CharField(max_length=40, default="PDI-SHAFT Rev C")
    inspector = models.CharField(max_length=40)
    submitted_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.CharField(max_length=40, blank=True)
    note = models.TextField(blank=True)
    photos = models.PositiveSmallIntegerField(default=0)
    shift = models.CharField(max_length=30, default="Shift A")
    line = models.CharField(max_length=40, blank=True)

    class Meta:
        ordering = ["-submitted_at", "-id"]

    def __str__(self):
        return f"{self.wo.wo_no} · {self.op}"

    @property
    def failed(self):
        return [m for m in self.measurements.all() if m.result == "fail"]

    @property
    def ctq_failed(self):
        return [m for m in self.failed if m.ctq]

    @property
    def ctq_note(self):
        if self.ctq_failed:
            return "CTQ failure — approve and concession are both locked"
        if self.failed:
            return f"{len(self.failed)} non-CTQ dimension out · concession eligible"
        return "All parameters in tolerance"


class Measurement(models.Model):
    inspection = models.ForeignKey(Inspection, on_delete=models.CASCADE, related_name="measurements")
    seq = models.PositiveSmallIntegerField(default=1)
    name = models.CharField(max_length=50)
    spec_text = models.CharField(max_length=40)
    nominal = models.FloatField(default=0)
    up = models.FloatField(default=0)
    dn = models.FloatField(default=0)
    is_max = models.BooleanField(default=False)
    value_num = models.FloatField(null=True, blank=True)
    value_text = models.CharField(max_length=12, blank=True)
    unit = models.CharField(max_length=8, default="mm")
    ctq = models.BooleanField(default=False)
    gauge = models.CharField(max_length=20, blank=True)

    class Meta:
        ordering = ["seq", "id"]

    def __str__(self):
        return f"{self.name} · {self.spec_text}"

    @property
    def limits(self):
        if self.is_max:
            return (0.0, self.up)
        return (round(self.nominal + self.dn, 3), round(self.nominal + self.up, 3))

    @property
    def formatted_value(self):
        if self.value_text:
            return self.value_text
        return f"{self.value_num:.3f}" if self.value_num is not None else "—"

    @property
    def result(self):
        if self.value_text:
            return "pass" if self.value_text.upper() in {"PASS", "GO"} else "fail"
        if self.value_num is None:
            return "pending"
        low, high = self.limits
        return "pass" if low <= self.value_num <= high else "fail"


class Hold(models.Model):
    DISPOSITIONS = [
        ("rework", "Rework"),
        ("scrap", "Scrap"),
        ("rtv", "Return to vendor"),
        ("concession", "Customer concession"),
    ]

    wo = models.ForeignKey(WorkOrder, on_delete=models.CASCADE, related_name="holds")
    reason = models.CharField(max_length=140)
    qty = models.PositiveIntegerField(default=0)
    since = models.CharField(max_length=10, default="08:55")
    status = models.CharField(max_length=14, default="open")  # open dispositioned
    inspector = models.CharField(max_length=40, blank=True)
    op = models.CharField(max_length=40, blank=True)
    photos = models.PositiveSmallIntegerField(default=0)
    disposition = models.CharField(max_length=14, blank=True, choices=DISPOSITIONS)
    disposition_note = models.TextField(blank=True)
    disposition_by = models.CharField(max_length=40, blank=True)
    disposition_at = models.DateTimeField(null=True, blank=True)
    dispatch_block_minutes = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-id"]

    def __str__(self):
        return f"{self.wo.wo_no} · {self.reason[:40]}"

    @property
    def is_dispatch_only(self):
        return self.status == "open" and self.dispatch_block_minutes > 0


class Template(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PENDING = "pending", "Awaiting QM approval"
        RELEASED = "released", "Released"

    code = models.CharField(max_length=24, unique=True)
    name = models.CharField(max_length=60)
    part_no = models.CharField(max_length=20)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    rev = models.CharField(max_length=4, default="A")
    owner = models.CharField(max_length=40, default="N. Devi")
    approved_by = models.CharField(max_length=60, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.name} · {self.rev}"

    @property
    def ctq_count(self):
        return self.fields.filter(ctq=True).count()

    @property
    def is_editable(self):
        return self.status == self.Status.DRAFT


class TemplateField(models.Model):
    KINDS = [("dim", "Dimension ±"), ("max", "MAX limit"), ("visual", "Pass / fail")]

    template = models.ForeignKey(Template, on_delete=models.CASCADE, related_name="fields")
    seq = models.PositiveSmallIntegerField(default=1)
    name = models.CharField(max_length=50)
    kind = models.CharField(max_length=8, default="dim")
    nominal = models.FloatField(default=0)
    up = models.FloatField(default=0)
    dn = models.FloatField(default=0)
    unit = models.CharField(max_length=8, default="mm")
    ctq = models.BooleanField(default=False)
    gauge = models.CharField(max_length=20, blank=True)
    pin_x = models.FloatField(default=0)  # % of drawing width
    pin_y = models.FloatField(default=0)

    class Meta:
        ordering = ["seq", "id"]

    def __str__(self):
        return f"{self.name} ({self.template.code})"

    @property
    def spec_text(self):
        if self.kind == "visual":
            return "PASS / FAIL"
        if self.kind == "max":
            return f"{self.up:g} MAX"
        return f"{self.nominal:g} +{self.up:g} / {self.dn:g}"

    @property
    def limits_text(self):
        if self.kind == "visual":
            return "Visual acceptance — PASS / FAIL"
        low = 0.0 if self.kind == "max" else self.nominal + self.dn
        high = self.up if self.kind == "max" else self.nominal + self.up
        return f"Limits {low:.3f} – {high:.3f} {self.unit}".strip()


class RevisionLog(models.Model):
    template = models.ForeignKey(Template, on_delete=models.CASCADE, related_name="revisions")
    rev = models.CharField(max_length=4)
    note = models.CharField(max_length=160)
    user = models.CharField(max_length=40)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.template.code} {self.rev}"


# ---------------------------------------------------------------- intake
class IntakeLot(models.Model):
    class Status(models.TextChoices):
        AWAITING = "awaiting", "Awaiting MTC verification"
        LAB = "lab", "In lab testing"
        RELEASED = "released", "Released to stores"
        QUARANTINED = "quarantined", "Supplier quarantine"

    no = models.CharField(max_length=12, unique=True)
    supplier = models.CharField(max_length=40)
    grade = models.CharField(max_length=20)
    heat_no = models.CharField(max_length=12)
    qty_kg = models.PositiveIntegerField()
    bundles = models.PositiveSmallIntegerField()
    vehicle = models.CharField(max_length=20)
    po = models.CharField(max_length=20)
    mtc_file = models.CharField(max_length=40, blank=True)
    received = models.CharField(max_length=20)
    status = models.CharField(max_length=14, choices=Status.choices, default=Status.AWAITING)
    chemistry_json = models.JSONField(default=dict, blank=True)
    lab_result = models.CharField(max_length=120, blank=True)
    note = models.CharField(max_length=160, blank=True)
    released_at = models.CharField(max_length=10, blank=True)
    released_by = models.CharField(max_length=40, blank=True)
    sncr = models.ForeignKey("SNCR", on_delete=models.SET_NULL, null=True, blank=True, related_name="lots")

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.no} · {self.heat_no}"

    @property
    def chemistry(self):
        """Return spec-checked rows: [(element, actual, spec, ok)]."""
        from .services import GRADE_SPECS
        spec = GRADE_SPECS.get(self.grade, {})
        rows = []
        for el, actual in (self.chemistry_json or {}).items():
            rule = spec.get(el)
            if not rule:
                rows.append((el, actual, "—", True))
                continue
            lo, hi = rule
            ok = lo <= actual <= hi
            rows.append((el, actual, f"{lo:g}–{hi:g}", ok))
        return rows

    @property
    def chemistry_ok(self):
        return all(row[3] for row in self.chemistry)


class SNCR(models.Model):
    no = models.CharField(max_length=12, unique=True)
    supplier = models.CharField(max_length=40)
    heat = models.CharField(max_length=12)
    issue = models.CharField(max_length=160)
    status = models.CharField(max_length=14, default="Open")
    action = models.CharField(max_length=80, blank=True)
    raised_on = models.CharField(max_length=20, blank=True)

    class Meta:
        ordering = ["no"]
        verbose_name = "supplier non-conformance"

    def __str__(self):
        return f"{self.no} · {self.supplier}"


# ---------------------------------------------------------------- dispatch
class Shipment(models.Model):
    no = models.CharField(max_length=12, unique=True)
    wo = models.ForeignKey(WorkOrder, on_delete=models.CASCADE, related_name="shipments")
    customer = models.CharField(max_length=40)
    part_name = models.CharField(max_length=60)
    qty = models.PositiveIntegerField()
    po = models.CharField(max_length=20)
    vehicle = models.CharField(max_length=20)
    crate = models.CharField(max_length=30)
    status = models.CharField(max_length=10, default="locked")  # ready locked shipped

    class Meta:
        ordering = ["no"]

    def __str__(self):
        return f"{self.no} · {self.customer}"


# ---------------------------------------------------------------- shopfloor
class Handover(models.Model):
    shift_from = models.CharField(max_length=20, default="Shift A")
    shift_to = models.CharField(max_length=20, default="Shift B")
    signed_by = models.CharField(max_length=40)
    checks = models.JSONField(default=dict)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.shift_from} → {self.shift_to} · {self.signed_by}"


class FirstPiece(models.Model):
    wo = models.ForeignKey(WorkOrder, on_delete=models.CASCADE, related_name="first_pieces")
    values = models.JSONField(default=dict)
    approved_by = models.CharField(max_length=40)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.wo.wo_no} first piece · {self.approved_by}"


class HourlyCheck(models.Model):
    wo = models.ForeignKey(WorkOrder, on_delete=models.CASCADE, related_name="hourly_checks")
    values = models.JSONField(default=dict)
    passed = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.wo.wo_no} hourly · {'pass' if self.passed else 'fail'}"
