from django.urls import path
from . import views

urlpatterns = [
    path("", views.index_redirect, name="index"),
    path("portal/logout/", views.portal_logout, name="portal_logout"),

    # Admin Portal Routes
    path("portal/admin/login/", views.admin_login, name="admin_login"),
    path("portal/admin/dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("portal/admin/courses/", views.course_list, name="course_list"),
    path("portal/admin/courses/new/", views.course_create, name="course_create"),
    path("portal/admin/courses/<int:course_id>/", views.course_edit, name="course_edit"),
    path("portal/admin/courses/<int:course_id>/archive/", views.course_archive, name="course_archive"),
    path("portal/admin/students/", views.student_list, name="student_list"),
    path("portal/admin/students/enroll/", views.student_enroll, name="student_enroll"),
    path("portal/admin/students/<int:student_id>/", views.student_detail, name="student_detail"),
    path("portal/admin/students/<int:student_id>/edit/", views.student_edit, name="student_edit"),
    path("portal/admin/students/<int:student_id>/delete/", views.student_delete, name="student_delete"),
    path("portal/admin/students/<int:student_id>/reset-password/", views.student_reset_password, name="student_reset_password"),
    path("portal/admin/attendance/", views.admin_attendance, name="admin_attendance"),
    path("portal/admin/approvals/", views.completion_approvals, name="completion_approvals"),
    path("portal/admin/certificates/", views.certificate_center, name="certificate_center"),
    path("portal/admin/certificates/<int:certificate_id>/download/", views.certificate_download, name="certificate_download"),
    path("portal/admin/certificates/<int:certificate_id>/revoke/", views.certificate_revoke, name="certificate_revoke"),
    path("portal/admin/settings/", views.organization_settings_view, name="admin_settings"),

    # Student Portal Routes
    path("portal/student/login/", views.student_login, name="student_login"),
    path("portal/student/dashboard/", views.student_dashboard, name="student_dashboard"),
    path("portal/student/courses/", views.student_courses, name="student_courses"),
    path("portal/student/attendance/", views.student_attendance, name="student_attendance"),
    path("portal/student/certificates/", views.student_certificates, name="student_certificates"),
    path("portal/student/certificates/<int:certificate_id>/download/", views.student_certificate_download, name="student_certificate_download"),
    path("portal/student/profile/", views.student_profile_view, name="student_profile"),

    # Public / Verification Route
    path("portal/certificates/<str:cert_number>/", views.public_certificate_view, name="public_certificate_view"),
    path("portal/certificates/<str:cert_number>/download/", views.public_certificate_download, name="public_certificate_download"),
]
