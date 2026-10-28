import datetime
from decimal import Decimal
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.utils import timezone

from .forms import (
    AdminLoginForm,
    CourseForm,
    StudentEnrollmentForm,
    StudentLoginForm,
    StudentPasswordChangeForm,
)
from .models import (
    AttendanceRecord,
    Certificate,
    Course,
    CourseSession,
    Enrollment,
    OrganizationSettings,
    Student,
)
from .pdf import generate_certificate_pdf, save_certificate_pdf


class ModelTests(TestCase):
    def setUp(self):
        self.org = OrganizationSettings.get_settings()
        self.course = Course.objects.create(
            name="Industrial Safety Fundamentals",
            code="CRS-101",
            duration_days=5,
            duration_hours=Decimal("30.0"),
            start_date=datetime.date(2026, 10, 1),
            end_date=datetime.date(2026, 10, 5),
            status="active",
        )
        self.user = User.objects.create_user(username="student1", email="student1@example.com", password="password123")
        self.student = Student.objects.create(
            user=self.user,
            full_name="Priya Raman",
            registration_number="MTI-2026-0001",
            email="student1@example.com",
            status="enrolled",
        )

    def test_organization_settings_singleton_and_logo(self):
        org = OrganizationSettings.get_settings()
        self.assertEqual(org.name, "Meridian Training Institute")
        self.assertEqual(org.logo_url, "/static/images/logo-placeholder.svg")
        # Ensure get_settings returns the same instance
        org2 = OrganizationSettings.get_settings()
        self.assertEqual(org.pk, org2.pk)

    def test_student_properties_and_initials(self):
        self.assertEqual(self.student.first_name, "Priya")
        self.assertEqual(self.student.initials, "PR")
        # User initials and student property extensions
        self.assertEqual(self.user.student, self.student)
        self.user.first_name = "Priya"
        self.user.last_name = "Raman"
        self.user.save()
        self.assertEqual(self.user.initials, "PR")

    def test_student_generate_registration_number(self):
        reg = Student.generate_registration_number()
        year = timezone.now().year
        self.assertTrue(reg.startswith(f"MTI-{year}-"))
        self.assertEqual(reg, f"MTI-{year}-0002")

    def test_course_enrolled_count(self):
        self.assertEqual(self.course.enrolled_count, 0)
        Enrollment.objects.create(student=self.student, course=self.course, status="enrolled")
        self.assertEqual(self.course.enrolled_count, 1)

    def test_enrollment_progress_and_attendance_calculations(self):
        enrollment = Enrollment.objects.create(student=self.student, course=self.course, status="enrolled")
        self.assertEqual(enrollment.attendance_percent, 0)
        self.assertEqual(enrollment.progress_percent, 0)

        # Create session 1
        s1 = CourseSession.objects.create(
            course=self.course,
            date=datetime.date(2026, 10, 1),
            topic="Introduction",
            planned_hours=Decimal("6.0"),
            actual_hours=Decimal("6.0"),
            is_completed=True,
        )
        AttendanceRecord.objects.create(session=s1, enrollment=enrollment, student=self.student, status="present")

        summary = enrollment.get_attendance_summary()
        self.assertEqual(summary["present"], 1)
        self.assertEqual(summary["total"], 1)
        self.assertEqual(summary["rate"], 100)
        self.assertEqual(enrollment.get_completed_hours(), Decimal("6.0"))
        # 6 / 30 hours = 20%
        self.assertEqual(enrollment.progress_percent, 20)

    def test_sync_completion_status(self):
        enrollment = Enrollment.objects.create(student=self.student, course=self.course, status="enrolled")
        self.assertEqual(enrollment.completion_status, "in_progress")

        # Create sessions totaling 30 hours
        for i in range(5):
            sess = CourseSession.objects.create(
                course=self.course,
                date=datetime.date(2026, 10, 1) + datetime.timedelta(days=i),
                topic=f"Topic {i+1}",
                planned_hours=Decimal("6.0"),
                actual_hours=Decimal("6.0"),
                is_completed=True,
            )
            AttendanceRecord.objects.create(session=sess, enrollment=enrollment, student=self.student, status="present")

        enrollment.sync_completion_status()
        enrollment.refresh_from_db()
        self.assertEqual(enrollment.completion_status, "pending")

    def test_certificate_snapshot_and_number_generation(self):
        cert = Certificate.objects.create(
            student=self.student,
            course=self.course,
            certificate_type="completion",
            duration_days=5,
            duration_hours=Decimal("30.0"),
            completion_date=datetime.date(2026, 10, 5),
            status="issued",
        )
        self.assertTrue(cert.certificate_number.startswith("MTI-"))
        self.assertEqual(cert.org_name, self.org.name)
        self.assertEqual(cert.signatory_name, self.org.signatory_name)
        self.assertTrue(cert.is_official)


class PDFGenerationTests(TestCase):
    def setUp(self):
        self.org = OrganizationSettings.get_settings()
        self.course = Course.objects.create(
            name="Project Management Essentials",
            code="CRS-102",
            duration_days=3,
            duration_hours=Decimal("21.0"),
            start_date=datetime.date(2026, 10, 1),
            end_date=datetime.date(2026, 10, 3),
            status="active",
        )
        self.student = Student.objects.create(
            full_name="Daniel Okafor",
            registration_number="MTI-2026-0003",
            email="daniel@example.com",
            status="enrolled",
        )
        self.cert = Certificate.objects.create(
            student=self.student,
            course=self.course,
            certificate_type="completion",
            duration_days=3,
            duration_hours=Decimal("21.0"),
            completion_date=datetime.date(2026, 10, 3),
            status="issued",
        )

    def test_generate_completion_pdf(self):
        buf = generate_certificate_pdf(self.cert)
        content = buf.getvalue()
        self.assertTrue(content.startswith(b"%PDF-"))
        self.assertGreater(len(content), 1000)

    def test_generate_achievement_pdf(self):
        self.cert.certificate_type = "achievement"
        self.cert.achievement_text = "With Highest Honors"
        self.cert.save()

        buf = generate_certificate_pdf(self.cert)
        content = buf.getvalue()
        self.assertTrue(content.startswith(b"%PDF-"))
        self.assertGreater(len(content), 1000)

    def test_generate_revoked_pdf(self):
        self.cert.status = "revoked"
        self.cert.save()

        buf = generate_certificate_pdf(self.cert)
        content = buf.getvalue()
        self.assertTrue(content.startswith(b"%PDF-"))

    def test_save_certificate_pdf(self):
        save_certificate_pdf(self.cert)
        self.cert.refresh_from_db()
        self.assertTrue(bool(self.cert.pdf_file))
        self.assertTrue(self.cert.pdf_file.name.endswith(".pdf"))


class FormTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="adminuser", email="admin@example.com", password="adminpassword123"
        )
        self.student_user = User.objects.create_user(
            username="MTI-2026-0010", email="student@example.com", password="studentpassword123"
        )
        self.student = Student.objects.create(
            user=self.student_user,
            full_name="Lena Fischer",
            registration_number="MTI-2026-0010",
            email="student@example.com",
            status="enrolled",
        )

    def test_admin_login_form_valid(self):
        form = AdminLoginForm(data={"username": "adminuser", "password": "adminpassword123"})
        self.assertTrue(form.is_valid())
        # Check login via email
        form_email = AdminLoginForm(data={"username": "admin@example.com", "password": "adminpassword123"})
        self.assertTrue(form_email.is_valid())

    def test_admin_login_form_rejects_non_admin(self):
        form = AdminLoginForm(data={"username": "MTI-2026-0010", "password": "studentpassword123"})
        self.assertFalse(form.is_valid())
        self.assertIn("Administrator privileges are required", form.errors["__all__"][0])

    def test_student_login_form_valid(self):
        # By registration number
        form_reg = StudentLoginForm(data={"username": "MTI-2026-0010", "password": "studentpassword123"})
        self.assertTrue(form_reg.is_valid())
        # By email
        form_email = StudentLoginForm(data={"username": "student@example.com", "password": "studentpassword123"})
        self.assertTrue(form_email.is_valid())

    def test_course_form_date_validation(self):
        # End date before start date
        form = CourseForm(
            data={
                "course_name": "Invalid Course",
                "course_code": "INV-001",
                "duration_days": 2,
                "duration_hours": 12,
                "start_date": "2026-10-10",
                "end_date": "2026-10-05",
                "status": "active",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("end_date", form.errors)

    def test_student_password_change_form(self):
        form_wrong = StudentPasswordChangeForm(self.student_user, data={"cur": "wrongpw", "new": "newsecret88"})
        self.assertFalse(form_wrong.is_valid())

        form_ok = StudentPasswordChangeForm(
            self.student_user, data={"cur": "studentpassword123", "new": "newsecret88"}
        )
        self.assertTrue(form_ok.is_valid())
        form_ok.save()
        self.student_user.refresh_from_db()
        self.assertTrue(self.student_user.check_password("newsecret88"))


class PermissionAndWorkflowTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_superuser(
            username="adminuser", email="admin@example.com", password="adminpassword123"
        )
        self.student_user = User.objects.create_user(
            username="MTI-2026-0050", email="student1@example.com", password="studentpassword123"
        )
        self.student = Student.objects.create(
            user=self.student_user,
            full_name="Aisha Bello",
            registration_number="MTI-2026-0050",
            email="student1@example.com",
            status="enrolled",
        )
        self.other_user = User.objects.create_user(
            username="MTI-2026-0051", email="other@example.com", password="otherpassword123"
        )
        self.other_student = Student.objects.create(
            user=self.other_user,
            full_name="Tom Becker",
            registration_number="MTI-2026-0051",
            email="other@example.com",
            status="enrolled",
        )
        self.course = Course.objects.create(
            name="Data Analysis with Excel",
            code="CRS-103",
            duration_days=4,
            duration_hours=Decimal("28.0"),
            start_date=datetime.date(2026, 10, 1),
            end_date=datetime.date(2026, 10, 4),
            status="active",
        )
        self.enrollment = Enrollment.objects.create(
            student=self.student,
            course=self.course,
            status="enrolled",
            completion_status="in_progress",
        )
        self.cert = Certificate.objects.create(
            student=self.student,
            course=self.course,
            certificate_type="completion",
            duration_days=4,
            duration_hours=Decimal("28.0"),
            completion_date=datetime.date(2026, 10, 4),
            status="issued",
        )

    def test_unauthenticated_redirects(self):
        resp = self.client.get("/portal/admin/dashboard/")
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp.url.startswith("/?next=") or resp.url == "/")

        resp2 = self.client.get("/portal/student/dashboard/")
        self.assertEqual(resp2.status_code, 302)
        self.assertTrue(resp2.url.startswith("/?next=") or resp2.url == "/")

    def test_student_cannot_access_admin_portal(self):
        self.client.login(username="MTI-2026-0050", password="studentpassword123")
        resp = self.client.get("/portal/admin/dashboard/")
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp.url.startswith("/?next=") or resp.url == "/")

    def test_logout_and_legacy_login_redirect_to_common_login(self):
        # Admin logout redirects to common login '/'
        self.client.login(username="adminuser", password="adminpassword123")
        resp_admin = self.client.get("/portal/logout/")
        self.assertEqual(resp_admin.status_code, 302)
        self.assertEqual(resp_admin.url, "/")

        # Student logout redirects to common login '/'
        self.client.login(username="MTI-2026-0050", password="studentpassword123")
        resp_student = self.client.get("/portal/logout/")
        self.assertEqual(resp_student.status_code, 302)
        self.assertEqual(resp_student.url, "/")

        # Legacy login URLs redirect to common login
        resp_leg_admin = self.client.get("/portal/admin/login/")
        self.assertEqual(resp_leg_admin.status_code, 302)
        self.assertTrue(resp_leg_admin.url.startswith("/?next="))

        resp_leg_student = self.client.get("/portal/student/login/")
        self.assertEqual(resp_leg_student.status_code, 302)
        self.assertTrue(resp_leg_student.url.startswith("/?next="))


    def test_student_cannot_download_other_student_certificate(self):
        # other_user logs in and tries to download self.cert (owned by self.student)
        self.client.login(username="MTI-2026-0051", password="otherpassword123")
        resp = self.client.get(f"/portal/student/certificates/{self.cert.id}/download/")
        self.assertEqual(resp.status_code, 403)

    def test_student_can_download_own_certificate(self):
        self.client.login(username="MTI-2026-0050", password="studentpassword123")
        resp = self.client.get(f"/portal/student/certificates/{self.cert.id}/download/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/pdf")

    def test_admin_course_management_workflow(self):
        self.client.login(username="adminuser", password="adminpassword123")

        # 1. Course List
        resp = self.client.get("/portal/admin/courses/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Data Analysis with Excel")

        # 2. Course Form (New & Edit GET)
        resp_new = self.client.get("/portal/admin/courses/new/")
        self.assertEqual(resp_new.status_code, 200)
        self.assertContains(resp_new, "Add course")

        resp_edit = self.client.get(f"/portal/admin/courses/{self.course.id}/")
        self.assertEqual(resp_edit.status_code, 200)
        self.assertContains(resp_edit, "Edit course")

        # 3. Add Course (POST)
        post_data = {
            "course_name": "Safety Leadership",
            "course_code": "SAF-202",
            "description": "Leadership training for safety supervisors.",
            "duration_days": 2,
            "duration_hours": 16,
            "start_date": "2026-11-01",
            "end_date": "2026-11-02",
            "status": "upcoming",
        }
        resp = self.client.post("/portal/admin/courses/new/", post_data)
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Course.objects.filter(code="SAF-202").exists())

        # 4. Archive Course
        course_saf = Course.objects.get(code="SAF-202")
        resp = self.client.post(f"/portal/admin/courses/{course_saf.id}/archive/")
        self.assertEqual(resp.status_code, 302)
        course_saf.refresh_from_db()
        self.assertEqual(course_saf.status, "archived")

    def test_admin_attendance_marking_workflow(self):
        self.client.login(username="adminuser", password="adminpassword123")

        # GET attendance with existing course
        resp_get = self.client.get("/portal/admin/attendance/")
        self.assertEqual(resp_get.status_code, 200)
        self.assertContains(resp_get, self.course.name)

        # Record daily attendance
        post_data = {
            "topic": "Excel Formulas & Logic",
            "planned_hours": "6.0",
            "actual_hours": "6.0",
            "class_done": "on",
            "att-0": "present",
        }
        resp = self.client.post(
            f"/portal/admin/attendance/?course_id={self.course.id}&date=2026-10-02",
            post_data,
        )
        self.assertEqual(resp.status_code, 302)

        session = CourseSession.objects.filter(course=self.course, date="2026-10-02").first()
        self.assertIsNotNone(session)
        self.assertEqual(session.topic, "Excel Formulas & Logic")

        record = AttendanceRecord.objects.filter(session=session, student=self.student).first()
        self.assertIsNotNone(record)
        self.assertEqual(record.status, "present")

    def test_admin_attendance_with_no_courses(self):
        Course.objects.all().delete()
        self.client.login(username="adminuser", password="adminpassword123")
        resp = self.client.get("/portal/admin/attendance/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "No courses available")

    def test_completion_approval_workflow(self):
        self.client.login(username="adminuser", password="adminpassword123")

        # Create a new enrollment without prior certificate
        new_course = Course.objects.create(
            name="Advanced AI Systems",
            code="CRS-999",
            duration_days=3,
            duration_hours=Decimal("18.0"),
            start_date=datetime.date(2026, 10, 10),
            end_date=datetime.date(2026, 10, 13),
            status="active",
        )
        new_enrollment = Enrollment.objects.create(
            student=self.student,
            course=new_course,
            status="enrolled",
            completion_status="pending",
        )

        # Approve completion
        resp = self.client.post(
            "/portal/admin/approvals/",
            {"enrollment_id": new_enrollment.id, "action": "approve"},
        )
        self.assertEqual(resp.status_code, 302)
        new_enrollment.refresh_from_db()
        self.assertEqual(new_enrollment.completion_status, "approved")
        self.assertEqual(new_enrollment.status, "completed")
        self.assertEqual(new_enrollment.approved_by, self.admin)

        # Verify certificate was automatically generated and issued
        auto_cert = Certificate.objects.filter(enrollment=new_enrollment).first()
        self.assertIsNotNone(auto_cert)
        self.assertEqual(auto_cert.status, "issued")
        self.assertEqual(auto_cert.certificate_type, "completion")
        self.assertEqual(auto_cert.student, self.student)
        self.assertEqual(auto_cert.course, new_course)
        self.assertTrue(bool(auto_cert.pdf_file))

        # Verify student receives/sees certificate immediately
        self.client.login(username="MTI-2026-0050", password="studentpassword123")
        dash_resp = self.client.get("/portal/student/dashboard/")
        self.assertEqual(dash_resp.status_code, 200)
        self.assertContains(dash_resp, auto_cert.certificate_number)

        cert_page_resp = self.client.get("/portal/student/certificates/")
        self.assertEqual(cert_page_resp.status_code, 200)
        self.assertContains(cert_page_resp, auto_cert.certificate_number)

        dl_resp = self.client.get(f"/portal/student/certificates/{auto_cert.id}/download/")
        self.assertEqual(dl_resp.status_code, 200)
        self.assertEqual(dl_resp["Content-Type"], "application/pdf")

        # Test idempotency: approving again doesn't duplicate certificates
        self.client.login(username="adminuser", password="adminpassword123")
        resp_again = self.client.post(
            "/portal/admin/approvals/",
            {"enrollment_id": new_enrollment.id, "action": "approve"},
        )
        self.assertEqual(resp_again.status_code, 302)
        total_certs = Certificate.objects.filter(enrollment=new_enrollment).count()
        self.assertEqual(total_certs, 1)

    def test_certificate_issuance_and_revoke_workflow(self):
        self.client.login(username="adminuser", password="adminpassword123")

        # Generate new achievement certificate
        post_data = {
            "student": self.student.id,
            "course": self.course.id,
            "cert_type": "achievement",
            "achievement_text": "Distinction in Advanced Analytics",
        }
        resp = self.client.post("/portal/admin/certificates/", post_data)
        self.assertEqual(resp.status_code, 302)

        new_cert = Certificate.objects.filter(
            student=self.student,
            course=self.course,
            certificate_type="achievement",
        ).first()
        self.assertIsNotNone(new_cert)
        self.assertEqual(new_cert.status, "issued")
        self.assertEqual(new_cert.achievement_text, "Distinction in Advanced Analytics")

        # Download PDF
        resp_pdf = self.client.get(f"/portal/admin/certificates/{new_cert.id}/download/")
        self.assertEqual(resp_pdf.status_code, 200)
        self.assertEqual(resp_pdf["Content-Type"], "application/pdf")

        # Revoke certificate
        resp_rev = self.client.post(f"/portal/admin/certificates/{new_cert.id}/revoke/")
        self.assertEqual(resp_rev.status_code, 302)
        new_cert.refresh_from_db()
        self.assertEqual(new_cert.status, "revoked")

    def test_public_certificate_verification(self):
        resp = self.client.get(f"/portal/certificates/{self.cert.certificate_number}/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.cert.certificate_number)
        self.assertContains(resp, self.student.full_name)
        self.assertContains(resp, self.course.name)

    def test_student_enrollment_with_custom_credentials(self):
        self.client.login(username="adminuser", password="adminpassword123")
        post_data = {
            "full_name": "Maya Lin",
            "username": "mayalin",
            "email": "maya.lin@example.com",
            "password": "securepassword88",
            "phone": "+1 555 0199",
            "course": self.course.id,
            "enroll_date": "2026-10-15",
        }
        resp = self.client.post("/portal/admin/students/enroll/", post_data)
        self.assertEqual(resp.status_code, 302)

        student = Student.objects.filter(email="maya.lin@example.com").first()
        self.assertIsNotNone(student)
        self.assertIsNotNone(student.user)
        self.assertEqual(student.user.username, "mayalin")
        # Ensure password is securely hashed and not stored in plaintext
        self.assertTrue(student.user.check_password("securepassword88"))
        self.assertNotEqual(student.user.password, "securepassword88")

    def test_student_enrollment_validation_duplicate_username_and_email(self):
        self.client.login(username="adminuser", password="adminpassword123")
        # Attempt to use admin's username
        post_data = {
            "full_name": "Duplicate User",
            "username": "adminuser",
            "email": "unique.dup@example.com",
            "password": "securepassword88",
            "course": self.course.id,
            "enroll_date": "2026-10-15",
        }
        resp = self.client.post("/portal/admin/students/enroll/", post_data)
        self.assertEqual(resp.status_code, 200)
        self.assertFormError(resp.context["form"], "username", "A user with this username already exists. Please choose a different username.")

        # Attempt to use admin's email
        post_data2 = {
            "full_name": "Duplicate Email",
            "username": "uniqueuser123",
            "email": "admin@example.com",
            "password": "securepassword88",
            "course": self.course.id,
            "enroll_date": "2026-10-15",
        }
        resp2 = self.client.post("/portal/admin/students/enroll/", post_data2)
        self.assertEqual(resp2.status_code, 200)
        self.assertFormError(resp2.context["form"], "email", "An account with this email address already exists.")

    def test_admin_reset_student_password(self):
        self.client.login(username="adminuser", password="adminpassword123")
        resp = self.client.post(
            f"/portal/admin/students/{self.student.id}/reset-password/",
            {"new_password": "brandnewpassword99"},
        )
        self.assertEqual(resp.status_code, 302)
        self.student.user.refresh_from_db()
        self.assertTrue(self.student.user.check_password("brandnewpassword99"))

    def test_common_login_username_email_and_role_redirects(self):
        # 1. Login student via username on '/'
        resp1 = self.client.post("/", {"username": "MTI-2026-0050", "password": "studentpassword123"})
        self.assertEqual(resp1.status_code, 302)
        self.assertEqual(resp1.url, "/portal/student/dashboard/")
        self.client.logout()

        # 2. Login student via email on '/'
        resp2 = self.client.post("/", {"username": "student1@example.com", "password": "studentpassword123"})
        self.assertEqual(resp2.status_code, 302)
        self.assertEqual(resp2.url, "/portal/student/dashboard/")
        self.client.logout()

        # 3. Login admin via '/'
        resp3 = self.client.post("/", {"username": "adminuser", "password": "adminpassword123"})
        self.assertEqual(resp3.status_code, 302)
        self.assertEqual(resp3.url, "/portal/admin/dashboard/")
        self.client.logout()

    def test_student_dashboard_certificate_display_and_restrictions(self):
        # Student dashboard with issued certificate
        self.client.login(username="MTI-2026-0050", password="studentpassword123")
        resp = self.client.get("/portal/student/dashboard/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.cert.certificate_number)
        self.assertContains(resp, self.course.name)

        # Revoked certificate should not appear as valid issued certificate
        self.cert.status = "revoked"
        self.cert.save()

        resp2 = self.client.get("/portal/student/dashboard/")
        self.assertEqual(resp2.status_code, 200)
        self.assertNotContains(resp2, self.cert.certificate_number)

        # Revoked certificate cannot be downloaded by student
        resp_dl = self.client.get(f"/portal/student/certificates/{self.cert.id}/download/")
        self.assertEqual(resp_dl.status_code, 403)

    def test_digital_signature_settings_and_snapshot(self):
        self.client.login(username="adminuser", password="adminpassword123")
        from PIL import Image
        from io import BytesIO
        img = Image.new("RGB", (100, 30), color="blue")
        img_io = BytesIO()
        img.save(img_io, format="PNG")
        sig_file = SimpleUploadedFile("sig.png", img_io.getvalue(), content_type="image/png")

        resp = self.client.post(
            "/portal/admin/settings/",
            {
                "name": "Meridian Safety Institute",
                "signatory_name": "Director Sarah Connor",
                "signatory_title": "Executive Director",
                "footer_text": "Official Institute Verification",
                "signature_image": sig_file,
            },
        )
        self.assertEqual(resp.status_code, 302)

        org = OrganizationSettings.get_settings()
        self.assertEqual(org.signatory_name, "Director Sarah Connor")
        self.assertTrue(bool(org.signature_image))

        # Generate a certificate - should snapshot signatory and signature
        new_cert = Certificate.objects.create(
            student=self.student,
            course=self.course,
            completion_date=datetime.date(2026, 10, 4),
            status="issued",
        )
        self.assertEqual(new_cert.signatory_name, "Director Sarah Connor")
        self.assertEqual(new_cert.signatory_title, "Executive Director")
        self.assertTrue(bool(new_cert.signature_url))

        # Now change organization settings
        org.signatory_name = "New Signatory Someone Else"
        org.save()

        # Existing certificate must retain historical snapshot
        new_cert.refresh_from_db()
        self.assertEqual(new_cert.signatory_name, "Director Sarah Connor")

        # Test PDF download with signature
        pdf_buf = generate_certificate_pdf(new_cert)
        pdf_bytes = pdf_buf.getvalue()
        self.assertTrue(pdf_bytes.startswith(b"%PDF-"))

        # Public verification download route
        resp_pub = self.client.get(f"/portal/certificates/{new_cert.certificate_number}/download/")
        self.assertEqual(resp_pub.status_code, 200)
        self.assertEqual(resp_pub["Content-Type"], "application/pdf")

    def test_organization_settings_view_with_and_without_signature_image(self):
        # 1. Test settings view with no signature image
        org = OrganizationSettings.get_settings()
        org.signature_image = None
        org.save()

        self.client.login(username="adminuser", password="adminpassword123")
        resp = self.client.get("/portal/admin/settings/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Organization settings")
        self.assertContains(resp, "No signature uploaded")

        # 2. Upload valid signature image
        from io import BytesIO
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile

        img = Image.new("RGB", (120, 40), color="blue")
        img_io = BytesIO()
        img.save(img_io, format="PNG")
        uploaded_sig = SimpleUploadedFile("new_sig.png", img_io.getvalue(), content_type="image/png")

        post_data = {
            "name": "Updated Academy",
            "signatory_name": "Dr. Updated Signatory",
            "signatory_title": "Dean of Studies",
            "signature_image": uploaded_sig,
            "footer_text": "Updated footer text.",
        }
        resp_post = self.client.post("/portal/admin/settings/", post_data)
        self.assertEqual(resp_post.status_code, 302)

        org.refresh_from_db()
        self.assertEqual(org.name, "Updated Academy")
        self.assertTrue(bool(org.signature_image))
        self.assertTrue(bool(org.signature_image_url))

        # 3. Test settings view with signature image
        resp2 = self.client.get("/portal/admin/settings/")
        self.assertEqual(resp2.status_code, 200)
        self.assertContains(resp2, org.signature_image_url)

        # 4. Security: Student cannot access admin settings
        self.client.login(username=self.student_user.username, password="studentpassword123")
        resp_student = self.client.get("/portal/admin/settings/")
        self.assertEqual(resp_student.status_code, 302)
        self.assertTrue(resp_student.url.startswith("/portal/admin/login/") or resp_student.url.startswith("/"))

    def test_signature_lifecycle_validation_replacement_and_both_cert_types(self):
        from io import BytesIO
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile

        self.client.login(username="adminuser", password="adminpassword123")
        org = OrganizationSettings.get_settings()

        # 1. Validation test: Invalid file extension (e.g. .txt or .pdf)
        invalid_file = SimpleUploadedFile("fake_sig.txt", b"not an image", content_type="text/plain")
        resp_inv = self.client.post("/portal/admin/settings/", {
            "name": org.name,
            "signatory_name": "Test Signatory",
            "signatory_title": "Test Title",
            "signature_image": invalid_file,
        })
        self.assertEqual(resp_inv.status_code, 200)
        self.assertContains(resp_inv, "Signature must be a PNG or JPG image file.")

        # 2. Validation test: Fake image (png extension but corrupted/invalid content)
        corrupted_file = SimpleUploadedFile("corrupted.png", b"corrupted bytes", content_type="image/png")
        resp_corrupt = self.client.post("/portal/admin/settings/", {
            "name": org.name,
            "signatory_name": "Test Signatory",
            "signatory_title": "Test Title",
            "signature_image": corrupted_file,
        })
        self.assertEqual(resp_corrupt.status_code, 200)
        self.assertContains(resp_corrupt, "The uploaded signature file is not a valid image.")

        # 3. Validation test: File size exceeding 5MB
        oversized_file = SimpleUploadedFile("huge.png", b"x" * (5 * 1024 * 1024 + 10), content_type="image/png")
        resp_huge = self.client.post("/portal/admin/settings/", {
            "name": org.name,
            "signatory_name": "Test Signatory",
            "signatory_title": "Test Title",
            "signature_image": oversized_file,
        })
        self.assertEqual(resp_huge.status_code, 200)
        self.assertContains(resp_huge, "Signature image file size must not exceed 5MB.")

        # 4. Upload valid JPEG signature
        img_jpg = Image.new("RGB", (150, 50), color="white")
        buf_jpg = BytesIO()
        img_jpg.save(buf_jpg, format="JPEG")
        jpg_sig = SimpleUploadedFile("auth_sig.jpg", buf_jpg.getvalue(), content_type="image/jpeg")

        resp_upload_jpg = self.client.post("/portal/admin/settings/", {
            "name": "Acme Institute",
            "signatory_name": "Dr. Arthur Pendelton",
            "signatory_title": "Chief Academic Officer",
            "signature_image": jpg_sig,
            "footer_text": "Official verification statement.",
        })
        self.assertEqual(resp_upload_jpg.status_code, 302)

        org.refresh_from_db()
        self.assertTrue(bool(org.signature_image))
        self.assertEqual(org.signatory_name, "Dr. Arthur Pendelton")
        first_sig_url = org.signature_image_url

        # Check settings view renders preview and replace button
        resp_view = self.client.get("/portal/admin/settings/")
        self.assertEqual(resp_view.status_code, 200)
        self.assertContains(resp_view, first_sig_url)
        self.assertContains(resp_view, "Replace signature")
        self.assertContains(resp_view, "Remove")

        # 5. Issue Completion Certificate and Achievement Certificate with this signature
        comp_cert = Certificate.objects.create(
            student=self.student,
            course=self.course,
            certificate_type="completion",
            completion_date=datetime.date(2026, 10, 5),
            status="issued",
        )
        self.assertEqual(comp_cert.signatory_name, "Dr. Arthur Pendelton")
        self.assertEqual(comp_cert.signatory_title, "Chief Academic Officer")
        self.assertTrue(bool(comp_cert.signature_url))

        ach_cert = Certificate.objects.create(
            student=self.student,
            course=self.course,
            certificate_type="achievement",
            achievement_text="Distinction in Technical Excellence",
            completion_date=datetime.date(2026, 10, 5),
            status="issued",
        )
        self.assertEqual(ach_cert.signatory_name, "Dr. Arthur Pendelton")
        self.assertEqual(ach_cert.signatory_title, "Chief Academic Officer")
        self.assertTrue(bool(ach_cert.signature_url))

        # Test PDF rendering for both certificates with signature
        pdf_comp = generate_certificate_pdf(comp_cert)
        self.assertTrue(pdf_comp.getvalue().startswith(b"%PDF-"))
        self.assertGreater(len(pdf_comp.getvalue()), 1000)

        pdf_ach = generate_certificate_pdf(ach_cert)
        self.assertTrue(pdf_ach.getvalue().startswith(b"%PDF-"))
        self.assertGreater(len(pdf_ach.getvalue()), 1000)

        # 6. Replace signature with valid PNG
        img_png = Image.new("RGBA", (140, 45), color=(0, 0, 0, 0))
        buf_png = BytesIO()
        img_png.save(buf_png, format="PNG")
        png_sig = SimpleUploadedFile("new_replacement.png", buf_png.getvalue(), content_type="image/png")

        resp_replace = self.client.post("/portal/admin/settings/", {
            "name": "Acme Institute",
            "signatory_name": "Prof. Beatrice Vance",
            "signatory_title": "Dean of Engineering",
            "signature_image": png_sig,
            "footer_text": "Official verification statement.",
        })
        self.assertEqual(resp_replace.status_code, 302)

        org.refresh_from_db()
        self.assertEqual(org.signatory_name, "Prof. Beatrice Vance")
        self.assertIn("new_replacement", org.signature_image.name)

        # Previously issued certificates MUST retain their snapshotted signature & signatory
        comp_cert.refresh_from_db()
        ach_cert.refresh_from_db()
        self.assertEqual(comp_cert.signatory_name, "Dr. Arthur Pendelton")
        self.assertEqual(ach_cert.signatory_name, "Dr. Arthur Pendelton")
        self.assertEqual(comp_cert.signatory_title, "Chief Academic Officer")
        self.assertIn("auth_sig", comp_cert.signature_url)
        self.assertIn("auth_sig", ach_cert.signature_url)

        # 7. Remove signature
        resp_remove = self.client.post("/portal/admin/settings/", {
            "name": "Acme Institute",
            "signatory_name": "Prof. Beatrice Vance",
            "signatory_title": "Dean of Engineering",
            "remove_signature": "1",
            "footer_text": "Official verification statement.",
        })
        self.assertEqual(resp_remove.status_code, 302)

        org.refresh_from_db()
        self.assertFalse(bool(org.signature_image))
        self.assertEqual(org.signature_image_url, "")

        # Settings view now displays placeholder and "Choose signature image"
        resp_view_empty = self.client.get("/portal/admin/settings/")
        self.assertEqual(resp_view_empty.status_code, 200)
        self.assertContains(resp_view_empty, "No signature uploaded")
        self.assertContains(resp_view_empty, "Choose signature image")

        # 8. Issue a certificate with NO signature; ensure both Completion & Achievement PDFs render cleanly
        no_sig_comp = Certificate.objects.create(
            student=self.student,
            course=self.course,
            certificate_type="completion",
            completion_date=datetime.date(2026, 10, 6),
            status="issued",
        )
        self.assertEqual(no_sig_comp.signature_url, "")
        pdf_no_sig_comp = generate_certificate_pdf(no_sig_comp)
        self.assertTrue(pdf_no_sig_comp.getvalue().startswith(b"%PDF-"))

        no_sig_ach = Certificate.objects.create(
            student=self.student,
            course=self.course,
            certificate_type="achievement",
            completion_date=datetime.date(2026, 10, 6),
            status="issued",
        )
        self.assertEqual(no_sig_ach.signature_url, "")
        pdf_no_sig_ach = generate_certificate_pdf(no_sig_ach)
        self.assertTrue(pdf_no_sig_ach.getvalue().startswith(b"%PDF-"))

        # Previously issued certificates with signatures still render their snapshot PDFs
        pdf_orig_comp = generate_certificate_pdf(comp_cert)
        self.assertTrue(pdf_orig_comp.getvalue().startswith(b"%PDF-"))

    def test_student_management_detail_view(self):
        self.client.login(username="adminuser", password="adminpassword123")
        resp = self.client.get(f"/portal/admin/students/{self.student.id}/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.student.full_name)
        self.assertContains(resp, self.student.registration_number)
        self.assertContains(resp, self.student.email)
        self.assertContains(resp, self.course.name)
        self.assertContains(resp, "Attendance summary")
        self.assertContains(resp, "Completion status")
        self.assertContains(resp, "Account &amp; Security")
        self.assertContains(resp, f"/portal/admin/students/{self.student.id}/edit/")
        self.assertContains(resp, f"/portal/admin/students/{self.student.id}/delete/")

        # Student cannot access admin student detail
        self.client.login(username=self.student_user.username, password="studentpassword123")
        resp_unauth = self.client.get(f"/portal/admin/students/{self.student.id}/")
        self.assertEqual(resp_unauth.status_code, 302)

    def test_student_management_update_and_preservation(self):
        self.client.login(username="adminuser", password="adminpassword123")

        # Set initial phone on student
        self.student.phone = "+1 555-4321"
        self.student.save()

        # Update student details, leaving phone blank to test preservation
        edit_data = {
            "full_name": "Aisha Bello Updated",
            "email": "aisha.updated@example.com",
            "username": "aishaupdated",
            "phone": "",  # Optional: must preserve existing phone
            "status": "completed",
            "new_password": "",  # Blank: must preserve existing password
        }
        resp = self.client.post(f"/portal/admin/students/{self.student.id}/edit/", edit_data)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, f"/portal/admin/students/{self.student.id}/")

        self.student.refresh_from_db()
        self.assertEqual(self.student.full_name, "Aisha Bello Updated")
        self.assertEqual(self.student.email, "aisha.updated@example.com")
        self.assertEqual(self.student.phone, "+1 555-4321")  # Preserved!
        self.assertEqual(self.student.status, "completed")
        self.assertEqual(self.student.user.username, "aishaupdated")
        self.assertTrue(self.student.user.check_password("studentpassword123"))  # Password preserved!

        # Test duplicate username rejection on edit
        edit_dup_username = {
            "full_name": "Aisha Bello Updated",
            "email": "aisha.updated@example.com",
            "username": "adminuser",  # Duplicate!
            "status": "completed",
        }
        resp_dup = self.client.post(f"/portal/admin/students/{self.student.id}/edit/", edit_dup_username)
        self.assertEqual(resp_dup.status_code, 200)
        self.assertFormError(resp_dup.context["form"], "username", "A user with this username already exists. Please choose a different username.")

        # Test duplicate email rejection on edit
        edit_dup_email = {
            "full_name": "Aisha Bello Updated",
            "email": "admin@example.com",  # Duplicate!
            "username": "aishaupdated",
            "status": "completed",
        }
        resp_dup2 = self.client.post(f"/portal/admin/students/{self.student.id}/edit/", edit_dup_email)
        self.assertEqual(resp_dup2.status_code, 200)
        self.assertFormError(resp_dup2.context["form"], "email", "An account with this email address already exists.")

    def test_student_management_delete_and_deactivate_workflow(self):
        self.client.login(username="adminuser", password="adminpassword123")

        # GET confirmation page
        resp_get = self.client.get(f"/portal/admin/students/{self.student.id}/delete/")
        self.assertEqual(resp_get.status_code, 200)
        self.assertContains(resp_get, "Manage student record")
        self.assertContains(resp_get, "Deactivate Student (Recommended)")
        self.assertContains(resp_get, "Permanent Deletion")
        self.assertContains(resp_get, "Database Foreign Key Rules")

        # 1. Test Deactivation workflow
        resp_deact = self.client.post(
            f"/portal/admin/students/{self.student.id}/delete/",
            {"action": "deactivate"},
        )
        self.assertEqual(resp_deact.status_code, 302)
        self.student.refresh_from_db()
        self.assertEqual(self.student.status, "inactive")
        self.assertFalse(self.student.user.is_active)
        # Ensure related records are preserved
        self.assertEqual(self.student.enrollments.count(), 1)
        self.assertEqual(self.student.certificates.count(), 1)

        # 2. Test Permanent Delete restriction when student has issued certificates without confirmation
        resp_blocked = self.client.post(
            f"/portal/admin/students/{self.student.id}/delete/",
            {"action": "delete"},  # Missing confirm_permanent_delete
        )
        self.assertEqual(resp_blocked.status_code, 200)
        self.assertTrue(Student.objects.filter(pk=self.student.id).exists())

        # 3. Test Permanent Delete with explicit confirmation
        resp_del = self.client.post(
            f"/portal/admin/students/{self.student.id}/delete/",
            {"action": "delete", "confirm_permanent_delete": "1"},
        )
        self.assertEqual(resp_del.status_code, 302)
        self.assertEqual(resp_del.url, "/portal/admin/students/")
        self.assertFalse(Student.objects.filter(pk=self.student.id).exists())

