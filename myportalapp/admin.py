from django.contrib import admin
from .models import (
    OrganizationSettings,
    Student,
    Course,
    Enrollment,
    CourseSession,
    AttendanceRecord,
    Certificate,
)


@admin.register(OrganizationSettings)
class OrganizationSettingsAdmin(admin.ModelAdmin):
    list_display = ("name", "signatory_name", "signatory_title", "updated_at")


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("full_name", "registration_number", "email", "phone", "status", "created_at")
    search_fields = ("full_name", "registration_number", "email")
    list_filter = ("status",)


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "duration_days", "duration_hours", "start_date", "end_date", "status")
    search_fields = ("name", "code")
    list_filter = ("status",)


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ("student", "course", "enrollment_date", "status", "completion_status", "approved_at")
    search_fields = ("student__full_name", "student__registration_number", "course__name", "course__code")
    list_filter = ("status", "completion_status")


@admin.register(CourseSession)
class CourseSessionAdmin(admin.ModelAdmin):
    list_display = ("course", "date", "topic", "planned_hours", "actual_hours", "is_completed")
    search_fields = ("course__name", "topic")
    list_filter = ("is_completed", "course")


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ("student", "session", "status", "created_at")
    search_fields = ("student__full_name", "session__course__name", "session__topic")
    list_filter = ("status",)


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = (
        "certificate_number",
        "student",
        "course",
        "certificate_type",
        "completion_date",
        "issue_date",
        "status",
    )
    search_fields = ("certificate_number", "student__full_name", "course__name")
    list_filter = ("certificate_type", "status")
