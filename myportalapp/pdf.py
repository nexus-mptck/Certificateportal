import os
from io import BytesIO
from django.conf import settings
from django.core.files.base import ContentFile
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.pdfgen import canvas


def generate_certificate_pdf(certificate, buffer=None):
    """
    Renders an official A4-landscape Certificate PDF for the given Certificate instance.
    Adheres to the design tokens and layout of the certificate template:
    - Completion: Warm off-white background (#fffdf8), gold framing (#a8812f), dark ink (#1c2433).
    - Achievement: Off-white ivory (#fbf8f1), navy primary (#0e1a2f) with gold accents (#b8923a).
    """
    if buffer is None:
        buffer = BytesIO()

    # Dimensions for A4 landscape
    width, height = landscape(A4)  # 841.89 x 595.27 points (297mm x 210mm)

    c = canvas.Canvas(buffer, pagesize=(width, height))
    c.setTitle(f"Certificate - {certificate.certificate_number}")

    is_achievement = (certificate.certificate_type == "achievement")

    # Colors
    if is_achievement:
        bg_color = colors.HexColor("#fbf8f1")
        ink_color = colors.HexColor("#0e1a2f")
        accent_color = colors.HexColor("#b8923a")
        outer_border_color = colors.HexColor("#0e1a2f")
        muted_color = colors.HexColor("#5a6577")
        light_gold = colors.HexColor("#fff8e6")
    else:
        bg_color = colors.HexColor("#fffdf8")
        ink_color = colors.HexColor("#1c2433")
        accent_color = colors.HexColor("#a8812f")
        outer_border_color = colors.HexColor("#a8812f")
        muted_color = colors.HexColor("#5a6577")
        light_gold = colors.HexColor("#fefbf3")

    # 1. Background fill
    c.setFillColor(bg_color)
    c.rect(0, 0, width, height, fill=1, stroke=0)

    # 2. Outer decorative borders
    if is_achievement:
        # Thick outer navy band (7mm approx 20pt)
        c.setStrokeColor(outer_border_color)
        c.setLineWidth(16)
        c.rect(8, 8, width - 16, height - 16, fill=0, stroke=1)

        # Thin inner gold frame
        c.setStrokeColor(accent_color)
        c.setLineWidth(1.5)
        c.rect(26, 26, width - 52, height - 52, fill=0, stroke=1)
        c.setLineWidth(0.75)
        c.rect(30, 30, width - 60, height - 60, fill=0, stroke=1)
    else:
        # Main gold outer frame (9mm inset ~ 25.5pt)
        c.setStrokeColor(outer_border_color)
        c.setLineWidth(3)
        c.rect(26, 26, width - 52, height - 52, fill=0, stroke=1)

        # Inner thin gold line (inset 2.2mm further ~ 6pt)
        c.setLineWidth(0.8)
        c.rect(32, 32, width - 64, height - 64, fill=0, stroke=1)

        # Decorative 4 corner accents
        c.setLineWidth(1.8)
        corner_size = 38
        inset = 39

        # Top-left corner
        c.line(inset, height - inset, inset + corner_size, height - inset)
        c.line(inset, height - inset, inset, height - inset - corner_size)

        # Top-right corner
        c.line(width - inset, height - inset, width - inset - corner_size, height - inset)
        c.line(width - inset, height - inset, width - inset, height - inset - corner_size)

        # Bottom-left corner
        c.line(inset, inset, inset + corner_size, inset)
        c.line(inset, inset, inset, inset + corner_size)

        # Bottom-right corner
        c.line(width - inset, inset, width - inset - corner_size, inset)
        c.line(width - inset, inset, width - inset, inset + corner_size)

    # 3. Revoked / Sample Watermark
    if certificate.status == "revoked":
        c.saveState()
        c.translate(width / 2.0, height / 2.0)
        c.rotate(-25)
        c.setFillColor(colors.Color(0.8, 0.1, 0.1, alpha=0.15))
        c.setFont("Helvetica-Bold", 72)
        c.drawCentredString(0, 0, "REVOKED")
        c.restoreState()

    center_x = width / 2.0

    # 4. Organization Branding & Header
    top_y = height - 76
    c.setFillColor(ink_color)
    c.setFont("Helvetica-Bold", 13)
    org_display = certificate.org_name or "Meridian Training Institute"
    c.drawCentredString(center_x, top_y, org_display.upper())

    # 5. Certificate Title
    top_y -= 44
    c.setFont("Times-Bold", 34)
    c.setFillColor(ink_color)
    if is_achievement:
        title_text = "CERTIFICATE OF ACHIEVEMENT"
    else:
        title_text = "Certificate of Completion"
    c.drawCentredString(center_x, top_y, title_text)

    # 6. "This certificate is presented to"
    top_y -= 26
    c.setFont("Helvetica", 11)
    c.setFillColor(muted_color)
    c.drawCentredString(center_x, top_y, "This certificate is presented to")

    # 7. Student Name
    top_y -= 42
    c.setFont("Times-BoldItalic" if not is_achievement else "Times-Bold", 30)
    c.setFillColor(ink_color)
    student_name = certificate.student.full_name if certificate.student else "Student Name"
    c.drawCentredString(center_x, top_y, student_name)

    # Name underline rule
    c.setStrokeColor(accent_color)
    c.setLineWidth(1)
    name_line_w = max(240, min(500, c.stringWidth(student_name, "Times-BoldItalic" if not is_achievement else "Times-Bold", 30) + 40))
    c.line(center_x - (name_line_w / 2), top_y - 6, center_x + (name_line_w / 2), top_y - 6)

    # 8. Lead text
    top_y -= 26
    c.setFont("Helvetica", 11)
    c.setFillColor(colors.HexColor("#344055"))
    if is_achievement:
        lead_text = "in recognition of outstanding achievement in the course"
    else:
        lead_text = "for successfully completing the training course"
    c.drawCentredString(center_x, top_y, lead_text)

    # 9. Course Name
    top_y -= 30
    c.setFont("Times-Bold", 20)
    c.setFillColor(ink_color)
    course_title = certificate.course.name if certificate.course else "Course Title"
    c.drawCentredString(center_x, top_y, course_title)

    # 10. Optional Achievement Badge Text
    if is_achievement and certificate.achievement_text:
        top_y -= 26
        c.setFont("Helvetica-Bold", 10)
        c.setFillColor(accent_color)
        ach_text = certificate.achievement_text
        c.drawCentredString(center_x, top_y, f"— {ach_text} —")

    # 11. Training Duration and Completion Date metadata
    top_y -= 32
    c.setFont("Helvetica", 10)
    c.setFillColor(muted_color)
    dur_str = f"Duration: {certificate.duration_days} training days  ·  {certificate.duration_hours} training hours"
    comp_date_str = f"Completed: {certificate.completion_date.strftime('%d %B %Y') if certificate.completion_date else '—'}"
    meta_str = f"{dur_str}        |        {comp_date_str}"
    c.drawCentredString(center_x, top_y, meta_str)

    # 12. Bottom Signatures & Seal
    foot_y = 100
    left_x = 145
    right_x = width - 145

    # Left signatory - digital signature or italic name
    sig_drawn = False
    sig_path = None
    if certificate.signature_image:
        try:
            if hasattr(certificate.signature_image, "path") and os.path.exists(certificate.signature_image.path):
                sig_path = certificate.signature_image.path
        except Exception:
            pass

    if not sig_path and getattr(certificate, "signature_image_url", None):
        media_url = getattr(settings, "MEDIA_URL", "/media/")
        if certificate.signature_image_url.startswith(media_url):
            rel = certificate.signature_image_url[len(media_url):]
            candidate = os.path.join(settings.MEDIA_ROOT, rel)
            if os.path.exists(candidate):
                sig_path = candidate

    if not sig_path and not getattr(certificate, "pk", None) and not getattr(certificate, "org_name", None):
        try:
            from .models import OrganizationSettings
            settings_obj = OrganizationSettings.get_settings()
            if settings_obj.signature_image and hasattr(settings_obj.signature_image, "path") and os.path.exists(settings_obj.signature_image.path):
                sig_path = settings_obj.signature_image.path
        except Exception:
            pass

    sig_w = 100
    sig_h = 36
    if sig_path and os.path.exists(sig_path):
        try:
            c.drawImage(
                sig_path,
                left_x - (sig_w / 2.0),
                foot_y + 26,
                width=sig_w,
                height=sig_h,
                preserveAspectRatio=True,
                mask='auto',
            )
            sig_drawn = True
        except Exception:
            sig_drawn = False
    elif certificate.signature_image:
        try:
            from reportlab.lib.utils import ImageReader
            certificate.signature_image.open('rb')
            img_reader = ImageReader(certificate.signature_image)
            c.drawImage(
                img_reader,
                left_x - (sig_w / 2.0),
                foot_y + 26,
                width=sig_w,
                height=sig_h,
                preserveAspectRatio=True,
                mask='auto',
            )
            sig_drawn = True
        except Exception:
            sig_drawn = False

    c.setStrokeColor(ink_color)
    c.setLineWidth(0.8)
    c.line(left_x - 70, foot_y + 24, left_x + 70, foot_y + 24)

    if not sig_drawn:
        c.setFont("Times-Italic", 13)
        c.setFillColor(ink_color)
        c.drawCentredString(left_x, foot_y + 30, certificate.signatory_name or "Authorized Signatory")

    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(ink_color)
    c.drawCentredString(left_x, foot_y + 12, certificate.signatory_name or "Authorized Signatory")

    c.setFont("Helvetica", 9)
    c.setFillColor(muted_color)
    c.drawCentredString(left_x, foot_y, certificate.signatory_title or "Director of Training")

    # Center Seal
    c.setStrokeColor(accent_color)
    c.setFillColor(light_gold)
    c.setLineWidth(1.5)
    c.circle(center_x, foot_y + 16, 26, fill=1, stroke=1)
    c.setLineWidth(0.6)
    c.circle(center_x, foot_y + 16, 22, fill=0, stroke=1)

    c.setFont("Helvetica-Bold", 7.5)
    c.setFillColor(accent_color)
    c.drawCentredString(center_x, foot_y + 18, "OFFICIAL")
    c.drawCentredString(center_x, foot_y + 9, "SEAL")

    # Right issue date
    c.setStrokeColor(ink_color)
    c.setLineWidth(0.8)
    c.line(right_x - 70, foot_y + 24, right_x + 70, foot_y + 24)

    issue_str = certificate.issue_date.strftime("%d %B %Y") if certificate.issue_date else "—"
    c.setFont("Helvetica", 11)
    c.setFillColor(ink_color)
    c.drawCentredString(right_x, foot_y + 30, issue_str)

    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(ink_color)
    c.drawCentredString(right_x, foot_y + 12, "Date of Issue")

    c.setFont("Helvetica", 9)
    c.setFillColor(muted_color)
    c.drawCentredString(right_x, foot_y, "Valid Certificate")

    # 13. Footer Notice
    footer_text = certificate.footer_text or "This certificate confirms participation in and completion of the listed training."
    c.setFont("Helvetica", 8)
    c.setFillColor(muted_color)
    c.drawCentredString(center_x, 58, footer_text)

    # 14. Certificate Number
    c.setFont("Courier-Bold", 9)
    c.setFillColor(colors.HexColor("#7a8497"))
    c.drawCentredString(center_x, 42, f"Certificate no. {certificate.certificate_number}")

    c.showPage()
    c.save()

    buffer.seek(0)
    return buffer


def save_certificate_pdf(certificate):
    """
    Renders and saves the PDF to certificate.pdf_file on the model.
    """
    buf = generate_certificate_pdf(certificate)
    filename = f"{certificate.certificate_number}.pdf"
    certificate.pdf_file.save(filename, ContentFile(buf.getvalue()), save=True)
    return certificate.pdf_file
