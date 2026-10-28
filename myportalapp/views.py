import json
from decimal import Decimal
from functools import wraps
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import Http404, HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import (
    AdminLoginForm,
    CertificateGenerationForm,
    CommonLoginForm,
    CourseForm,
    OrganizationSettingsForm,
    StudentEditForm,
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


# ==============================================================================
# Permission Decorators
# ==============================================================================

def admin_required(view_func):
    """
    Ensures the user is authenticated and has administrative rights.
    """
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"/?next={request.path}")
        if not (request.user.is_staff or request.user.is_superuser):
            messages.error(request, "Access denied. Administrator privileges required.")
            return redirect("/")
        return view_func(request, *args, **kwargs)
    return _wrapped


def student_required(view_func):
    """
    Ensures the user is authenticated and has an associated Student profile.
    """
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"/?next={request.path}")
        if not hasattr(request.user, "student_profile") or request.user.student_profile is None:
            messages.error(request, "Access denied. Student portal account required.")
            return redirect("/")
        return view_func(request, *args, **kwargs)
    return _wrapped


# ==============================================================================
# Root & Auth Views
# ==============================================================================

def index_redirect(request):
    """
    Root '/' — serves the common login page; authenticated users go to their dashboard.
    """
    if request.user.is_authenticated:
        if request.user.is_staff or request.user.is_superuser:
            return redirect("/portal/admin/dashboard/")
        if hasattr(request.user, "student_profile") and request.user.student_profile:
            return redirect("/portal/student/dashboard/")

    return common_login(request)


def common_login(request):
    """
    Unified login view — single page for both admins and students.
    After authentication the user is redirected to the correct role dashboard.
    """
    if request.user.is_authenticated:
        if request.user.is_staff or request.user.is_superuser:
            return redirect("/portal/admin/dashboard/")
        if hasattr(request.user, "student_profile") and request.user.student_profile:
            return redirect("/portal/student/dashboard/")

    next_url = request.GET.get("next", "").strip()

    if request.method == "POST":
        form = CommonLoginForm(request.POST)
        if form.is_valid():
            user = form.cleaned_data["user"]
            role = form.cleaned_data["role"]
            login(request, user)
            if not form.cleaned_data.get("remember"):
                request.session.set_expiry(0)
            if next_url:
                if role == "student" and "/portal/admin/" in next_url:
                    next_url = "/portal/student/dashboard/"
                elif role == "admin" and "/portal/student/" in next_url:
                    next_url = "/portal/admin/dashboard/"
                return redirect(next_url)
            if role == "admin":
                messages.success(request, f"Welcome back, {user.first_name or user.username}!")
                return redirect("/portal/admin/dashboard/")
            else:
                messages.success(request, f"Welcome back, {user.student_profile.first_name}!")
                return redirect("/portal/student/dashboard/")
        else:
            for error in form.non_field_errors():
                messages.error(request, error)
    else:
        form = CommonLoginForm()

    return render(request, "common_login.html", {"form": form, "next": next_url})


def admin_login(request):
    """
    Redirects legacy admin login route to the unified common login.
    """
    next_url = request.GET.get("next") or "/portal/admin/dashboard/"
    return redirect(f"/?next={next_url}" if next_url else "/")


def student_login(request):
    """
    Redirects legacy student login route to the unified common login.
    """
    next_url = request.GET.get("next") or "/portal/student/dashboard/"
    return redirect(f"/?next={next_url}" if next_url else "/")


def portal_logout(request):
    """
    Logs out the user and redirects to the common login page.
    """
    logout(request)
    messages.info(request, "You have been signed out.")
    return redirect("/")


# ==============================================================================
# Admin Portal Views
# ==============================================================================

@admin_required
def admin_dashboard(request):
    """
    Admin dashboard displaying live stats, trend charts, recent enrollments,
    upcoming sessions, and pending completion approvals.
    """
    total_courses = Course.objects.count()
    active_students = Student.objects.filter(status="enrolled").count()
    enrolled_students = Enrollment.objects.filter(status="enrolled").count()
    certificates_issued = Certificate.objects.filter(status="issued").count()

    # Recent enrollments
    recent_enrollments = (
        Enrollment.objects.select_related("student", "course")
        .order_by("-created_at")[:5]
    )

    # Upcoming sessions (from today onwards or most recent)
    today = timezone.now().date()
    upcoming_sessions = (
        CourseSession.objects.select_related("course")
        .filter(date__gte=today)
        .order_by("date")[:5]
    )
    if not upcoming_sessions.exists():
        upcoming_sessions = (
            CourseSession.objects.select_related("course")
            .order_by("-date")[:5]
        )

    # Pending approvals
    pending_approvals = (
        Enrollment.objects.select_related("student", "course")
        .filter(completion_status="pending")
        .order_by("-created_at")[:5]
    )

    # Monthly enrollment trend (past 10 months of current year)
    current_year = today.year
    months_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    monthly_counts = [0] * 12
    enrollments_this_year = Enrollment.objects.filter(enrollment_date__year=current_year)
    for e in enrollments_this_year:
        m_idx = e.enrollment_date.month - 1
        if 0 <= m_idx < 12:
            monthly_counts[m_idx] += 1

    # Truncate up to current month (at least Jan-Oct)
    end_month = max(10, today.month)
    enrollment_trend = {
        "labels": months_labels[:end_month],
        "counts": monthly_counts[:end_month],
    }

    # Certificate types breakdown
    completion_count = Certificate.objects.filter(certificate_type="completion", status="issued").count()
    achievement_count = Certificate.objects.filter(certificate_type="achievement", status="issued").count()

    context = {
        "total_courses": total_courses,
        "active_students": active_students,
        "enrolled_students": enrolled_students,
        "certificates_issued": certificates_issued,
        "recent_enrollments": recent_enrollments,
        "upcoming_sessions": upcoming_sessions,
        "pending_approvals": pending_approvals,
        "enrollment_trend": enrollment_trend,
        "completion_count": completion_count,
        "achievement_count": achievement_count,
    }
    return render(request, "admin/dashboard.html", context)


@admin_required
def course_list(request):
    """
    List of training courses with enrolled count annotations and filters.
    """
    courses = Course.objects.annotate(
        total_enrolled=Count(
            "enrollments",
            filter=Q(enrollments__status__in=["enrolled", "completed"]),
        )
    ).order_by("name")

    return render(request, "admin/courses.html", {"courses": courses})


@admin_required
def course_create(request):
    """
    Create a new course.
    """
    if request.method == "POST":
        form = CourseForm(request.POST)
        if form.is_valid():
            course = form.save()
            messages.success(request, f"Course '{course.name}' created successfully.")
            return redirect("/portal/admin/courses/")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = CourseForm()

    return render(request, "admin/course_form.html", {"form": form, "is_edit": False})


@admin_required
def course_edit(request, course_id):
    """
    Edit an existing course.
    """
    course = get_object_or_404(Course, pk=course_id)
    if request.method == "POST":
        form = CourseForm(request.POST, instance=course)
        if form.is_valid():
            form.save()
            messages.success(request, f"Course '{course.name}' updated successfully.")
            return redirect("/portal/admin/courses/")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = CourseForm(instance=course)

    return render(request, "admin/course_form.html", {"form": form, "course": course, "is_edit": True})


@admin_required
@require_POST
def course_archive(request, course_id):
    """
    Archives a course.
    """
    course = get_object_or_404(Course, pk=course_id)
    course.status = "archived" if course.status != "archived" else "active"
    course.save(update_fields=["status"])
    messages.success(request, f"Course '{course.name}' status updated to {course.status}.")
    return redirect("/portal/admin/courses/")


@admin_required
def student_list(request):
    """
    List all students with progress and enrollment status.
    """
    students = (
        Student.objects.prefetch_related("enrollments__course")
        .all()
        .order_by("-created_at")
    )
    return render(request, "admin/students.html", {"students": students})


@admin_required
def student_enroll(request):
    """
    Enroll student form: registers student (if new) and links to a course.
    """
    courses = Course.objects.filter(status__in=["active", "upcoming"]).order_by("name")
    suggested_reg = Student.generate_registration_number()

    if request.method == "POST":
        form = StudentEnrollmentForm(request.POST)
        if form.is_valid():
            full_name = form.cleaned_data["full_name"]
            email = form.cleaned_data["email"].strip().lower()
            phone = form.cleaned_data.get("phone", "")
            course = form.cleaned_data["course"]
            enroll_date = form.cleaned_data["enroll_date"]
            chosen_username = form.cleaned_data.get("username", "").strip()
            chosen_password = form.cleaned_data.get("password", "")

            # Find or create student
            student = Student.objects.filter(email__iexact=email).first()
            if not student:
                student = Student.objects.create(
                    full_name=full_name,
                    email=email,
                    phone=phone,
                    registration_number=suggested_reg,
                    status="enrolled",
                )
            else:
                student.full_name = full_name
                if phone:
                    student.phone = phone
                student.save()

            # Ensure linked User account exists for student portal access
            username = chosen_username or student.registration_number
            initial_password = chosen_password or student.registration_number.lower()

            if not student.user:
                if User.objects.filter(username__iexact=username).exists():
                    username = student.registration_number
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=initial_password,
                    first_name=student.first_name,
                )
                student.user = user
                student.save(update_fields=["user"])
            else:
                if chosen_username and student.user.username != chosen_username:
                    student.user.username = chosen_username
                if chosen_password:
                    student.user.set_password(chosen_password)
                student.user.email = email
                student.user.save()

            # Create or update enrollment
            enrollment, created = Enrollment.objects.get_or_create(
                student=student,
                course=course,
                defaults={"enrollment_date": enroll_date, "status": "enrolled", "completion_status": "in_progress"},
            )
            if not created:
                enrollment.status = "enrolled"
                enrollment.enrollment_date = enroll_date
                enrollment.save()

            messages.success(request, f"{student.full_name} enrolled in {course.name}.")
            return redirect("/portal/admin/students/")
        else:
            messages.error(request, "Please fix the highlighted fields.")
    else:
        form = StudentEnrollmentForm(initial={"enroll_date": timezone.now().date()})

    context = {
        "form": form,
        "courses": courses,
        "suggested_reg": suggested_reg,
    }
    return render(request, "admin/enrollment_form.html", context)


@admin_required
@require_POST
def student_reset_password(request, student_id):
    """
    Securely sets a new password for a student account without exposing the current password.
    """
    student = get_object_or_404(Student, pk=student_id)
    new_password = request.POST.get("new_password", "").strip()

    if len(new_password) < 8:
        messages.error(request, "Password must be at least 8 characters long.")
        return redirect(f"/portal/admin/students/{student.id}/")

    if not student.user:
        username = student.registration_number
        user = User.objects.create_user(
            username=username,
            email=student.email,
            password=new_password,
            first_name=student.first_name,
        )
        student.user = user
        student.save(update_fields=["user"])
    else:
        student.user.set_password(new_password)
        student.user.save()

    messages.success(request, f"Password for {student.full_name} has been reset successfully.")
    return redirect(f"/portal/admin/students/{student.id}/")


@admin_required
def student_detail(request, student_id):
    """
    Detailed profile of a student, showing enrolled courses, progress,
    attendance summary, and certificates.
    """
    student = get_object_or_404(
        Student.objects.prefetch_related(
            "enrollments__course",
            "enrollments__attendance_records__session",
            "certificates__course",
        ),
        pk=student_id,
    )

    primary_enrollment = student.enrollments.first()
    attendance_summary = primary_enrollment.get_attendance_summary() if primary_enrollment else {
        "present": 0, "absent": 0, "leave": 0, "total": 0, "rate": 0
    }
    completed_hours = primary_enrollment.get_completed_hours() if primary_enrollment else Decimal("0.0")

    context = {
        "student": student,
        "primary_enrollment": primary_enrollment,
        "attendance_summary": attendance_summary,
        "completed_hours": completed_hours,
        "certificates": student.certificates.all(),
    }
    return render(request, "admin/student_detail.html", context)


@admin_required
def student_edit(request, student_id):
    """
    Update student details including personal info, portal credentials, and status.
    """
    student = get_object_or_404(Student, pk=student_id)
    if request.method == "POST":
        form = StudentEditForm(student, request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, f"Student '{student.full_name}' updated successfully.")
            return redirect(f"/portal/admin/students/{student.id}/")
        else:
            messages.error(request, "Please correct the highlighted errors.")
    else:
        form = StudentEditForm(student)

    return render(request, "admin/student_form.html", {"form": form, "student": student})


@admin_required
def student_delete(request, student_id):
    """
    Safe deletion or deactivation workflow with confirmation.
    Explains foreign-key CASCADE impact and preserves official certificate records.
    """
    student = get_object_or_404(Student, pk=student_id)
    enrollments = student.enrollments.select_related("course").all()
    attendance_count = student.attendance_records.count()
    certificates = student.certificates.all()
    issued_certificates_count = certificates.filter(status="issued").count()
    has_issued_certificates = issued_certificates_count > 0

    if request.method == "POST":
        action = request.POST.get("action", "deactivate")
        if action == "deactivate":
            student.status = "inactive"
            student.save(update_fields=["status"])
            if student.user:
                student.user.is_active = False
                student.user.save(update_fields=["is_active"])
            messages.success(
                request,
                f"Student '{student.full_name}' was successfully deactivated. Historical records and certificates have been preserved.",
            )
            return redirect(f"/portal/admin/students/{student.id}/")
        elif action == "delete":
            confirm_permanent = request.POST.get("confirm_permanent_delete")
            if has_issued_certificates and not confirm_permanent:
                messages.error(
                    request,
                    "Cannot delete a student with issued certificates without checking the confirmation box acknowledging permanent loss of official certificate records.",
                )
            else:
                student_name = student.full_name
                user = student.user
                student.delete()
                if user:
                    user.delete()
                messages.success(
                    request,
                    f"Student '{student_name}' and all associated records have been permanently deleted.",
                )
                return redirect("/portal/admin/students/")

    context = {
        "student": student,
        "enrollments": enrollments,
        "attendance_count": attendance_count,
        "certificates": certificates,
        "issued_certificates_count": issued_certificates_count,
        "has_issued_certificates": has_issued_certificates,
    }
    return render(request, "admin/student_confirm_delete.html", context)


@admin_required
def admin_attendance(request):
    """
    Record and view daily attendance for a selected course session.
    """
    courses = Course.objects.filter(status__in=["active", "upcoming"]).order_by("name")
    selected_course_id = request.GET.get("course_id") or (str(courses.first().pk) if courses.exists() else None)
    selected_date_str = request.GET.get("date") or timezone.now().date().isoformat()

    selected_course = None
    if selected_course_id:
        selected_course = Course.objects.filter(pk=selected_course_id).first()

    session = None
    if selected_course:
        session = CourseSession.objects.filter(course=selected_course, date=selected_date_str).first()

    # Roster of enrolled students
    enrollments = []
    if selected_course:
        enrollments = (
            Enrollment.objects.filter(course=selected_course, status__in=["enrolled", "completed"])
            .select_related("student")
            .order_by("student__full_name")
        )

    if request.method == "POST":
        topic = request.POST.get("topic", "").strip() or "Course Session"
        planned_hours = Decimal(request.POST.get("planned_hours") or "6.0")
        actual_hours = Decimal(request.POST.get("actual_hours") or "6.0")
        is_completed = request.POST.get("class_done") in ("on", "true", "1")

        if not selected_course:
            messages.error(request, "Please select a course.")
            return redirect("/portal/admin/attendance/")

        # Create or update session
        session, _ = CourseSession.objects.update_or_create(
            course=selected_course,
            date=selected_date_str,
            defaults={
                "topic": topic,
                "planned_hours": planned_hours,
                "actual_hours": actual_hours,
                "is_completed": is_completed,
            },
        )

        # Update attendance records for each student
        for idx, enr in enumerate(enrollments):
            field_name = f"att-{idx}"
            status = request.POST.get(field_name, "present")
            AttendanceRecord.objects.update_or_create(
                session=session,
                student=enr.student,
                defaults={"enrollment": enr, "status": status},
            )
            # Check and sync completion status
            enr.sync_completion_status()

        messages.success(request, f"Attendance saved for {selected_course.name} on {selected_date_str}.")
        return redirect(f"/portal/admin/attendance/?course_id={selected_course.pk}&date={selected_date_str}")

    # Build student row state
    roster = []
    present_cnt = 0
    absent_cnt = 0
    leave_cnt = 0

    for idx, enr in enumerate(enrollments):
        existing_rec = None
        if session:
            existing_rec = AttendanceRecord.objects.filter(session=session, student=enr.student).first()

        current_status = existing_rec.status if existing_rec else "present"
        if current_status == "present":
            present_cnt += 1
        elif current_status == "absent":
            absent_cnt += 1
        elif current_status == "leave":
            leave_cnt += 1

        roster.append({
            "idx": idx,
            "enrollment": enr,
            "student": enr.student,
            "status": current_status,
            "overall_attendance": enr.attendance_percent,
        })

    total_marked = len(roster)
    today_rate = round((present_cnt / total_marked) * 100) if total_marked > 0 else 0

    planned_hours = (
        session.planned_hours
        if session and session.planned_hours is not None
        else (selected_course.duration_hours if selected_course and selected_course.duration_hours is not None else Decimal("6.0"))
    )

    context = {
        "courses": courses,
        "selected_course": selected_course,
        "selected_date": selected_date_str,
        "session": session,
        "planned_hours": planned_hours,
        "roster": roster,
        "sum_present": present_cnt,
        "sum_absent": absent_cnt,
        "sum_leave": leave_cnt,
        "sum_rate": today_rate,
    }
    return render(request, "admin/attendance.html", context)


@admin_required
def completion_approvals(request):
    """
    Review completion requests for students meeting attendance & hour criteria.
    Supports approval and rejection workflows.
    """
    if request.method == "POST":
        enrollment_id = request.POST.get("enrollment_id")
        action = request.POST.get("action")
        enrollment = get_object_or_404(Enrollment, pk=enrollment_id)

        if action == "approve":
            enrollment.completion_status = "approved"
            enrollment.status = "completed"
            enrollment.approved_by = request.user
            enrollment.approved_at = timezone.now()
            if not enrollment.completion_date:
                enrollment.completion_date = timezone.now().date()
            enrollment.save()

            try:
                cert = enrollment.generate_completion_certificate()
                messages.success(
                    request,
                    f"Completion approved! Certificate {cert.certificate_number} has been automatically generated and issued for {enrollment.student.full_name}.",
                )
            except Exception as e:
                messages.warning(
                    request,
                    f"Completion approved for {enrollment.student.full_name}, but certificate generation encountered: {e}",
                )
        elif action == "reject":
            enrollment.completion_status = "rejected"
            enrollment.save(update_fields=["completion_status"])
            messages.error(request, f"Completion rejected for {enrollment.student.full_name}.")
        return redirect("/portal/admin/approvals/")

    requests = (
        Enrollment.objects.filter(completion_status__in=["pending", "approved", "rejected"])
        .select_related("student", "course")
        .prefetch_related("certificates")
        .order_by("-enrollment_date")
    )
    return render(request, "admin/completion_approvals.html", {"requests": requests})


@admin_required
def certificate_center(request):
    """
    Manage issued certificates and generate new completion/achievement certificates.
    """
    # Eligible students (those with approved completions or active enrollments)
    students = Student.objects.all().order_by("full_name")
    courses = Course.objects.all().order_by("name")
    certificates = Certificate.objects.select_related("student", "course").order_by("-created_at")

    if request.method == "POST":
        form = CertificateGenerationForm(request.POST)
        if form.is_valid():
            student = form.cleaned_data["student"]
            course = form.cleaned_data["course"]
            cert_type = form.cleaned_data["cert_type"]
            achievement_text = form.cleaned_data["achievement_text"]

            enrollment = Enrollment.objects.filter(student=student, course=course).first()
            completion_date = (
                enrollment.completion_date if (enrollment and enrollment.completion_date) else timezone.now().date()
            )

            # Create Certificate record
            cert = Certificate(
                student=student,
                course=course,
                enrollment=enrollment,
                certificate_type=cert_type,
                achievement_text=achievement_text,
                duration_days=course.duration_days,
                duration_hours=course.duration_hours,
                completion_date=completion_date,
                issue_date=timezone.now().date(),
                status="issued",
            )
            cert.save()

            # Render server-side PDF with ReportLab and store to media
            try:
                save_certificate_pdf(cert)
            except Exception as e:
                # PDF generation error shouldn't crash the database save, but inform admin
                messages.warning(request, f"Certificate record created, but PDF rendering encountered: {e}")
            else:
                messages.success(request, f"Certificate {cert.certificate_number} generated successfully.")

            return redirect("/portal/admin/certificates/")
        else:
            messages.error(request, "Please fix the certificate generation form errors.")
    else:
        form = CertificateGenerationForm()

    context = {
        "form": form,
        "students": students,
        "courses": courses,
        "certificates": certificates,
    }
    return render(request, "admin/certificates.html", context)


@admin_required
def certificate_download(request, certificate_id):
    """
    Generates and returns the Certificate PDF file for download.
    """
    cert = get_object_or_404(Certificate.objects.select_related("student", "course"), pk=certificate_id)
    buffer = generate_certificate_pdf(cert)
    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    filename = f"{cert.certificate_number}.pdf"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@admin_required
@require_POST
def certificate_revoke(request, certificate_id):
    """
    Revokes or restores an issued certificate.
    """
    cert = get_object_or_404(Certificate, pk=certificate_id)
    cert.status = "revoked" if cert.status == "issued" else "issued"
    cert.save(update_fields=["status"])
    # Regenerate PDF with REVOKED watermark if revoked
    save_certificate_pdf(cert)
    messages.success(request, f"Certificate {cert.certificate_number} status set to {cert.status}.")
    return redirect("/portal/admin/certificates/")


@admin_required
def organization_settings_view(request):
    """
    Manage organization branding, logo upload, and signatory information.
    """
    settings_obj = OrganizationSettings.get_settings()

    if request.method == "POST":
        form = OrganizationSettingsForm(request.POST, request.FILES, instance=settings_obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Organization settings saved successfully.")
            return redirect("/portal/admin/settings/")
        else:
            messages.error(request, "Please correct the highlighted errors.")
    else:
        form = OrganizationSettingsForm(instance=settings_obj)

    return render(
        request,
        "admin/settings.html",
        {
            "form": form,
            "settings": settings_obj,
            "signature_image_url": settings_obj.signature_image_url,
        },
    )


# ==============================================================================
# Student Portal Views
# ==============================================================================

@student_required
def student_dashboard(request):
    """
    Student dashboard displaying active enrollments, course progress,
    recent attendance, and latest certificate.
    """
    student = request.user.student_profile
    enrollments = (
        Enrollment.objects.filter(student=student)
        .select_related("course")
        .order_by("-enrollment_date")
    )
    recent_attendance = (
        AttendanceRecord.objects.filter(student=student)
        .select_related("session")
        .order_by("-session__date")[:5]
    )
    latest_certificate = (
        Certificate.objects.filter(student=student, status="issued")
        .select_related("course")
        .order_by("-issue_date")
        .first()
    )

    context = {
        "student": student,
        "enrollments": enrollments,
        "recent_attendance": recent_attendance,
        "latest_certificate": latest_certificate,
    }
    return render(request, "student/dashboard.html", context)


@student_required
def student_courses(request):
    """
    Lists all courses the logged-in student is enrolled in.
    """
    student = request.user.student_profile
    enrollments = (
        Enrollment.objects.filter(student=student)
        .select_related("course")
        .order_by("-enrollment_date")
    )
    return render(request, "student/my_courses.html", {"enrollments": enrollments, "student": student})


@student_required
def student_attendance(request):
    """
    Lists attendance history and attendance percentage for the logged-in student.
    """
    student = request.user.student_profile
    records = (
        AttendanceRecord.objects.filter(student=student)
        .select_related("session__course")
        .order_by("-session__date")
    )

    present_count = records.filter(status="present").count()
    absent_count = records.filter(status="absent").count()
    leave_count = records.filter(status="leave").count()
    total_count = records.count()
    rate = round((present_count / total_count) * 100) if total_count > 0 else 0

    context = {
        "student": student,
        "records": records,
        "present_count": present_count,
        "absent_count": absent_count,
        "leave_count": leave_count,
        "total_count": total_count,
        "rate": rate,
    }
    return render(request, "student/attendance.html", context)


@student_required
def student_certificates(request):
    """
    Lists all certificates earned by the logged-in student.
    """
    student = request.user.student_profile
    certificates = (
        Certificate.objects.filter(student=student, status="issued")
        .select_related("course")
        .order_by("-issue_date")
    )
    return render(request, "student/my_certificates.html", {"certificates": certificates, "student": student})


@student_required
def student_certificate_download(request, certificate_id):
    """
    Allows a student to download their own certificate PDF.
    Prevents unauthorized access to other students' certificates.
    """
    student = request.user.student_profile
    cert = get_object_or_404(Certificate, pk=certificate_id)
    if cert.student_id != student.id:
        return HttpResponseForbidden("You are not authorized to access this certificate.")
    if cert.status != "issued":
        return HttpResponseForbidden("This certificate is not currently available for download.")

    buffer = generate_certificate_pdf(cert)
    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    filename = f"{cert.certificate_number}.pdf"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@student_required
def student_profile_view(request):
    """
    Allows student to view profile and update password.
    """
    student = request.user.student_profile
    if request.method == "POST":
        form = StudentPasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            form.save()
            # Keep student logged in after password change
            login(request, request.user)
            messages.success(request, "Your password has been updated successfully.")
            return redirect("/portal/student/profile/")
        else:
            messages.error(request, "Please fix the password errors below.")
    else:
        form = StudentPasswordChangeForm(request.user)

    return render(request, "student/profile.html", {"student": student, "form": form})


# ==============================================================================
# Public / Standalone Certificate Verification
# ==============================================================================

def public_certificate_view(request, cert_number):
    """
    Standalone printable certificate view (e.g. for QR codes / verification links).
    """
    cert = get_object_or_404(
        Certificate.objects.select_related("student", "course"),
        certificate_number=cert_number,
    )
    template_name = (
        "certificates/achievement_certificate.html"
        if cert.certificate_type == "achievement"
        else "certificates/completion_certificate.html"
    )
    context = {
        "certificate": cert,
        "student_name": cert.student.full_name,
        "course_title": cert.course.name,
        "duration_days": cert.duration_days,
        "duration_hours": cert.duration_hours,
        "completion_date": cert.completion_date.strftime("%d %B %Y"),
        "issue_date": cert.issue_date.strftime("%d %B %Y"),
        "certificate_number": cert.certificate_number,
        "achievement_text": cert.achievement_text,
        "signatory_name": cert.signatory_name,
        "signatory_title": cert.signatory_title,
        "signature_url": cert.signature_url,
        "signature_image_url": cert.signature_url,
        "footer_text": cert.footer_text,
        "is_official": cert.is_official,
        "cert_type": cert.certificate_type,
    }
    return render(request, template_name, context)


def public_certificate_download(request, cert_number):
    """
    Allows downloading the official verified PDF for an issued certificate.
    """
    cert = get_object_or_404(
        Certificate.objects.select_related("student", "course"),
        certificate_number=cert_number,
    )
    if cert.status != "issued":
        return HttpResponseForbidden("This certificate is not currently available for download.")

    buffer = generate_certificate_pdf(cert)
    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    filename = f"{cert.certificate_number}.pdf"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
