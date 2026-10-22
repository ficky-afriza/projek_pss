from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import AccountProfile, ContactMessage, Order, Product


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(label="Email")

    class Meta:
        model = User
        fields = ("username", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Username"
        self.fields["username"].help_text = "Gunakan minimal 5 karakter."
        self.fields["password1"].label = "Kata sandi"
        self.fields["password1"].help_text = (
            "Minimal 8 karakter. Hindari kata sandi umum atau yang mirip dengan username."
        )
        self.fields["password2"].label = "Ulangi kata sandi"
        self.fields["password2"].help_text = "Masukkan kata sandi yang sama untuk konfirmasi."

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if len(username) < 5:
            raise forms.ValidationError("Username harus terdiri dari minimal 5 karakter.")
        return username

    def clean_email(self):
        email = self.cleaned_data["email"].strip()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Email sudah terdaftar.")
        return email


class CheckoutForm(forms.Form):
    address = forms.CharField(
        label="Alamat lengkap",
        min_length=5,
        max_length=2000,
        widget=forms.Textarea(attrs={"rows": 4}),
    )
    payment_method = forms.ChoiceField(choices=Order.PaymentMethod.choices, label="Metode pembayaran")


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ("name", "price", "stock", "category", "description", "image")


class ContactForm(forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ("subject", "message")


class AccountForm(forms.ModelForm):
    avatar = forms.ImageField(required=False, label="Foto profil")

    class Meta:
        model = User
        fields = ("username", "email")

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if len(username) < 5:
            raise forms.ValidationError("Username harus terdiri dari minimal 5 karakter.")
        if User.objects.exclude(pk=self.instance.pk).filter(username__iexact=username).exists():
            raise forms.ValidationError("Username sudah digunakan.")
        return username

    def clean_email(self):
        email = self.cleaned_data["email"].strip()
        if User.objects.exclude(pk=self.instance.pk).filter(email__iexact=email).exists():
            raise forms.ValidationError("Email sudah terdaftar.")
        return email

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit and self.cleaned_data.get("avatar"):
            profile, _ = AccountProfile.objects.get_or_create(user=user)
            profile.avatar = self.cleaned_data["avatar"]
            profile.save(update_fields=["avatar"])
        return user
