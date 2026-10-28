import re
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal


class OrganizationSettings(models.Model):
    name = models.CharField(max_length=200, default="Meridian Training Institute")
    logo = models.ImageField(upload_to="branding/", blank=True, null=True)
    signatory_name = models.CharField(max_length=200, default="Dr. Helena Voss")
    signatory_title = models.CharField(max_length=200, default="Director of Training")
    signature_image = models.ImageField(upload_to="signatures/", blank=True, null=True)
    footer_text = models.TextField(
        default="This certificate confirms participation in and completion of the listed training."
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Organization Setting"
        verbose_name_plural = "Organization Settings"

    def __str__(self):
        return self.name

    @classmethod
    def get_settings(cls):
        obj, created = cls.objects.get_or_create(
            id=1,
            defaults={
                "name": "Meridian Training Institute",
                "signatory_name": "Dr. Helena Voss",
                "signatory_title": "Director of Training",
                "footer_text": "This certificate confirms participation in and completion of the listed training.",
            },
        )
        return obj

    @property
    def logo_url(self):
        if self.logo:
            try:
                return self.logo.url
            except Exception:
                pass
        return "/static/images/logo-placeholder.svg"

    @property
    def signature_image_url(self):
        if self.signature_image:
            try:
                return self.signature_image.url
            except Exception:
                pass
        return ""


class Student(models.Model):
    STATUS_CHOICES = [
        ("enrolled", "Enrolled"),
        ("completed", "Completed"),
        ("inactive", "Inactive"),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="student_profile",
        null=True,
        blank=True,
    )
    full_name = models.CharField(max_length=200)
    registration_number = models.CharField(max_length=64, unique=True, db_index=True)
    email = models.EmailField()
    phone = models.CharField(max_length=50, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="enrolled")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.full_name} ({self.registration_number})"

    @property
    def first_name(self):
        parts = self.full_name.strip().split()
        return parts[0] if parts else self.full_name

    @property
    def initials(self):
        parts = self.full_name.strip().split()
        if len(parts) >= 2:
            return f"{parts[0][0]}{parts[-1][0]}".upper()
        elif parts and len(parts[0]) >= 2:
            return parts[0][:2].upper()
        elif parts and len(parts[0]) == 1:
            return parts[0].upper()
        return "ST"

    @classmethod
    def generate_registration_number(cls):
        current_year = timezone.now().year
        prefix = f"MTI-{current_year}-"
        # Find existing numbers with matching prefix
        existing = cls.objects.filter(registration_number__startswith=prefix).values_list(
            "registration_number", flat=True
        )
        max_num = 0
        for num_str in existing:
            match = re.search(r"(\d+)$", num_str)
            if match:
                val = int(match.group(1))
                if val > max_num:
                    max_num = val
        next_val = max_num + 1
        return f"{prefix}{next_val:04d}"


class Course(models.Model):
    STATUS_CHOICES = [
        ("active", "Active"),
        ("upcoming", "Upcoming"),
        ("archived", "Archived"),
    ]

    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    duration_days = models.PositiveIntegerField(default=1)
    duration_hours = models.DecimalField(max_digits=6, decimal_places=1, default=6.0)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code})"

    @property
    def enrolled_count(self):
        return self.enrollments.filter(status__in=["enrolled", "completed"]).count()


class Enrollment(models.Model):
    STATUS_CHOICES = [
        ("enrolled", "Enrolled"),
        ("completed", "Completed"),
        ("inactive", "Inactive"),
    ]

    COMPLETION_CHOICES = [
        ("in_progress", "In progress"),
        ("pending", "Awaiting approval"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="enrollments")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="enrollments")
    enrollment_date = models.DateField(default=timezone.now)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="enrolled")
    completion_status = models.CharField(
        max_length=20, choices=COMPLETION_CHOICES, default="in_progress"
    )
    approved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_enrollments"
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    completion_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("student", "course")
        ordering = ["-enrollment_date"]

    def __str__(self):
        return f"{self.student.full_name} - {self.course.name}"

    def get_attendance_summary(self):
        records = self.attendance_records.all()
        present = records.filter(status="present").count()
        absent = records.filter(status="absent").count()
        leave = records.filter(status="leave").count()
        total = records.count()
        rate = round((present / total) * 100) if total > 0 else 0
        return {
            "present": present,
            "absent": absent,
            "leave": leave,
            "total": total,
            "rate": rate,
        }

    def get_completed_hours(self):
        # Sum actual_hours for sessions where attendance status is present
        records = self.attendance_records.filter(status="present").select_related("session")
        total = Decimal("0.0")
        for rec in records:
            total += rec.session.actual_hours
        return total

    @property
    def attendance_percent(self):
        return self.get_attendance_summary()["rate"]

    @property
    def progress_percent(self):
        if self.status == "completed":
            return 100
        req = self.course.duration_hours
        if req and req > 0:
            done = self.get_completed_hours()
            pct = int(round((done / req) * 100))
            return min(pct, 100)
        return 0

    def sync_completion_status(self):
        # Auto-detect if criteria met (80% attendance and >= course duration hours)
        if self.status != "completed" and self.completion_status == "in_progress":
            rate = self.attendance_percent
            hours = self.get_completed_hours()
            if rate >= 80 and hours >= self.course.duration_hours:
                self.completion_status = "pending"
                self.save(update_fields=["completion_status"])

    def generate_completion_certificate(self):
        """
        Generates and issues a completion certificate for this enrollment if one does not already exist.
        Returns the Certificate instance.
        """
        from .pdf import save_certificate_pdf

        cert = self.certificates.filter(status="issued").first()
        if not cert:
            cert = Certificate.objects.filter(
                student=self.student,
                course=self.course,
                certificate_type="completion",
                status="issued",
            ).first()

        if not cert:
            cert = Certificate(
                student=self.student,
                course=self.course,
                enrollment=self,
                certificate_type="completion",
                duration_days=self.course.duration_days,
                duration_hours=self.course.duration_hours,
                completion_date=self.completion_date or timezone.now().date(),
                issue_date=timezone.now().date(),
                status="issued",
            )
            cert.save()
            save_certificate_pdf(cert)
        else:
            if not cert.enrollment:
                cert.enrollment = self
                cert.save(update_fields=["enrollment"])
            if not cert.pdf_file:
                try:
                    save_certificate_pdf(cert)
                except Exception:
                    pass
        return cert


class CourseSession(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="sessions")
    date = models.DateField()
    topic = models.CharField(max_length=255)
    planned_hours = models.DecimalField(max_digits=5, decimal_places=1, default=6.0)
    actual_hours = models.DecimalField(max_digits=5, decimal_places=1, default=6.0)
    is_completed = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-created_at"]

    def __str__(self):
        return f"{self.course.code} - {self.date}: {self.topic}"


class AttendanceRecord(models.Model):
    STATUS_CHOICES = [
        ("present", "Present"),
        ("absent", "Absent"),
        ("leave", "Leave"),
    ]

    session = models.ForeignKey(CourseSession, on_delete=models.CASCADE, related_name="attendance_records")
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name="attendance_records")
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="attendance_records")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="present")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("session", "student")
        ordering = ["-session__date"]

    def __str__(self):
        return f"{self.student.full_name} - {self.session.date} ({self.status})"


class Certificate(models.Model):
    TYPE_CHOICES = [
        ("completion", "Completion"),
        ("achievement", "Achievement"),
    ]

    STATUS_CHOICES = [
        ("issued", "Issued"),
        ("revoked", "Revoked"),
    ]

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="certificates")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="certificates")
    enrollment = models.ForeignKey(
        Enrollment, on_delete=models.SET_NULL, null=True, blank=True, related_name="certificates"
    )
    certificate_number = models.CharField(max_length=100, unique=True, db_index=True)
    certificate_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="completion")
    achievement_text = models.CharField(max_length=255, blank=True)
    duration_days = models.PositiveIntegerField(default=1)
    duration_hours = models.DecimalField(max_digits=6, decimal_places=1, default=1.0)
    completion_date = models.DateField()
    issue_date = models.DateField(default=timezone.now)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="issued")
    pdf_file = models.FileField(upload_to="certificates/", blank=True, null=True)

    # Branding snapshot (tamper-proof historical snapshot)
    org_name = models.CharField(max_length=200)
    org_logo_url = models.CharField(max_length=255, blank=True)
    signatory_name = models.CharField(max_length=200)
    signatory_title = models.CharField(max_length=200)
    signature_image_url = models.CharField(max_length=255, blank=True)
    signature_image = models.ImageField(upload_to="certificates/signatures/", blank=True, null=True)
    footer_text = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-issue_date", "-created_at"]

    def __str__(self):
        return f"{self.certificate_number} - {self.student.full_name} ({self.course.name})"

    @property
    def is_official(self):
        return self.status == "issued"

    @property
    def signature_url(self):
        if self.signature_image:
            try:
                return self.signature_image.url
            except Exception:
                pass
        return self.signature_image_url or ""

    def save(self, *args, **kwargs):
        if not self.certificate_number:
            self.certificate_number = self.generate_certificate_number()
        if not self.org_name:
            settings_obj = OrganizationSettings.get_settings()
            self.org_name = settings_obj.name
            self.org_logo_url = settings_obj.logo_url
            self.signatory_name = settings_obj.signatory_name
            self.signatory_title = settings_obj.signatory_title
            self.footer_text = settings_obj.footer_text
            self.signature_image_url = settings_obj.signature_image_url
            if settings_obj.signature_image:
                try:
                    import os
                    from django.core.files.base import ContentFile
                    try:
                        settings_obj.signature_image.open("rb")
                        content = settings_obj.signature_image.read()
                    finally:
                        try:
                            settings_obj.signature_image.close()
                        except Exception:
                            pass
                    filename = os.path.basename(settings_obj.signature_image.name)
                    self.signature_image.save(filename, ContentFile(content), save=False)
                    try:
                        self.signature_image_url = self.signature_image.url
                    except Exception:
                        self.signature_image_url = settings_obj.signature_image_url
                except Exception:
                    self.signature_image_url = settings_obj.signature_image_url
        if not self.signatory_name:
            settings_obj = OrganizationSettings.get_settings()
            self.signatory_name = settings_obj.signatory_name
        if not self.signatory_title:
            settings_obj = OrganizationSettings.get_settings()
            self.signatory_title = settings_obj.signatory_title
        super().save(*args, **kwargs)

    @classmethod
    def generate_certificate_number(cls):
        current_year = timezone.now().year
        prefix = f"MTI-{current_year}-"
        existing = cls.objects.filter(certificate_number__startswith=prefix).values_list(
            "certificate_number", flat=True
        )
        max_num = 0
        for num_str in existing:
            match = re.search(r"(\d+)$", num_str)
            if match:
                val = int(match.group(1))
                if val > max_num:
                    max_num = val
        next_val = max_num + 1
        return f"{prefix}{next_val:04d}"


def _get_user_initials(self):
    name = (self.get_full_name() or self.username or "").strip()
    parts = name.split()
    if len(parts) >= 2:
        return f"{parts[0][0]}{parts[-1][0]}".upper()
    elif parts and len(parts[0]) >= 2:
        return parts[0][:2].upper()
    elif parts and len(parts[0]) == 1:
        return parts[0].upper()
    return "US"


if not hasattr(User, "initials"):
    User.add_to_class("initials", property(_get_user_initials))

if not hasattr(User, "student"):
    User.add_to_class("student", property(lambda self: getattr(self, "student_profile", None)))

