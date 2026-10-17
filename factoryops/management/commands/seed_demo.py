"""Recreate the full demo factory. Idempotent: wipes and re-seeds.

    python manage.py seed_demo
"""
from datetime import date, datetime, timedelta

from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand
from django.utils import timezone

from factoryops.models import (
    AuditLog, Employee, FirstPiece, Gauge, Handover, Heat, Hold, HourlyCheck,
    Inspection, IntakeLot, Machine, Measurement, Operation, Part, RevisionLog,
    Role, SNCR, Shipment, Template, TemplateField, WorkOrder,
)

DEMO_PASSWORD = "zapuza"

GAUGE_FOR_NAME = {
    "Shaft OD": "MIC-204", "Journal OD": "MIC-204", "Bore diameter": "MIC-204",
    "Bore Ø": "MIC-204", "Runout": "DTI-014", "Face flatness": "DTI-014",
    "Surface finish Ra": "RUG-06", "Coating thickness": "RUG-06",
    "Coating Thickness": "RUG-06", "KV coil diam": "VC-118",
}

PEOPLE = [
    # username, name, initials, role, device, ip
    ("sravi", "S. Ravi", "SR", Role.SUPERVISOR, "DSK-03", "10.8.1.12"),
    ("rkarthik", "R. Karthik", "RK", Role.INSPECTOR, "TAB-07", "10.8.2.41"),
    ("ndevi", "N. Devi", "ND", Role.ENGINEER, "DSK-08", "10.8.1.24"),
    ("amurugan", "A. Murugan", "AM", Role.OPERATOR, "TAB-07", "10.8.3.19"),
    ("kvel", "K. Vel", "KV", Role.OPERATOR, "TAB-09", "10.8.3.27"),
    ("pmanager", "P. Anandan", "PA", Role.PLANT, "DSK-01", "10.8.1.4"),
    ("qmanager", "V. Sundaram", "VS", Role.QM, "DSK-05", "10.8.1.9"),
]

OPS = [
    "Raw Material Sawing", "CNC Rough Turning", "CNC Finish Turning", "Heat Treatment",
    "Precision Grinding", "Surface Coating", "Final Assembly", "Final PDI & Wash", "Packing",
]

MACHINES = [
    ("CNC-L4", "CNC Lathe #04", "Machining Shop", "running", "WO-1042", "Shaft Spindle A1", "Op 20 CNC Rough Turning", 68, "ok", "04:12", "12,400"),
    ("CNC-L5", "CNC Lathe #05", "Machining Shop", "idle", "", "Awaiting job", "", 0, "ok", "", ""),
    ("VMC-02", "VMC Station #02", "Machining Shop", "running", "WO-1044", "Gear Housing G2", "Op 20 CNC Rough Turning", 41, "ok", "08:35", "9,800"),
    ("VMC-03", "VMC Station #03", "Machining Shop", "idle", "", "Awaiting job", "", 0, "ok", "", ""),
    ("HT-01", "Heat Treat Oven #01", "Heat Treatment Bay", "locked", "LOCKED", "PM checklist overdue", "Job selection disabled", 0, "overdue", "", ""),
    ("HT-02", "Heat Treat Oven #02", "Heat Treatment Bay", "running", "WO-1039", "Pinion Set PN-4471", "Op 40 Cooling hold", 88, "ok", "—", "—"),
    ("GRD-01", "Surface Grinder #01", "Grinding Bay", "running", "WO-1041", "Bearing Housing BH-88", "Op 50 Precision Grinding", 54, "ok", "06:18", "5,600"),
    ("ASM-01", "Assembly Cell #01", "Final Assembly", "idle", "", "Awaiting job", "", 0, "ok", "", ""),
    ("CT-01", "Surface Coating Line", "Finishing Bay", "down", "FAULT", "Rectifier fault — maintenance", "", 0, "ok", "", ""),
    ("CMM-01", "CMM Inspection Cell", "Quality Lab", "running", "WO-1041", "Bearing Housing BH-88", "Dimensional verification", 100, "ok", "11:02", "1,900"),
    ("SAW-01", "Power Saw #01", "Raw Material Store", "running", "WO-1046", "Coupling Hub CH-15", "Op 10 Raw Material Sawing", 23, "ok", "02:44", "18,200"),
    ("PCK-01", "Packing Bay", "Dispatch", "idle", "", "", "", 0, "ok", "", ""),
]

GAUGES = [
    ("VC-104", "Vernier Caliper", "0–150 mm", date(2026, 1, 12), date(2027, 1, 12), "valid", "Tool Crib A"),
    ("MIC-204", "Micrometer", "25–50 mm", date(2026, 6, 3), date(2026, 12, 3), "valid", "Tool Crib A"),
    ("DTI-011", "Dial Test Indicator", "0.01 mm", date(2025, 9, 20), date(2026, 9, 20), "expired", "Grinding Bay"),
    ("DTI-014", "Dial Test Indicator", "0.001 mm", date(2026, 10, 2), date(2027, 10, 2), "valid", "Tool Crib B"),
    ("PG-04", "Thread Plug Gauge M24×2", "6g", date(2026, 8, 15), date(2027, 2, 15), "valid", "Final PDI"),
    ("RUG-06", "Surface Roughness Tester", "Ra 0.05–10", date(2026, 7, 28), date(2027, 7, 28), "valid", "Quality Lab"),
    ("CMM-01", "CMM Machine (Zeiss)", "500×700×500", date(2026, 4, 1), date(2027, 4, 1), "valid", "Quality Lab"),
    ("PG-09", "Thread Ring Gauge M18", "6g", date(2025, 11, 5), date(2026, 11, 5), "expiring", "Tool Crib B"),
    ("VC-118", "Vernier Caliper", "0–200 mm", date(2025, 8, 18), date(2026, 8, 18), "expired", "Machining Line #2"),
]

HEATS = [
    ("H-8042", "EN8D", "JSW Steel", "MTC-8042-JSW.pdf", 2400, date(2026, 10, 12), "released"),
    ("H-7710", "20MnCr5", "Kalyani Steels", "MTC-7710-KS.pdf", 1800, date(2026, 10, 8), "released"),
    ("H-7621", "EN8D", "JSW Steel", "MTC-7621-JSW.pdf", 900, date(2026, 10, 5), "released"),
    ("H-7903", "EN19", "Mukand Ltd", "MTC-7903-MK.pdf", 1200, date(2026, 10, 9), "released"),
    ("H-7998", "C45", "JSW Steel", "MTC-7998-JSW.pdf", 3100, date(2026, 10, 11), "in-lab"),
    ("H-7734", "EN19", "Kalyani Steels", "MTC-7734-KS.pdf", 750, date(2026, 10, 7), "released"),
    ("H-8056", "42CrMo4", "Mukand Ltd", "MTC-8056-MK.pdf", 1600, date(2026, 10, 13), "released"),
    ("H-7588", "EN8D", "JSW Steel", "MTC-7588-JSW.pdf", 2200, date(2026, 10, 1), "released"),
    ("H-7502", "C45", "Sunrise Metals", "MTC-7502-SM.pdf", 1000, date(2026, 9, 28), "released"),
    ("H-7802", "42CrMo4", "Kalyani Steels", "MTC-7802-KS.pdf", 1500, date(2026, 10, 10), "released"),
    ("H-7844", "EN19", "Mukand Ltd", "MTC-7844-MK.pdf", 800, date(2026, 10, 9), "released"),
    ("H-8011", "EN8D", "JSW Steel", "MTC-8011-JSW.pdf", 2600, date(2026, 10, 12), "released"),
]

PARTS = [
    ("SA-2201", "Shaft Spindle A1", "RK Auto Components"),
    ("PN-4471", "Pinion Set PN-4471", "Gearworks Ltd"),
    ("BH-0088", "Bearing Housing BH-88", "Nord Drives"),
    ("GH-9010", "Gear Housing G2", "Mahindra & Mahindra"),
    ("CH-0015", "Coupling Hub CH-15", "Ashok Leyland"),
    ("IS-3302", "Input Shaft IS-3302", "RK Auto Components"),
    ("EP-0022", "End Plate EP-22", "Sundaram Fasteners"),
    ("FA-0012", "Flange Adapter FA-12", "Tata Motors"),
    ("DS-0007", "Drive Sleeve DS-7", "ZF India"),
    ("SR-0009", "Spacer Ring SR-9", "Bosch India"),
    ("VB-0003", "Valve Body VB-3", "Cummins India"),
    ("AX-0090", "Stub Axle AX-90", "Tata Motors"),
    ("RC-0004", "Retainer Cap RC-4", "Bosch India"),
    ("PS-0011", "Pinion Shaft PS-11", "Gearworks Ltd"),
    ("SA-2210", "Shaft Spindle A1", "RK Auto Components"),
]

# wo, part, qty, heat, status, priority, due, done, scrap, operator, line, ops_done, active_status, queue_h
JOBS = [
    ("WO-1042", "SA-2201", 120, "H-8042", "IN_PROGRESS", "high", "Today, 18:00", 68, 1, "A. Murugan", "Machining Line #1", 4, "active", 0.3),
    ("WO-1039", "PN-4471", 250, "H-7710", "HOLD", "normal", "20 Oct 2026", 250, 0, "M. Prakash", "Heat Treatment", 3, "hold", 5.4),
    ("WO-1041", "BH-0088", 40, "H-7621", "IN_PROGRESS", "normal", "19 Oct 2026", 22, 0, "S. Ravi", "Grinding Bay", 4, "active", 1.8),
    ("WO-1044", "GH-9010", 60, "H-8011", "IN_PROGRESS", "normal", "22 Oct 2026", 24, 2, "K. Vel", "Machining Line #1", 1, "active", 2.6),
    ("WO-1046", "CH-0015", 300, "H-7998", "IN_PROGRESS", "normal", "24 Oct 2026", 69, 0, "J. Selvam", "Raw Material Store", 0, "active", 1.2),
    ("WO-1049", "IS-3302", 80, "H-8042", "AWAITING_APPROVAL", "high", "18 Oct 2026", 80, 0, "A. Murugan", "Final PDI", 7, "active", 0.6),
    ("WO-1051", "EP-0022", 150, "H-7903", "QUARANTINED", "critical", "19 Oct 2026", 150, 0, "R. Karthik", "Quality Hold", 7, "blocked", 4.6),
    ("WO-1045", "FA-0012", 500, "H-7655", "CONCESSION", "normal", "21 Oct 2026", 500, 3, "S. Ravi", "Packing", 9, "pending", 3.1),
    ("WO-1052", "DS-0007", 220, "H-7802", "IN_PROGRESS", "normal", "23 Oct 2026", 118, 0, "K. Vel", "Machining Line #2", 2, "active", 0.4),
    ("WO-1038", "SR-0009", 1000, "H-7588", "READY_DISPATCH", "high", "18 Oct 2026", 1000, 2, "M. Prakash", "Dispatch Staging", 9, "pending", 0.0),
    ("WO-1050", "VB-0003", 45, "H-7734", "IN_PROGRESS", "normal", "20 Oct 2026", 31, 0, "J. Selvam", "Assembly", 5, "active", 3.4),
    ("WO-1053", "AX-0090", 160, "H-8056", "IN_PROGRESS", "normal", "25 Oct 2026", 140, 1, "A. Murugan", "Finishing Bay", 5, "active", 6.2),
    ("WO-1054", "RC-0004", 900, "H-7502", "DISPATCHED", "normal", "16 Oct 2026", 900, 4, "S. Ravi", "Dispatched", 9, "pending", 0.0),
    ("WO-1047", "PS-0011", 200, "H-7844", "IN_PROGRESS", "low", "26 Oct 2026", 64, 0, "K. Vel", "Machining Line #2", 5, "active", 0.9),
]


def ops_for(done_idx: int, active_status: str = "active"):
    """Build the 9-operation ladder."""
    rows = []
    for i, name in enumerate(OPS):
        if i < done_idx:
            status = "done"
        elif i == done_idx:
            status = active_status
        else:
            status = "pending"
        rows.append((i, name, status))
    return rows


class Command(BaseCommand):
    help = "Reset and seed the Zapuza FactoryOps demo factory"

    def handle(self, *args, **options):
        self.stdout.write("Clearing existing demo data…")
        for model in (Measurement, Inspection, Hold, Operation, Shipment, WorkOrder, Part, FirstPiece,
                      HourlyCheck, Handover, TemplateField, Template, RevisionLog, IntakeLot, SNCR,
                      AuditLog, Gauge, Heat, Machine, Employee):
            model.objects.all().delete()
        User.objects.filter(username__in=[p[0] for p in PEOPLE]).delete()
        Group.objects.all().delete()

        # ---- people & roles
        groups = {}
        for value, label in Role.choices:
            groups[value] = Group.objects.create(name=label)
        for username, name, initials, role, device, ip in PEOPLE:
            user = User.objects.create_user(username=username, password=DEMO_PASSWORD,
                                            first_name=name.split(" ")[-1], last_name=name.split(" ")[0])
            user.groups.add(groups[role])
            Employee.objects.create(user=user, name=name, initials=initials, role=role, device=device, ip=ip)

        # ---- master data
        for code, name, dept, state, job, part, op, progress, pm, cycle, target in MACHINES:
            Machine.objects.create(code=code, name=name, dept=dept, state=state, job=job,
                                   part=part, op=op, progress=progress, pm_status=pm,
                                   cycle=cycle, target=target)
        for code, kind, rng, cal, due, status, holder in GAUGES:
            Gauge.objects.create(code=code, kind=kind, range_text=rng, calibrated_on=cal,
                                 due_on=due, status=status, holder=holder)
        heats = {}
        for heat_no, grade, supplier, mtc, qty, received, status in HEATS:
            heats[heat_no] = Heat.objects.create(heat_no=heat_no, grade=grade, supplier=supplier,
                                                 mtc_file=mtc, qty_kg=qty, received=received, status=status)
        parts = {}
        for part_no, name, customer in PARTS:
            parts[part_no] = Part.objects.create(part_no=part_no, name=name, customer=customer)

        # ---- work orders + traveler ladders
        for (wo_no, part_no, qty, heat_no, status, priority, due, done, scrap,
             operator, line, done_idx, active_status, queue_h) in JOBS:
            wo = WorkOrder.objects.create(
                wo_no=wo_no, part=parts[part_no], qty=qty, heat=heats.get(heat_no), status=status,
                priority=priority, due_text=due, qty_done=done, qty_scrap=scrap, operator=operator,
                line=line, queue_hours=queue_h,
            )
            machine_for = {1: "CNC-L4", 2: "CNC-L4", 3: "HT-02", 4: "GRD-01", 5: "CT-01", 8: "PCK-01"}
            for seq, name, op_status in ops_for(done_idx, active_status):
                Operation.objects.create(wo=wo, seq=seq, name=name, status=op_status,
                                         machine=machine_for.get(seq, ""),
                                         meta="")
            # a little realism on the current / completed steps
            if wo_no == "WO-1042":
                wo.operations.filter(seq=3).update(meta="Completed 08:12 · hold 4h satisfied")
                wo.operations.filter(seq=4).update(meta="Op running 00:42:18 · cycle 04:12")
            if wo_no == "WO-1039":
                wo.operations.filter(seq=3).update(meta="Cooling hold active · 01:22:14 remaining")
            if wo_no == "WO-1049":
                wo.operations.filter(seq=7).update(meta="Checklist submitted 09:42 · awaiting supervisor")
            if wo_no == "WO-1051":
                wo.operations.filter(seq=7).update(meta="CTQ out-of-tolerance · quarantined 08:55")
            if wo_no == "WO-1045":
                wo.operations.filter(seq=7).update(meta="Concession CC-0114 · non-CTQ · approved")
                wo.operations.filter(seq=8).update(meta="Packing in progress")
            if wo_no == "WO-1052":
                wo.operations.filter(seq=2).update(meta="First-piece approval pending")

        # ---- inspections
        def add_measurements(insp, rows):
            for i, (name, spec, nominal, up, dn, is_max, value_num, value_text, ctq, unit) in enumerate(rows, start=1):
                Measurement.objects.create(
                    inspection=insp, seq=i, name=name, spec_text=spec, nominal=nominal, up=up, dn=dn,
                    is_max=is_max, value_num=value_num, value_text=value_text, ctq=ctq, unit=unit,
                    gauge=GAUGE_FOR_NAME.get(name, "MIC-204"),
                )

        ap1 = Inspection.objects.create(
            wo=WorkOrder.objects.get(wo_no="WO-1049"), op="Op 80 Final PDI & Wash",
            template_label="PDI-SHAFT Rev C", inspector="R. Karthik",
            submitted_at=timezone.make_aware(datetime(2026, 10, 17, 9, 42)),
            status="pending", photos=2, line="Final PDI",
        )
        add_measurements(ap1, [
            ("Shaft OD", "Ø32.00 +0.00 / −0.02", 32.0, 0.0, -0.02, False, 32.006, "", True, "mm"),
            ("Overall Length", "118.50 ±0.30", 118.5, 0.30, -0.30, False, 118.42, "", False, "mm"),
            ("Thread M24 × 2 − 6g", "GO / NO-GO", 0, 0, 0, False, None, "GO", True, ""),
            ("Runout", "0.020 MAX", 0, 0.020, 0, True, 0.018, "", True, "mm"),
            ("Surface Finish Ra", "0.8 MAX", 0, 0.8, 0, True, 0.74, "", False, "µm"),
            ("End Chamfer", "1.50 ±0.20", 1.5, 0.20, -0.20, False, 1.68, "", False, "mm"),
        ])
        ap2 = Inspection.objects.create(
            wo=WorkOrder.objects.get(wo_no="WO-1053"), op="Op 60 Surface Coating",
            template_label="PDI-AXLE Rev B", inspector="R. Karthik",
            submitted_at=timezone.make_aware(datetime(2026, 10, 17, 10, 5)),
            status="pending", photos=0, line="Finishing Bay",
        )
        add_measurements(ap2, [
            ("Journal OD", "Ø45.00 ±0.015", 45.0, 0.015, -0.015, False, 45.006, "", True, "mm"),
            ("Length", "210.0 ±0.5", 210.0, 0.5, -0.5, False, 210.22, "", False, "mm"),
            ("Coating Thickness", "18 µm ±3", 18.0, 3.0, -3.0, False, 17.4, "", False, "µm"),
            ("Visual — no runs / sags", "PASS / FAIL", 0, 0, 0, False, None, "PASS", False, ""),
        ])
        ap3 = Inspection.objects.create(
            wo=WorkOrder.objects.get(wo_no="WO-1051"), op="Op 80 Final PDI & Wash",
            template_label="PDI-PLATE Rev A", inspector="R. Karthik",
            submitted_at=timezone.make_aware(datetime(2026, 10, 17, 8, 47)),
            status="rejected", photos=2, line="Final PDI",
            decided_at=timezone.make_aware(datetime(2026, 10, 17, 8, 55)), decided_by="S. Ravi",
            note="CTQ failure — escalated to MRB",
        )
        add_measurements(ap3, [
            ("Bore Diameter", "Ø60.00 +0.020 / −0.000", 60.0, 0.020, 0.0, False, 60.048, "", True, "mm"),
            ("Flatness", "0.05 MAX", 0, 0.05, 0, True, 0.032, "", False, "mm"),
            ("Thickness", "12.00 ±0.10", 12.0, 0.10, -0.10, False, 11.96, "", False, "mm"),
        ])

        # historic PDI approvals that let two shipments clear (or clear-but-held)
        ap4 = Inspection.objects.create(
            wo=WorkOrder.objects.get(wo_no="WO-1038"), op="Op 80 Final PDI & Wash",
            template_label="PDI-RING Rev B", inspector="R. Karthik",
            submitted_at=timezone.make_aware(datetime(2026, 10, 16, 15, 40)),
            status="approved", photos=1, line="Dispatch Staging",
            decided_at=timezone.make_aware(datetime(2026, 10, 16, 16, 5)), decided_by="S. Ravi",
        )
        add_measurements(ap4, [
            ("Ring OD", "Ø90.00 ±0.02", 90.0, 0.02, -0.02, False, 90.004, "", True, "mm"),
            ("Thickness", "6.00 ±0.05", 6.0, 0.05, -0.05, False, 5.99, "", False, "mm"),
            ("Visual — no burrs", "PASS / FAIL", 0, 0, 0, False, None, "PASS", False, ""),
        ])
        ap5 = Inspection.objects.create(
            wo=WorkOrder.objects.get(wo_no="WO-1045"), op="Op 80 Final PDI & Wash",
            template_label="PDI-FLANGE Rev B", inspector="R. Karthik",
            submitted_at=timezone.make_aware(datetime(2026, 10, 17, 9, 52)),
            status="conceded", photos=2, line="Packing",
            decided_at=timezone.make_aware(datetime(2026, 10, 17, 9, 58)), decided_by="S. Ravi",
            note="CC-0114 · visual acceptance agreed with customer · non-CTQ dimension",
        )
        add_measurements(ap5, [
            ("Flange OD", "Ø140.00 ±0.10", 140.0, 0.1, -0.1, False, 140.14, "", False, "mm"),
            ("Bolt circle", "Ø110.00 ±0.05", 110.0, 0.05, -0.05, False, 110.01, "", True, "mm"),
            ("Coating thickness", "18 µm ±3", 18.0, 3.0, -3.0, False, 17.8, "", False, "µm"),
        ])

        # ---- hold (from the rejected lot) + a dispatch-only cure hold
        Hold.objects.create(
            wo=WorkOrder.objects.get(wo_no="WO-1051"), reason="CTQ bore Ø60.048 exceeds upper limit +0.020",
            qty=150, since="08:55", status="open", inspector="R. Karthik",
            op="Op 80 Final PDI", photos=2,
        )
        Hold.objects.create(
            wo=WorkOrder.objects.get(wo_no="WO-1045"), reason="Post-coating cure hold — 2h mandatory",
            qty=500, since="10:12", status="open", inspector="S. Ravi", op="Op 60 Surface Coating",
            photos=0, dispatch_block_minutes=38,
        )
        Hold.objects.create(
            wo=WorkOrder.objects.get(wo_no="WO-1047"), reason="Bore Ø38.012 over upper limit +0.010",
            qty=60, since="07:40", status="dispositioned", inspector="R. Karthik",
            op="Op 50 Precision Grinding", photos=2, disposition="rework",
            disposition_note="Ground 0.02 mm under and re-inspected 100% — 60 pcs accepted for assembly.",
            disposition_by="S. Ravi", disposition_at=timezone.make_aware(datetime(2026, 10, 17, 8, 25)),
        )

        # ---- in-process samples and first piece history
        hc1 = HourlyCheck.objects.create(wo=WorkOrder.objects.get(wo_no="WO-1052"),
                                         values={"sample_1": 31.994, "sample_2": 31.998, "sample_3": 31.996},
                                         passed=True)
        HourlyCheck.objects.filter(pk=hc1.pk).update(created_at=timezone.now() - timedelta(hours=2))
        FirstPiece.objects.create(wo=WorkOrder.objects.get(wo_no="WO-1042"),
                                  values={"Datum OD (Ø40.00 ±0.02)": 40.004, "Setup length (96.00 ±0.25)": 96.02,
                                          "Runout (0.020 MAX)": 0.008},
                                  approved_by="R. Karthik")

        # ---- shipments
        Shipment.objects.create(no="SHIP-2288", wo=WorkOrder.objects.get(wo_no="WO-1038"),
                                customer="Bosch India", part_name="Spacer Ring SR-9", qty=1000,
                                po="PO-88213", vehicle="TN 59 AB 4471", crate="CR-0098 — CR-0102", status="ready")
        Shipment.objects.create(no="SHIP-2290", wo=WorkOrder.objects.get(wo_no="WO-1050"),
                                customer="Cummins India", part_name="Valve Body VB-3", qty=45,
                                po="PO-88167", vehicle="TN 72 CD 8810", crate="CR-0103", status="locked")
        Shipment.objects.create(no="SHIP-2291", wo=WorkOrder.objects.get(wo_no="WO-1045"),
                                customer="Tata Motors", part_name="Flange Adapter FA-12", qty=500,
                                po="PO-87990", vehicle="TN 59 EF 1204", crate="CR-0104 — CR-0106", status="locked")
        Shipment.objects.create(no="SHIP-2292", wo=WorkOrder.objects.get(wo_no="WO-1049"),
                                customer="RK Auto Components", part_name="Input Shaft IS-3302", qty=80,
                                po="PO-88330", vehicle="Unassigned", crate="CR-0107", status="locked")

        # ---- PDI templates
        def tpl(code, name, part_no, status, rev, owner, approved_by, fields, revisions):
            t = Template.objects.create(code=code, name=name, part_no=part_no, status=status,
                                        rev=rev, owner=owner, approved_by=approved_by,
                                        approved_at=timezone.now() if approved_by else None)
            for i, f in enumerate(fields, start=1):
                f.setdefault("gauge", GAUGE_FOR_NAME.get(f["name"], "MIC-204"))
                TemplateField.objects.create(template=t, seq=i, **f)
            for rrev, note, user, when in revisions:
                RevisionLog.objects.create(template=t, rev=rrev, note=note, user=user, created_at=when)
            return t

        shaft_fields = [
            dict(name="Shaft OD", kind="dim", nominal=32, up=0.0, dn=-0.02, ctq=True, pin_x=54, pin_y=22, unit="mm"),
            dict(name="Shoulder length", kind="dim", nominal=118.5, up=0.3, dn=-0.3, ctq=True, pin_x=40, pin_y=66, unit="mm"),
            dict(name="Runout", kind="max", nominal=0, up=0.02, ctq=True, pin_x=78, pin_y=44, unit="mm"),
            dict(name="Surface finish Ra", kind="max", nominal=0, up=0.8, ctq=False, pin_x=22, pin_y=50, unit="µm"),
            dict(name="End chamfer", kind="dim", nominal=1.5, up=0.2, dn=-0.2, ctq=False, pin_x=86, pin_y=62, unit="mm"),
            dict(name="Thread M24 × 2 − 6g", kind="visual", ctq=False, pin_x=64, pin_y=30),
        ]
        tpl("PDI-SHAFT", "PDI — Shaft Spindle A1", "SA-2201", "released", "C", "N. Devi",
            "Quality Manager · 02 Sep 2026", shaft_fields, [
                ("C", "Blueprint pin 6 added for thread gauge", "Quality Manager", timezone.now() - timedelta(days=45)),
                ("B", "CTQ flags added to OD and runout after customer PPAP feedback", "Quality Manager", timezone.now() - timedelta(days=123)),
                ("A", "Initial release with 4 dimensions", "Quality Manager", timezone.now() - timedelta(days=278)),
            ])
        tpl("PDI-AXLE", "PDI — Stub Axle AX-90", "AX-0090", "released", "B", "N. Devi",
            "Quality Manager · 14 Aug 2026", [
                dict(name="Journal OD", kind="dim", nominal=45, up=0.015, dn=-0.015, ctq=True, pin_x=50, pin_y=28),
                dict(name="Length", kind="dim", nominal=210, up=0.5, dn=-0.5, ctq=False, pin_x=38, pin_y=62),
                dict(name="Coating thickness", kind="dim", nominal=18, up=3, dn=-3, ctq=False, pin_x=66, pin_y=52, unit="µm"),
                dict(name="Visual — no runs / sags", kind="visual", ctq=False, pin_x=24, pin_y=44),
            ], [("B", "Coating thickness tolerance tightened", "Quality Manager", timezone.now() - timedelta(days=64))])
        tpl("IP-GEARHOUSING", "In-Process — Gear Housing G2", "GH-9010", "draft", "A", "N. Devi", "", [
            dict(name="Bore Ø", kind="dim", nominal=62, up=0.02, dn=0, ctq=True, pin_x=52, pin_y=34),
            dict(name="Face flatness", kind="max", nominal=0, up=0.05, ctq=False, pin_x=30, pin_y=58),
            dict(name="Mounting hole pitch", kind="dim", nominal=96, up=0.1, dn=-0.1, ctq=True, pin_x=70, pin_y=66),
            dict(name="Wall thickness", kind="dim", nominal=9, up=0.3, dn=-0.3, ctq=False, pin_x=46, pin_y=48),
        ], [("A", "Draft created for Gear Housing G2", "N. Devi", timezone.now() - timedelta(days=2))])
        tpl("PDI-PLATE", "PDI — End Plate EP-22", "EP-0022", "released", "A", "N. Devi",
            "Quality Manager · 21 Jul 2026", [
                dict(name="Bore diameter", kind="dim", nominal=60, up=0.02, dn=0, ctq=True, pin_x=50, pin_y=40),
                dict(name="Flatness", kind="max", nominal=0, up=0.05, ctq=False, pin_x=32, pin_y=60),
                dict(name="Thickness", kind="dim", nominal=12, up=0.1, dn=-0.1, ctq=False, pin_x=68, pin_y=30),
            ], [("A", "Initial release", "Quality Manager", timezone.now() - timedelta(days=88))])
        tpl("FP-FIRSTPIECE", "First-Piece — CNC Turning Family", "All turned parts", "released", "D", "N. Devi",
            "Quality Manager · 30 Sep 2026", [
                dict(name="Datum OD", kind="dim", nominal=40, up=0.02, dn=-0.02, ctq=True, pin_x=48, pin_y=26),
                dict(name="Setup length", kind="dim", nominal=96, up=0.25, dn=-0.25, ctq=False, pin_x=36, pin_y=64),
                dict(name="Runout", kind="max", nominal=0, up=0.02, ctq=True, pin_x=74, pin_y=48),
            ], [("D", "Added runout check for all turning cells", "Quality Manager", timezone.now() - timedelta(days=17))])

        # ---- intake + SNCRs
        sncr42 = SNCR.objects.create(no="SNCR-0042", supplier="Sunrise Metals", heat="H-8091",
                                     issue="No valid MTC supplied — intake rejected", status="Open",
                                     action="Stock quarantined · Purchasing notified", raised_on="16 Oct 2026")
        SNCR.objects.create(no="SNCR-0039", supplier="Mukand Ltd", heat="H-8066",
                            issue="Bar diameter undersize (Ø28.42 vs Ø28.50 min)", status="Under review",
                            action="100% incoming inspection", raised_on="14 Oct 2026")
        SNCR.objects.create(no="SNCR-0031", supplier="Bharat Forge", heat="H-8012",
                            issue="Chemistry deviation — Cr 1.42% (max 1.30%)", status="Closed",
                            action="Supplier CAPA accepted", raised_on="09 Oct 2026")

        IntakeLot.objects.create(no="INT-8841", supplier="JSW Steel", grade="EN8D", heat_no="H-8101", qty_kg=2400,
                                 bundles=12, vehicle="TN 38 GH 2201", po="PO-7742", mtc_file="MTC-8101-JSW.pdf",
                                 received="received 09:10",
                                 chemistry_json={"C": 0.41, "Mn": 0.78, "Si": 0.24, "S": 0.021, "P": 0.018})
        IntakeLot.objects.create(no="INT-8840", supplier="Kalyani Steels", grade="20MnCr5", heat_no="H-8099",
                                 qty_kg=1800, bundles=9, vehicle="KA 05 MJ 8812", po="PO-7738",
                                 mtc_file="MTC-8099-KS.pdf", received="received 08:42",
                                 status="lab", note="Lab sample tagged LAB-8840 · spectro analysis in progress.",
                                 chemistry_json={"C": 0.19, "Mn": 1.24, "Cr": 1.12})
        IntakeLot.objects.create(no="INT-8839", supplier="Mukand Ltd", grade="EN19", heat_no="H-8097", qty_kg=750,
                                 bundles=4, vehicle="MH 12 QP 4471", po="PO-7731", mtc_file="MTC-8097-MK.pdf",
                                 received="received 07:55",
                                 chemistry_json={"C": 0.47, "Mn": 0.66, "Cr": 1.04, "Mo": 0.29})
        IntakeLot.objects.create(no="INT-8838", supplier="JSW Steel", grade="C45", heat_no="H-8095", qty_kg=3100,
                                 bundles=15, vehicle="TN 38 GH 2201", po="PO-7726", mtc_file="MTC-8095-JSW.pdf",
                                 received="released 08:12", status="released",
                                 released_at="08:12", released_by="N. Devi",
                                 chemistry_json={"C": 0.45, "Mn": 0.71, "Si": 0.22})
        IntakeLot.objects.create(no="INT-8836", supplier="Sunrise Metals", grade="EN8D", heat_no="H-8091", qty_kg=600,
                                 bundles=3, vehicle="TN 59 KL 1104", po="PO-7719", mtc_file="",
                                 received="received 06:40", status="quarantined", sncr=sncr42,
                                 note="No valid mill test certificate supplied — stock is frozen.", chemistry_json={})

        # ---- handover history + audit trail
        Handover.objects.create(shift_from="Shift C", shift_to="Shift A", signed_by="A. Murugan",
                                checks={"jobs": True, "parts": True, "alerts": True, "tools": True,
                                        "health": True, "checks": True},
                                note="WO-1042 first piece approved at 06:38 · DTI-011 blocked from measurement")
        Handover.objects.create(shift_from="Shift B", shift_to="Shift C", signed_by="K. Vel",
                                checks={"jobs": True, "parts": True, "alerts": True, "tools": True,
                                        "health": True, "checks": True},
                                note="HT Oven #01 PM overdue — maintenance informed; WO-1039 cooling hold running")

        AUDIT = [
            ("10:12:44", "R. Karthik", "QA Floor Inspector", "Inspection submitted", "WO-1049 · Op 80 PDI",
             "6 parameters · 1 non-CTQ out of tolerance · 2 photos", "10.8.2.41", "TAB-07", "9f3a2c"),
            ("10:05:18", "R. Karthik", "QA Floor Inspector", "Inspection submitted", "WO-1053 · Op 60",
             "4 parameters · all in tolerance", "10.8.2.41", "TAB-07", "7b1d90"),
            ("09:58:02", "S. Ravi", "Shift Supervisor", "Concession issued", "CC-0114 · WO-1045",
             "Reason: visual acceptance · Quality Manager co-sign", "10.8.1.12", "DSK-03", "c4e881"),
            ("09:42:36", "R. Karthik", "QA Floor Inspector", "Station scan verified", "CNC-L4 / TRAVELER-WO-1049",
             "Dual QR presence rule satisfied", "10.8.2.41", "TAB-07", "11af62"),
            ("09:31:09", "System", "Interlock Engine", "Shipping gate blocked", "SHIP-2290 · WO-1050",
             "Rule a failed — Op 70 Final Assembly incomplete", "—", "SERVER", "5d0c44"),
            ("09:20:51", "M. Prakash", "Machine Operator", "Shift handover signed", "HT-02 · Shift A → B",
             "12 open checks acknowledged · 0 overdue", "10.8.3.19", "TAB-11", "ae77b3"),
            ("08:55:47", "S. Ravi", "Shift Supervisor", "Lot quarantined", "QUA-2208 · WO-1051",
             "CTQ failure · moved to Rejection Holding Area", "10.8.1.12", "DSK-03", "0c93f1"),
            ("08:41:15", "System", "Calibration Engine", "Measurement blocked", "DTI-011",
             "Gauge calibration expired 20 Sep 2026 — entry refused", "—", "SERVER", "e2b408"),
        ]
        for t, user, role, action, entity, detail, ip, device, h in AUDIT:
            log = AuditLog.objects.create(user=user, role=role, action=action, entity=entity,
                                          detail=detail, ip=ip, device=device, hash=h)
            # backdate to today's shift for a believable trail
            hh, mm, ss = [int(x) for x in t.split(":")]
            AuditLog.objects.filter(pk=log.pk).update(
                at=timezone.make_aware(datetime.combine(date.today(), datetime.min.time()) +
                                       timedelta(hours=hh, minutes=mm, seconds=ss))
            )

        self.stdout.write(self.style.SUCCESS(
            f"Seeded {WorkOrder.objects.count()} work orders, {Inspection.objects.count()} inspections, "
            f"{IntakeLot.objects.count()} intake lots, {Template.objects.count()} templates, "
            f"{Shipment.objects.count()} shipments, {Employee.objects.count()} users."
        ))
        self.stdout.write("Demo logins (password 'zapuza'): " + ", ".join(p[0] for p in PEOPLE))
