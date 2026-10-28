from decimal import Decimal
from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import Course, Student, Enrollment, OrganizationSettings, Certificate


class CommonLoginForm(forms.Form):
    """
    Unified login form for the root '/' login page.
    Accepts username, email, or student registration number + password.
    After validation, cleaned_data contains:
      'user'  – the authenticated User object
      'role'  – 'admin' | 'student'
    """
    username = forms.CharField(max_length=150, required=True)
    password = forms.CharField(widget=forms.PasswordInput, required=True)
    remember  = forms.BooleanField(required=False)

    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get("username", "").strip()
        password = cleaned_data.get("password", "")

        if not (username and password):
            return cleaned_data

        user = None

        # 1) Try direct username authentication
        user = authenticate(username=username, password=password)

        # 2) Try by email
        if not user:
            for user_candidate in User.objects.filter(email__iexact=username):
                auth_user = authenticate(username=user_candidate.username, password=password)
                if auth_user:
                    user = auth_user
                    break

        # 3) Try student registration number
        if not user:
            student = Student.objects.filter(registration_number__iexact=username).select_related("user").first()
            if student and student.user:
                user = authenticate(username=student.user.username, password=password)

        if not user:
            raise ValidationError(
                "Invalid credentials. Please check your username / email / registration number and password."
            )

        # Determine role
        if user.is_staff or user.is_superuser:
            cleaned_data["role"] = "admin"
        elif hasattr(user, "student_profile") and user.student_profile is not None:
            cleaned_data["role"] = "student"
        else:
            raise ValidationError(
                "Your account is not linked to an admin or student role. Contact support."
            )

        cleaned_data["user"] = user
        return cleaned_data


class AdminLoginForm(forms.Form):
    username = forms.CharField(max_length=150, required=True)
    password = forms.CharField(widget=forms.PasswordInput, required=True)
    remember = forms.BooleanField(required=False)

    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get("username")
        password = cleaned_data.get("password")

        if username and password:
            # Check by username or email
            user = authenticate(username=username, password=password)
            if not user:
                # Try finding user by email
                try:
                    user_obj = User.objects.get(email__iexact=username)
                    user = authenticate(username=user_obj.username, password=password)
                except (User.DoesNotExist, User.MultipleObjectsReturned):
                    pass

            if not user:
                raise ValidationError("The username or password is incorrect. Check both and try again.")
            if not (user.is_staff or user.is_superuser):
                raise ValidationError("Access denied. Administrator privileges are required.")

            cleaned_data["user"] = user
        return cleaned_data


class StudentLoginForm(forms.Form):
    username = forms.CharField(max_length=150, required=True)
    password = forms.CharField(widget=forms.PasswordInput, required=True)
    remember = forms.BooleanField(required=False)

    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get("username")
        password = cleaned_data.get("password")

        if username and password:
            # Check if username is registration number, email, or username
            user = authenticate(username=username, password=password)
            if not user:
                # Try finding student by registration number
                try:
                    student = Student.objects.select_related("user").get(registration_number__iexact=username)
                    if student.user:
                        user = authenticate(username=student.user.username, password=password)
                except Student.DoesNotExist:
                    pass

            if not user:
                # Try finding user by email
                try:
                    user_obj = User.objects.get(email__iexact=username)
                    user = authenticate(username=user_obj.username, password=password)
                except (User.DoesNotExist, User.MultipleObjectsReturned):
                    pass

            if not user:
                raise ValidationError("The registration number or password is incorrect. Check both and try again.")

            # Verify that user has an associated student profile
            if not hasattr(user, "student_profile") or user.student_profile is None:
                raise ValidationError("This account is not associated with an enrolled student record.")

            cleaned_data["user"] = user
        return cleaned_data


class CourseForm(forms.ModelForm):
    course_name = forms.CharField(max_length=200, required=True)
    course_code = forms.CharField(max_length=50, required=True)

    class Meta:
        model = Course
        fields = [
            "name",
            "code",
            "description",
            "duration_days",
            "duration_hours",
            "start_date",
            "end_date",
            "status",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["course_name"].initial = self.instance.name
            self.fields["course_code"].initial = self.instance.code
        # Map template field names
        if self.data:
            if "course_name" in self.data and "name" not in self.data:
                self.data = self.data.copy()
                self.data["name"] = self.data.get("course_name")
            if "course_code" in self.data and "code" not in self.data:
                self.data = self.data.copy()
                self.data["code"] = self.data.get("course_code")

    def clean(self):
        cleaned_data = super().clean()
        name = cleaned_data.get("course_name") or cleaned_data.get("name")
        code = cleaned_data.get("course_code") or cleaned_data.get("code")
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")

        if name:
            cleaned_data["name"] = name
        if code:
            cleaned_data["code"] = code.strip().upper()
            # Check unique code
            qs = Course.objects.filter(code__iexact=cleaned_data["code"])
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error("course_code", f"A course with code '{cleaned_data['code']}' already exists.")

        if start_date and end_date and end_date < start_date:
            self.add_error("end_date", "End date must be on or after the start date.")

        return cleaned_data


class StudentEnrollmentForm(forms.Form):
    full_name = forms.CharField(max_length=200, required=True)
    username = forms.CharField(max_length=150, required=False)
    email = forms.EmailField(required=True)
    password = forms.CharField(widget=forms.PasswordInput, required=False, min_length=8)
    phone = forms.CharField(max_length=50, required=False)
    course = forms.ModelChoiceField(queryset=Course.objects.all(), required=True)
    enroll_date = forms.DateField(required=True, initial=timezone.now)

    def clean_full_name(self):
        name = self.cleaned_data["full_name"].strip()
        if len(name) < 2:
            raise ValidationError("Please enter a valid full name.")
        return name

    def clean_username(self):
        username = self.cleaned_data.get("username", "").strip()
        if username:
            email = self.data.get("email", "").strip().lower()
            existing_user = User.objects.filter(username__iexact=username).first()
            if existing_user:
                if hasattr(existing_user, "student_profile") and existing_user.student_profile and existing_user.student_profile.email.lower() == email:
                    return username
                raise ValidationError("A user with this username already exists. Please choose a different username.")
        return username

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        existing_user = User.objects.filter(email__iexact=email).first()
        if existing_user:
            # If user exists but is not linked to any student profile, it conflicts (e.g. admin email)
            if not hasattr(existing_user, "student_profile") or existing_user.student_profile is None:
                raise ValidationError("An account with this email address already exists.")
        return email

    def clean_password(self):
        pw = self.cleaned_data.get("password")
        if pw and len(pw) < 8:
            raise ValidationError("Password must be at least 8 characters long.")
        return pw


class CertificateGenerationForm(forms.Form):
    student = forms.ModelChoiceField(queryset=Student.objects.all(), required=True)
    course = forms.ModelChoiceField(queryset=Course.objects.all(), required=True)
    cert_type = forms.ChoiceField(
        choices=[("completion", "Completion"), ("achievement", "Achievement")],
        initial="completion",
        required=True,
    )
    achievement_text = forms.CharField(max_length=255, required=False)


class OrganizationSettingsForm(forms.ModelForm):
    remove_signature = forms.BooleanField(required=False, widget=forms.HiddenInput())
    # Override with FileField so Django's ImageField validator doesn't run first,
    # letting our custom clean_signature_image control all error messages.
    signature_image = forms.FileField(required=False, widget=forms.ClearableFileInput())

    class Meta:
        model = OrganizationSettings
        fields = ["name", "logo", "signatory_name", "signatory_title", "signature_image", "footer_text"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.data:
            self.data = self.data.copy()
            if "company" in self.data and "name" not in self.data:
                self.data["name"] = self.data.get("company")
            if "sig" in self.data and "signatory_name" not in self.data:
                self.data["signatory_name"] = self.data.get("sig")
            if "desig" in self.data and "signatory_title" not in self.data:
                self.data["signatory_title"] = self.data.get("desig")
            if "footer" in self.data and "footer_text" not in self.data:
                self.data["footer_text"] = self.data.get("footer")
            if "remove_signature" in self.data:
                val = self.data.get("remove_signature")
                self.data["remove_signature"] = str(val).lower() in ("1", "true", "yes", "on")

    def clean_signature_image(self):
        import os
        from django.core.files.uploadedfile import UploadedFile
        sig = self.cleaned_data.get("signature_image")
        # If no new file was uploaded, retain the existing file on the instance
        if not sig:
            if self.instance and self.instance.pk:
                return self.instance.signature_image or None
            return None
        # Only validate newly uploaded files
        if isinstance(sig, UploadedFile):
            # Extension check
            ext = os.path.splitext(sig.name)[1].lower()
            if ext not in [".png", ".jpg", ".jpeg"]:
                raise ValidationError("Signature must be a PNG or JPG image file.")
            # File size check
            if hasattr(sig, "size") and sig.size > 5 * 1024 * 1024:
                raise ValidationError("Signature image file size must not exceed 5MB.")
            # PIL image validity check
            try:
                from PIL import Image
                sig.seek(0)
                img = Image.open(sig)
                img.verify()
                if img.format not in ("PNG", "JPEG"):
                    raise ValidationError("Signature must be a valid PNG or JPG image file.")
                sig.seek(0)
            except ValidationError:
                raise
            except Exception:
                raise ValidationError("The uploaded signature file is not a valid image.")
        return sig

    def clean_logo(self):
        logo = self.cleaned_data.get("logo")
        if logo and hasattr(logo, "name"):
            import os
            ext = os.path.splitext(logo.name)[1].lower()
            if ext not in [".png", ".jpg", ".jpeg", ".svg"]:
                raise ValidationError("Logo must be a PNG, JPG or SVG image file.")
            if hasattr(logo, "size") and logo.size > 5 * 1024 * 1024:
                raise ValidationError("Logo file size must not exceed 5MB.")
        return logo

    def save(self, commit=True):
        import os
        from django.core.files.uploadedfile import UploadedFile
        from django.core.files.base import ContentFile

        # Call super().save(commit=False) — this populates all fields EXCEPT
        # signature_image (because we overrode it with FileField, not ImageField).
        instance = super().save(commit=False)

        sig_value = self.cleaned_data.get("signature_image")
        remove = self.cleaned_data.get("remove_signature")

        if isinstance(sig_value, UploadedFile):
            # New file uploaded — delete old file if replacing
            if instance.pk:
                try:
                    old_obj = OrganizationSettings.objects.filter(pk=instance.pk).first()
                    if old_obj and old_obj.signature_image:
                        old_obj.signature_image.delete(save=False)
                except Exception:
                    pass
            # Assign the uploaded file to the model's ImageField
            try:
                sig_value.seek(0)
                filename = os.path.basename(sig_value.name)
                instance.signature_image.save(filename, ContentFile(sig_value.read()), save=False)
            except Exception:
                pass
        elif remove:
            # Remove existing signature
            if instance.signature_image:
                try:
                    instance.signature_image.delete(save=False)
                except Exception:
                    pass
            instance.signature_image = None
        elif sig_value and not isinstance(sig_value, UploadedFile):
            # clean_signature_image returned the existing FieldFile — keep it unchanged
            instance.signature_image = sig_value

        if commit:
            instance.save()
        return instance


class AdminStudentPasswordResetForm(forms.Form):
    new_password = forms.CharField(widget=forms.PasswordInput, min_length=8, required=True)

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def save(self):
        new_password = self.cleaned_data["new_password"]
        self.user.set_password(new_password)
        self.user.save()
        return self.user


class StudentPasswordChangeForm(forms.Form):
    cur = forms.CharField(widget=forms.PasswordInput, required=True)
    new = forms.CharField(widget=forms.PasswordInput, min_length=8, required=True)

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_cur(self):
        cur_password = self.cleaned_data["cur"]
        if not self.user.check_password(cur_password):
            raise ValidationError("Current password is incorrect.")
        return cur_password

    def save(self):
        new_password = self.cleaned_data["new"]
        self.user.set_password(new_password)
        self.user.save()
        return self.user


class StudentEditForm(forms.Form):
    full_name = forms.CharField(max_length=200, required=True)
    username = forms.CharField(max_length=150, required=False)
    email = forms.EmailField(required=True)
    phone = forms.CharField(max_length=50, required=False)
    status = forms.ChoiceField(choices=Student.STATUS_CHOICES, required=True)
    new_password = forms.CharField(widget=forms.PasswordInput, required=False, min_length=8)

    def __init__(self, student, *args, **kwargs):
        self.student = student
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.fields["full_name"].initial = student.full_name
            self.fields["email"].initial = student.email
            self.fields["phone"].initial = student.phone
            self.fields["status"].initial = student.status
            if student.user:
                self.fields["username"].initial = student.user.username

    def clean_full_name(self):
        name = self.cleaned_data["full_name"].strip()
        if len(name) < 2:
            raise ValidationError("Please enter a valid full name.")
        return name

    def clean_username(self):
        username = self.cleaned_data.get("username", "").strip()
        if not username:
            if self.student.user:
                return self.student.user.username
            return self.student.registration_number.lower()
        qs = User.objects.filter(username__iexact=username)
        if self.student.user:
            qs = qs.exclude(pk=self.student.user.pk)
        if qs.exists():
            raise ValidationError("A user with this username already exists. Please choose a different username.")
        return username

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        qs = User.objects.filter(email__iexact=email)
        if self.student.user:
            qs = qs.exclude(pk=self.student.user.pk)
        if qs.exists():
            raise ValidationError("An account with this email address already exists.")
        return email

    def clean_phone(self):
        phone = self.cleaned_data.get("phone", "").strip()
        # Preserve existing data when optional field is blank
        if not phone and self.student.phone:
            return self.student.phone
        return phone

    def clean_new_password(self):
        pw = self.cleaned_data.get("new_password")
        if pw and len(pw) < 8:
            raise ValidationError("Password must be at least 8 characters long.")
        return pw

    def save(self):
        self.student.full_name = self.cleaned_data["full_name"]
        self.student.email = self.cleaned_data["email"]
        self.student.phone = self.cleaned_data["phone"]
        self.student.status = self.cleaned_data["status"]
        self.student.save()

        username = self.cleaned_data["username"]
        email = self.cleaned_data["email"]
        new_password = self.cleaned_data.get("new_password")

        name_parts = self.student.full_name.split()
        first_name = name_parts[0]
        last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""

        if self.student.user:
            user = self.student.user
            user.username = username
            user.email = email
            user.first_name = first_name
            user.last_name = last_name
            if new_password:
                user.set_password(new_password)
            user.save()
        else:
            user = User.objects.create_user(
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                password=new_password or self.student.registration_number,
            )
            self.student.user = user
            self.student.save(update_fields=["user"])

        return self.student

