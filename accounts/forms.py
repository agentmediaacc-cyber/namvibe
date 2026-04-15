from django import forms

class SignupForm(forms.Form):
    full_name = forms.CharField(max_length=120)
    username = forms.CharField(max_length=30)
    email = forms.EmailField()
    phone = forms.CharField(max_length=30)
    password = forms.CharField(widget=forms.PasswordInput())
    confirm_password = forms.CharField(widget=forms.PasswordInput())

    def clean_username(self):
        username = self.cleaned_data["username"].strip().lower()
        if len(username) < 3:
            raise forms.ValidationError("Username must be at least 3 characters.")
        allowed = "abcdefghijklmnopqrstuvwxyz0123456789._"
        if any(ch not in allowed for ch in username):
            raise forms.ValidationError("Use only letters, numbers, dot, and underscore.")
        return username

    def clean_phone(self):
        phone = self.cleaned_data["phone"].strip()
        if len(phone) < 7:
            raise forms.ValidationError("Enter a valid phone number.")
        return phone

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
        return password

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get("password")
        confirm = cleaned.get("confirm_password")
        if password and confirm and password != confirm:
            self.add_error("confirm_password", "Passwords do not match.")
        return cleaned
