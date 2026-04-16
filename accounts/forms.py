from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from .models import AccountProfile

class SignupForm(forms.Form):
    full_name = forms.CharField(max_length=120)
    username = forms.CharField(max_length=30)
    email = forms.EmailField()
    cellphone_number = forms.CharField(max_length=30)
    residential_address = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}))
    country_of_origin = forms.CharField(max_length=80)
    current_country = forms.CharField(max_length=80)
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
        return username

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists() or AccountProfile.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean_cellphone_number(self):
        cellphone_number = self.cleaned_data["cellphone_number"].strip()
        digits = [char for char in cellphone_number if char.isdigit()]
        if len(digits) < 7:
            raise forms.ValidationError("Enter a valid cellphone number.")
        if AccountProfile.objects.filter(cellphone_number__iexact=cellphone_number).exists():
            raise forms.ValidationError("An account with this cellphone number already exists.")
        return cellphone_number

    def clean_residential_address(self):
        residential_address = self.cleaned_data["residential_address"].strip()
        if len(residential_address) < 8:
            raise forms.ValidationError("Enter a complete residential address.")
        return residential_address

    def clean_country_of_origin(self):
        return self.cleaned_data["country_of_origin"].strip()

    def clean_current_country(self):
        return self.cleaned_data["current_country"].strip()

    def clean_password(self):
        password = self.cleaned_data["password"]
        if len(password) < 8:
            raise forms.ValidationError("Password must be at least 8 characters.")
        if not any(c.isupper() for c in password):
            raise forms.ValidationError("Password must include an uppercase letter.")
        if not any(c.islower() for c in password):
            raise forms.ValidationError("Password must include a lowercase letter.")
        if not any(c.isdigit() for c in password):
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
        if password and confirm and password != confirm:
            self.add_error("confirm_password", "Passwords do not match.")
        return cleaned


class LoginForm(forms.Form):
    identifier = forms.CharField(max_length=150)
    password = forms.CharField(widget=forms.PasswordInput())

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
            user = User.objects.filter(email__iexact=identifier).first()

        if user is None:
            raise forms.ValidationError("Invalid email, username, or password.")

        authenticated = authenticate(username=user.username, password=password)
        if authenticated is None:
            raise forms.ValidationError("Invalid email, username, or password.")

        if not authenticated.is_active:
            raise forms.ValidationError("This account is inactive.")

        cleaned["user"] = authenticated
        return cleaned
