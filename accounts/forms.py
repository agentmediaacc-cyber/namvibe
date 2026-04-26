from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from .models import AccountProfile, Profile
from .services import master_admin_email, master_admin_supabase_uid


COUNTRY_CODE_CHOICES = [
    ("+264", "Namibia (+264)"),
    ("+27", "South Africa (+27)"),
    ("+267", "Botswana (+267)"),
    ("+260", "Zambia (+260)"),
    ("+244", "Angola (+244)"),
]


class SignupForm(forms.Form):
    full_name = forms.CharField(max_length=120)
    country_code = forms.ChoiceField(choices=COUNTRY_CODE_CHOICES, initial="+264")
    cellphone_number = forms.CharField(max_length=30)
    email = forms.EmailField()
    username = forms.CharField(max_length=30)
    password = forms.CharField(widget=forms.PasswordInput())
    confirm_password = forms.CharField(widget=forms.PasswordInput())

    def clean_full_name(self):
        full_name = self.cleaned_data["full_name"].strip()
        if len(full_name.split()) < 2:
            raise forms.ValidationError("Enter your first and last name.")
        return full_name

    def clean_username(self):
        username = self.cleaned_data["username"].strip().lower()
        if len(username) < 3:
            raise forms.ValidationError("Username must be at least 3 characters.")
        allowed = "abcdefghijklmnopqrstuvwxyz0123456789._"
        if any(ch not in allowed for ch in username):
            raise forms.ValidationError("Use only letters, numbers, dot, and underscore.")
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("This username is already taken.")
        if Profile.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("This username is already taken.")
        return username

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists() or AccountProfile.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean_cellphone_number(self):
        cellphone_number = "".join(char for char in self.cleaned_data["cellphone_number"] if char.isdigit())
        if len(cellphone_number) < 7:
            raise forms.ValidationError("Enter a valid cellphone number.")
        return cellphone_number

    def clean_password(self):
        password = self.cleaned_data["password"]
        if len(password) < 8:
            raise forms.ValidationError("Password must be at least 8 characters.")
        if not any(char.isupper() for char in password):
            raise forms.ValidationError("Password must include an uppercase letter.")
        if not any(char.islower() for char in password):
            raise forms.ValidationError("Password must include a lowercase letter.")
        if not any(char.isdigit() for char in password):
            raise forms.ValidationError("Password must include a number.")
        try:
            validate_password(password)
        except ValidationError as exc:
            raise forms.ValidationError(exc.messages)
        return password

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get("password")
        confirm = cleaned.get("confirm_password")
        country_code = cleaned.get("country_code") or "+264"
        number = cleaned.get("cellphone_number")
        if password and confirm and password != confirm:
            self.add_error("confirm_password", "Passwords do not match.")
        if number:
            normalized_phone = f"{country_code}{number.lstrip('0')}"
            if AccountProfile.objects.filter(cellphone_number__iexact=normalized_phone).exists():
                self.add_error("cellphone_number", "An account with this cellphone number already exists.")
            cleaned["normalized_phone"] = normalized_phone
        return cleaned


class LoginForm(forms.Form):
    identifier = forms.CharField(max_length=150)
    password = forms.CharField(widget=forms.PasswordInput())
    remember_me = forms.BooleanField(required=False)

    def clean_identifier(self):
        return self.cleaned_data["identifier"].strip()

    def clean(self):
        cleaned = super().clean()
        identifier = cleaned.get("identifier", "")
        password = cleaned.get("password", "")

        if not identifier or not password:
            return cleaned

        user = User.objects.filter(username__iexact=identifier).first()
        if user is None:
            normalized_identifier = identifier.lower().strip()
            master_email = master_admin_email()
            master_uid = master_admin_supabase_uid()
            if normalized_identifier == master_email:
                if master_uid:
                    user = User.objects.filter(account_role__supabase_uid=master_uid).first()
                if user is None:
                    user = User.objects.filter(email__iexact=normalized_identifier).order_by("id").first()
            else:
                user = User.objects.filter(email__iexact=normalized_identifier).first()

        if user is None:
            raise forms.ValidationError("Account not recognized.")

        authenticated = authenticate(username=user.username, password=password)
        if authenticated is None:
            raise forms.ValidationError("Incorrect password.")

        if not authenticated.is_active:
            raise forms.ValidationError("This account is inactive.")

        cleaned["user"] = authenticated
        return cleaned


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = (
            "display_name",
            "username",
            "bio",
            "avatar",
            "cover_image",
            "website",
            "town",
            "region",
            "location",
            "is_creator",
            "is_private",
        )
        widgets = {
            "bio": forms.Textarea(attrs={"rows": 4}),
        }

    def clean_username(self):
        username = self.cleaned_data["username"].strip().lower()
        if len(username) < 3:
            raise forms.ValidationError("Username must be at least 3 characters.")
        qs = Profile.objects.filter(username__iexact=username)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("This username is already taken.")
        return username
