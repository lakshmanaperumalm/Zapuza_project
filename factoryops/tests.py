"""Business-rule regression suite for the Zapuza FactoryOps prototype.

Every test runs against the same seeded demo dataset the client sees, so the
assertions double as a check that the demo story is still true.
"""
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .models import (
    AuditLog, FirstPiece, Handover, HourlyCheck, Inspection, IntakeLot, Machine,
    Measurement, SNCR, Shipment, Template, WorkOrder,
)
from .services import gate_checks


class Seeded(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", verbosity=0)

    def as_user(self, username):
        self.assertTrue(self.client.login(username=username, password="zapuza"), username)
        return self.client

    def messages_text(self, response):
        """Follow a redirect and return every flash message rendered on the page."""
        return " ".join(str(m) for m in response.wsgi_request._messages)


# --------------------------------------------------------------------- approvals
class ApprovalRules(Seeded):
    def test_supervisor_approves_a_clean_checklist(self):
        insp = Inspection.objects.get(wo__wo_no="WO-1053")
        self.as_user("sravi")
        self.client.post(reverse("factoryops:approve_inspection", args=[insp.pk]))
        insp.refresh_from_db()
        self.assertEqual(insp.status, Inspection.Status.APPROVED)
        # Op 60 is an in-process check: signing it moves the traveler forward.
        self.assertEqual(insp.wo.status, WorkOrder.Status.IN_PROGRESS)
        self.assertEqual(insp.wo.operations.filter(status="active").count(), 1)

    def test_ctq_failure_blocks_approval(self):
        insp = Inspection.objects.get(wo__wo_no="WO-1049")
        self.assertTrue(insp.ctq_failed)
        self.as_user("sravi")
        resp = self.client.post(reverse("factoryops:approve_inspection", args=[insp.pk]), follow=True)
        insp.refresh_from_db()
        self.assertEqual(insp.status, Inspection.Status.PENDING)
        self.assertIn("CTQ", resp.content.decode())

    def test_operator_cannot_approve(self):
        insp = Inspection.objects.get(wo__wo_no="WO-1053")
        self.as_user("amurugan")
        self.client.post(reverse("factoryops:approve_inspection", args=[insp.pk]))
        insp.refresh_from_db()
        self.assertEqual(insp.status, Inspection.Status.PENDING)

    def test_concession_needs_a_real_justification(self):
        insp = Inspection.objects.create(
            wo=WorkOrder.objects.get(wo_no="WO-1053"), op="Op 60 Visual", inspector="R. Karthik",
            template_label="PDI-SHAFT Rev C", status=Inspection.Status.PENDING,
        )
        Measurement.objects.create(inspection=insp, seq=1, name="Surface finish Ra", spec_text="0.8 MAX",
                                   is_max=True, up=0.8, value_num=0.92, unit="µm", ctq=False)
        self.as_user("sravi")
        self.client.post(reverse("factoryops:concession_inspection", args=[insp.pk]),
                         {"justification": "ok"})
        insp.refresh_from_db()
        self.assertEqual(insp.status, Inspection.Status.PENDING)
        self.client.post(reverse("factoryops:concession_inspection", args=[insp.pk]),
                         {"justification": "Customer-approved cosmetic deviation, drawing note 4."})
        insp.refresh_from_db()
        self.assertEqual(insp.status, Inspection.Status.CONCEDED)

    def test_ctq_failure_cannot_be_conceded(self):
        insp = Inspection.objects.get(wo__wo_no="WO-1049")
        self.as_user("sravi")
        self.client.post(reverse("factoryops:concession_inspection", args=[insp.pk]),
                         {"justification": "Please let this one through, the customer is waiting."})
        insp.refresh_from_db()
        self.assertEqual(insp.status, Inspection.Status.PENDING)

    def test_reject_quarantines_the_lot(self):
        insp = Inspection.objects.get(wo__wo_no="WO-1049")
        self.as_user("sravi")
        self.client.post(reverse("factoryops:reject_inspection", args=[insp.pk]),
                         {"reason": "Shaft OD over tolerance", "note": "Moved to MRB"})
        insp.refresh_from_db()
        self.assertEqual(insp.status, Inspection.Status.REJECTED)
        self.assertEqual(insp.wo.status, WorkOrder.Status.QUARANTINED)
        self.assertTrue(insp.wo.holds.filter(status="open").exists())


# ---------------------------------------------------------------------- dispatch
class DispatchInterlocks(Seeded):
    def test_clear_shipment_passes_all_three_gates(self):
        ship = Shipment.objects.get(no="SHIP-2288")
        self.assertTrue(all(c["ok"] for c in gate_checks(ship)))

    def test_pending_pdi_locks_the_gate(self):
        ship = Shipment.objects.get(no="SHIP-2292")
        checks = gate_checks(ship)
        self.assertFalse(all(c["ok"] for c in checks))
        self.assertFalse(checks[2]["ok"])

    def test_blocked_gate_pass_does_not_ship(self):
        ship = Shipment.objects.get(no="SHIP-2292")
        self.as_user("pmanager")
        self.client.post(reverse("factoryops:gate_pass", args=[ship.pk]), follow=True)
        ship.refresh_from_db()
        self.assertNotEqual(ship.status, "shipped")


# ------------------------------------------------------------------------ intake
class IntakeRules(Seeded):
    def test_chemistry_outside_grade_blocks_release(self):
        lot = IntakeLot.objects.get(no="INT-8839")
        self.assertFalse(lot.chemistry_ok)
        self.as_user("ndevi")
        resp = self.client.post(reverse("factoryops:verify_lot", args=[lot.pk]),
                                {"ack_mtc": "on", "ack_heat": "on"}, follow=True)
        lot.refresh_from_db()
        self.assertEqual(lot.status, IntakeLot.Status.AWAITING)
        self.assertIn("Chemistry", resp.content.decode())

    def test_clean_lot_releases(self):
        lot = IntakeLot.objects.get(no="INT-8841")
        self.as_user("ndevi")
        self.client.post(reverse("factoryops:verify_lot", args=[lot.pk]),
                         {"ack_mtc": "on", "ack_heat": "on"})
        lot.refresh_from_db()
        self.assertEqual(lot.status, IntakeLot.Status.RELEASED)
        self.assertEqual(lot.released_by, "N. Devi")

    def test_missing_acknowledgement_blocks_release(self):
        lot = IntakeLot.objects.get(no="INT-8841")
        self.as_user("ndevi")
        self.client.post(reverse("factoryops:verify_lot", args=[lot.pk]), {"ack_mtc": "on"})
        lot.refresh_from_db()
        self.assertEqual(lot.status, IntakeLot.Status.AWAITING)

    def test_lab_failure_quarantines_and_raises_sncr(self):
        lot = IntakeLot.objects.get(no="INT-8840")
        self.as_user("ndevi")
        self.client.post(reverse("factoryops:send_lab", args=[lot.pk]))
        before = SNCR.objects.count()
        self.client.post(reverse("factoryops:lab_result", args=[lot.pk]),
                         {"result": "fail", "detail": "Cr 1.24 over 20MnCr5 limits"})
        lot.refresh_from_db()
        self.assertEqual(lot.status, IntakeLot.Status.QUARANTINED)
        self.assertEqual(SNCR.objects.count(), before + 1)
        self.assertIsNotNone(lot.sncr)

    def test_operator_cannot_release_material(self):
        lot = IntakeLot.objects.get(no="INT-8841")
        self.as_user("amurugan")
        self.client.post(reverse("factoryops:verify_lot", args=[lot.pk]),
                         {"ack_mtc": "on", "ack_heat": "on"})
        lot.refresh_from_db()
        self.assertEqual(lot.status, IntakeLot.Status.AWAITING)


# ----------------------------------------------------------------------- studio
class TemplateLifecycle(Seeded):
    def test_draft_to_pending_to_released(self):
        tpl = Template.objects.get(status=Template.Status.DRAFT)
        self.as_user("ndevi")
        self.client.post(reverse("factoryops:submit_template", args=[tpl.pk]))
        tpl.refresh_from_db()
        self.assertEqual(tpl.status, Template.Status.PENDING)

        self.client.post(reverse("factoryops:approve_template", args=[tpl.pk]))
        tpl.refresh_from_db()
        self.assertEqual(tpl.status, Template.Status.PENDING)  # engineer cannot release

        self.as_user("qmanager")
        self.client.post(reverse("factoryops:approve_template", args=[tpl.pk]))
        tpl.refresh_from_db()
        self.assertEqual(tpl.status, Template.Status.RELEASED)
        self.assertTrue(tpl.approved_by)

    def test_released_template_is_read_only(self):
        tpl = Template.objects.filter(status=Template.Status.RELEASED).first()
        self.as_user("ndevi")
        resp = self.client.post(reverse("factoryops:add_field", args=[tpl.pk]),
                                {"name": "Sneaky extra check", "kind": "dim", "nominal": "1",
                                 "up": "0", "dn": "0", "unit": "mm"}, follow=True)
        self.assertEqual(tpl.fields.filter(name="Sneaky extra check").count(), 0)
        self.assertIn("revision", resp.content.decode().lower())

    def test_empty_draft_cannot_be_submitted(self):
        tpl = Template.objects.create(code="PDI-EMPTY", name="Empty", part_no="XX-1",
                                      status=Template.Status.DRAFT, rev="A", owner="N. Devi")
        self.as_user("ndevi")
        self.client.post(reverse("factoryops:submit_template", args=[tpl.pk]))
        tpl.refresh_from_db()
        self.assertEqual(tpl.status, Template.Status.DRAFT)


# ----------------------------------------------------------------------- tablet
class TabletFlow(Seeded):
    def sign_handover(self):
        checks = {k: "on" for k in ["jobs", "parts", "alerts", "tools", "health", "checks"]}
        checks["signature"] = "R. Karthik"
        return self.client.post(reverse("factoryops:tablet_handover"), checks)

    def test_handover_requires_every_item(self):
        self.as_user("rkarthik")
        self.client.post(reverse("factoryops:tablet_handover"),
                         {"jobs": "on", "signature": "R. Karthik"})
        self.assertEqual(Handover.objects.count(), 2)  # seed rows only
        self.sign_handover()
        self.assertEqual(Handover.objects.count(), 3)
        self.assertTrue(self.client.session["handover_ok"])

    def test_jobs_are_locked_until_a_station_is_scanned(self):
        self.as_user("rkarthik")
        self.sign_handover()
        resp = self.client.get(reverse("factoryops:tablet_jobs"))
        self.assertRedirects(resp, reverse("factoryops:tablet_station"))
        self.client.post(reverse("factoryops:tablet_station"), {"code": "CNC-L4"})
        self.assertEqual(self.client.get(reverse("factoryops:tablet_jobs")).status_code, 200)

    def test_pm_locked_machine_refuses_the_station(self):
        machine = Machine.objects.get(code="HT-01")
        self.assertEqual(machine.pm_status, "overdue")
        self.as_user("rkarthik")
        self.sign_handover()
        self.client.post(reverse("factoryops:tablet_station"), {"code": "HT-01"})
        self.assertNotEqual(self.client.session.get("station"), "HT-01")

    def test_inspection_requires_the_traveler_scan(self):
        self.as_user("rkarthik")
        self.sign_handover()
        self.client.post(reverse("factoryops:tablet_station"), {"code": "CNC-L4"})
        resp = self.client.get(reverse("factoryops:tablet_inspect", args=["WO-1052"]))
        self.assertRedirects(resp, reverse("factoryops:tablet_traveler", args=["WO-1052"]))

    def _open_inspect(self):
        self.as_user("rkarthik")
        self.sign_handover()
        self.client.post(reverse("factoryops:tablet_station"), {"code": "CNC-L4"})
        self.client.post(reverse("factoryops:tablet_traveler", args=["WO-1052"]))
        wo = WorkOrder.objects.get(wo_no="WO-1052")
        tpl = Template.objects.get(code="PDI-SHAFT", status=Template.Status.RELEASED)
        return wo, tpl

    def _payload(self, tpl, gauge="MIC-204", photos=False, oot=False):
        data = {}
        for f in tpl.fields.all():
            if f.kind == "visual":
                data[f"m_{f.pk}"] = "PASS"
            elif f.kind == "max":
                data[f"m_{f.pk}"] = "0.050" if oot else "0.001"
            else:
                data[f"m_{f.pk}"] = f"{f.nominal + (0.5 if oot else 0):.3f}"
            data[f"g_{f.pk}"] = gauge
        if photos:
            data["photos"] = "on"
        return data

    def test_expired_gauge_refuses_the_reading(self):
        wo, tpl = self._open_inspect()
        before = Inspection.objects.count()
        resp = self.client.post(reverse("factoryops:tablet_inspect", args=["WO-1052"]),
                                self._payload(tpl, gauge="DTI-011"), follow=True)
        self.assertEqual(Inspection.objects.count(), before)
        self.assertIn("expired", resp.content.decode().lower())

    def test_out_of_tolerance_needs_photos(self):
        wo, tpl = self._open_inspect()
        before = Inspection.objects.count()
        self.client.post(reverse("factoryops:tablet_inspect", args=["WO-1052"]),
                         self._payload(tpl, oot=True))
        self.assertEqual(Inspection.objects.count(), before)
        self.client.post(reverse("factoryops:tablet_inspect", args=["WO-1052"]),
                         self._payload(tpl, oot=True, photos=True))
        self.assertEqual(Inspection.objects.count(), before + 1)

    def test_clean_checklist_creates_a_pending_inspection(self):
        wo, tpl = self._open_inspect()
        before = AuditLog.objects.count()
        resp = self.client.post(reverse("factoryops:tablet_inspect", args=["WO-1052"]),
                                self._payload(tpl), follow=True)
        insp = Inspection.objects.filter(wo=wo).order_by("-id").first()
        self.assertEqual(insp.status, Inspection.Status.PENDING)
        self.assertEqual(insp.measurements.count(), tpl.fields.count())
        wo.refresh_from_db()
        self.assertEqual(wo.status, WorkOrder.Status.AWAITING)
        self.assertGreater(AuditLog.objects.count(), before)
        self.assertIn("WO-1052", resp.content.decode())

    def test_hourly_sample_records_a_pass_and_a_fail(self):
        self.as_user("rkarthik")
        self.sign_handover()
        before = HourlyCheck.objects.filter(wo__wo_no="WO-1052").count()
        url = reverse("factoryops:tablet_hourly", args=["WO-1052"])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.post(url, {"s1": "31.996", "s2": "31.998", "s3": "31.994"})
        self.assertEqual(HourlyCheck.objects.filter(wo__wo_no="WO-1052").count(), before + 1)
        self.assertTrue(HourlyCheck.objects.filter(wo__wo_no="WO-1052").first().passed)
        self.client.post(url, {"s1": "31.996", "s2": "32.040", "s3": "31.994"})
        latest = HourlyCheck.objects.filter(wo__wo_no="WO-1052").first()
        self.assertEqual(HourlyCheck.objects.filter(wo__wo_no="WO-1052").count(), before + 2)
        self.assertFalse(latest.passed)

    def test_first_piece_gate_blocks_bad_setup(self):
        self.as_user("rkarthik")
        self.sign_handover()
        self.client.post(reverse("factoryops:tablet_first_piece", args=["WO-1052"]),
                         {"d1": "40.5", "d2": "96.0", "d3": "0.005", "ack": "on"})
        self.assertFalse(FirstPiece.objects.filter(wo__wo_no="WO-1052").exists())
        self.client.post(reverse("factoryops:tablet_first_piece", args=["WO-1052"]),
                         {"d1": "40.004", "d2": "96.02", "d3": "0.008", "ack": "on"})
        self.assertTrue(FirstPiece.objects.filter(wo__wo_no="WO-1052").exists())


# ------------------------------------------------------------------------- audit
class AuditTrail(Seeded):
    def test_every_decision_appends_a_hashed_entry(self):
        before = AuditLog.objects.count()
        insp = Inspection.objects.get(wo__wo_no="WO-1053")
        self.as_user("sravi")
        self.client.post(reverse("factoryops:approve_inspection", args=[insp.pk]))
        self.assertEqual(AuditLog.objects.count(), before + 1)
        entry = AuditLog.objects.latest("id")
        self.assertEqual(len(entry.hash), 6)
        self.assertEqual(entry.user, "S. Ravi")

    def test_audit_survives_a_filtered_query(self):
        self.as_user("sravi")
        resp = self.client.get(reverse("factoryops:audit"), {"q": "Inspection approved"})
        self.assertEqual(resp.status_code, 200)


# ------------------------------------------------------------------------ portal
class PortalPages(Seeded):
    def test_every_portal_screen_renders_for_the_supervisor(self):
        self.as_user("sravi")
        urls = [
            reverse("factoryops:dashboard"), reverse("factoryops:flow"), reverse("factoryops:jobs"),
            reverse("factoryops:approvals"), reverse("factoryops:holds"), reverse("factoryops:dispatch"),
            reverse("factoryops:intake"), reverse("factoryops:studio"), reverse("factoryops:trace"),
            reverse("factoryops:master"), reverse("factoryops:audit"), reverse("factoryops:team"),
            reverse("factoryops:rollout"), reverse("factoryops:demo"),
            reverse("factoryops:job_detail", args=["WO-1052"]),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_each_master_tab_renders(self):
        self.as_user("sravi")
        for tab in ["machines", "gauges", "templates", "heats", "parts"]:
            with self.subTest(tab=tab):
                resp = self.client.get(reverse("factoryops:master"), {"tab": tab})
                self.assertEqual(resp.status_code, 200)
                self.assertContains(resp, f"?tab={tab}")

    def test_login_required(self):
        resp = self.client.get(reverse("factoryops:approvals"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login/", resp["Location"])
