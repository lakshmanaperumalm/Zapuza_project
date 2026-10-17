from django.urls import path

from . import views

app_name = "factoryops"

urlpatterns = [
    path("", views.cover, name="cover"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),

    path("portal/", views.dashboard, name="dashboard"),
    path("portal/flow/", views.flow, name="flow"),
    path("portal/jobs/", views.jobs, name="jobs"),
    path("portal/jobs/<str:wo_no>/", views.job_detail, name="job_detail"),
    path("portal/approvals/", views.approvals, name="approvals"),
    path("portal/approvals/<int:pk>/approve/", views.approve_inspection, name="approve_inspection"),
    path("portal/approvals/<int:pk>/concession/", views.concession_inspection, name="concession_inspection"),
    path("portal/approvals/<int:pk>/reject/", views.reject_inspection, name="reject_inspection"),
    path("portal/holds/", views.holds, name="holds"),
    path("portal/holds/<int:pk>/dispose/", views.dispose_hold, name="dispose_hold"),
    path("portal/dispatch/", views.dispatch, name="dispatch"),
    path("portal/dispatch/<int:pk>/", views.gate_pass, name="gate_pass"),
    path("portal/intake/", views.intake, name="intake"),
    path("portal/intake/<int:pk>/verify/", views.verify_lot, name="verify_lot"),
    path("portal/intake/<int:pk>/lab/", views.send_lab, name="send_lab"),
    path("portal/intake/<int:pk>/lab-result/", views.lab_result, name="lab_result"),
    path("portal/intake/<int:pk>/reject/", views.reject_lot, name="reject_lot"),
    path("portal/studio/", views.studio, name="studio"),
    path("portal/studio/<int:pk>/revision/", views.new_revision, name="new_revision"),
    path("portal/studio/<int:pk>/field/", views.add_field, name="add_field"),
    path("portal/studio/<int:pk>/field/<int:field_id>/delete/", views.delete_field, name="delete_field"),
    path("portal/studio/<int:pk>/submit/", views.submit_template, name="submit_template"),
    path("portal/studio/<int:pk>/approve/", views.approve_template, name="approve_template"),
    path("portal/studio/<int:pk>/return/", views.return_template, name="return_template"),
    path("portal/trace/", views.trace, name="trace"),
    path("portal/master/", views.master, name="master"),
    path("portal/audit/", views.audit, name="audit"),
    path("portal/team/", views.team, name="team"),
    path("portal/rollout/", views.rollout, name="rollout"),
    path("portal/demo/", views.demo, name="demo"),

    path("tablet/", views.tablet_home, name="tablet_home"),
    path("tablet/scan/", views.tablet_station, name="tablet_station"),
    path("tablet/jobs/", views.tablet_jobs, name="tablet_jobs"),
    path("tablet/first-piece/<str:wo_no>/", views.tablet_first_piece, name="tablet_first_piece"),
    path("tablet/traveler/<str:wo_no>/", views.tablet_traveler, name="tablet_traveler"),
    path("tablet/inspect/<str:wo_no>/", views.tablet_inspect, name="tablet_inspect"),
    path("tablet/submitted/<int:pk>/", views.tablet_submitted, name="tablet_submitted"),
    path("tablet/hourly/<str:wo_no>/", views.tablet_hourly, name="tablet_hourly"),
    path("tablet/handover/", views.tablet_handover, name="tablet_handover"),
]
