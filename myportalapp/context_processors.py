from django.utils import timezone
from .models import OrganizationSettings, Enrollment


def portal_context(request):
    """
    Global template context for the certification portal.
    Supplies organization branding, user role indicators,
    and pending approval counters.
    """
    try:
        org = OrganizationSettings.get_settings()
    except Exception:
        org = None

    pending_approvals_count = 0
    student_profile = None
    is_admin = False
    is_student = False

    if hasattr(request, "user") and request.user.is_authenticated:
        is_admin = request.user.is_staff or request.user.is_superuser
        if hasattr(request.user, "student_profile"):
            student_profile = request.user.student_profile
            is_student = student_profile is not None
        else:
            is_student = False

        if is_admin:
            try:
                pending_approvals_count = Enrollment.objects.filter(
                    completion_status="pending"
                ).count()
            except Exception:
                pending_approvals_count = 0

    return {
        "org": org,
        "signature_image_url": (org.signature_image_url if org else ""),
        "pending_approvals_count": pending_approvals_count,
        "user_is_admin": is_admin,
        "user_is_student": is_student,
        "student_profile": student_profile,
        "now": timezone.now(),
    }
