from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model

from .models import GiftCatalog, MembershipPlan


class GiftSendForm(forms.Form):
    gift = forms.ModelChoiceField(queryset=GiftCatalog.objects.none(), empty_label=None)
    quantity = forms.IntegerField(min_value=1, max_value=25, initial=1)
    next = forms.CharField(required=False, widget=forms.HiddenInput())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["gift"].queryset = GiftCatalog.objects.filter(is_active=True).order_by("coin_cost", "name")


class StaffCoinAdjustmentForm(forms.Form):
    MODE_TOPUP = "topup"
    MODE_SPEND = "spend"
    MODE_CHOICES = [
        (MODE_TOPUP, "Top up"),
        (MODE_SPEND, "Spend / debit"),
    ]

    user = forms.ModelChoiceField(queryset=get_user_model().objects.order_by("username"))
    mode = forms.ChoiceField(choices=MODE_CHOICES, initial=MODE_TOPUP)
    amount = forms.DecimalField(min_value=Decimal("0.01"), decimal_places=2, max_digits=10)
    reference = forms.CharField(max_length=160, required=False)


class StaffPremiumTierForm(forms.Form):
    user = forms.ModelChoiceField(queryset=get_user_model().objects.order_by("username"))
    plan = forms.ModelChoiceField(queryset=MembershipPlan.objects.filter(is_active=True).order_by("price", "name"))
    reference = forms.CharField(max_length=160, required=False)
