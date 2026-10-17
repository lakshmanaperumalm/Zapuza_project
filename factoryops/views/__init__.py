from .auth import cover, login_view, logout_view
from .intake import intake, lab_result, reject_lot, send_lab, verify_lot
from .portal import (
    approvals, approve_inspection, audit, concession_inspection, dashboard, demo,
    dispatch, flow, gate_pass, holds, dispose_hold, job_detail, jobs, master,
    reject_inspection, rollout, team, trace,
)
from .studio import (
    add_field, approve_template, delete_field, new_revision, return_template,
    studio, submit_template,
)
from .tablet import (
    first_piece as tablet_first_piece, handover as tablet_handover, home as tablet_home,
    hourly as tablet_hourly, inspect as tablet_inspect, jobs as tablet_jobs,
    station_scan as tablet_station, submitted as tablet_submitted, traveler as tablet_traveler,
)

__all__ = [
    "cover", "login_view", "logout_view", "dashboard", "flow", "jobs", "job_detail",
    "approvals", "approve_inspection", "concession_inspection", "reject_inspection",
    "holds", "dispose_hold", "dispatch", "gate_pass", "trace", "master", "audit",
    "team", "rollout", "demo", "intake", "verify_lot", "send_lab", "lab_result",
    "reject_lot", "studio", "new_revision", "add_field", "delete_field",
    "submit_template", "approve_template", "return_template", "tablet_home",
    "tablet_station", "tablet_jobs", "tablet_traveler", "tablet_inspect", "tablet_submitted",
    "tablet_first_piece", "tablet_hourly", "tablet_handover",
]
