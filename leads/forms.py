from django import forms

from catalog.models import Vehicle

from .models import Inquiry
from .validators import (
    CYRILLIC_CITY_ERROR,
    CYRILLIC_NAME_ERROR,
    assert_cyrillic_label,
    assert_no_spam_markers,
    normalize_ru_phone,
)


class InquiryForm(forms.ModelForm):
    phone = forms.CharField(
        max_length=20,
        widget=forms.TextInput(
            attrs={
                "class": "glass-panel",
                "placeholder": "+7 (___) ___-__-__",
                "inputmode": "tel",
                "autocomplete": "tel",
            }
        ),
    )

    class Meta:
        model = Inquiry
        fields = ["name", "phone", "city", "message", "vehicle"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "glass-panel",
                    "placeholder": "Ваше имя",
                    "autocomplete": "name",
                }
            ),
            "city": forms.TextInput(
                attrs={
                    "class": "glass-panel",
                    "placeholder": "Ваш город",
                    "autocomplete": "address-level2",
                }
            ),
            "message": forms.Textarea(
                attrs={
                    "class": "glass-panel",
                    "placeholder": "Какая техника вас интересует?",
                    "rows": 4,
                }
            ),
            "vehicle": forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["message"].required = False
        self.fields["name"].max_length = 100
        self.fields["city"].max_length = 120
        self.fields["vehicle"].required = False
        self.fields["vehicle"].queryset = Vehicle.objects.filter(is_published=True)

    def clean(self):
        cleaned = super().clean()
        # Invalid / unpublished hidden PKs must not fail the lead or attach.
        self._errors.pop("vehicle", None)
        raw = (self.data.get("vehicle") or "").strip()
        vehicle = None
        if raw.isdigit():
            vehicle = Vehicle.objects.filter(pk=int(raw), is_published=True).first()
        cleaned["vehicle"] = vehicle
        return cleaned

    def clean_phone(self):
        return normalize_ru_phone(self.cleaned_data.get("phone", ""))

    def clean_name(self):
        return assert_cyrillic_label(
            self.cleaned_data.get("name", ""), CYRILLIC_NAME_ERROR
        )

    def clean_city(self):
        return assert_cyrillic_label(
            self.cleaned_data.get("city", ""), CYRILLIC_CITY_ERROR
        )

    def clean_message(self):
        return assert_no_spam_markers(
            self.cleaned_data.get("message", ""), allow_empty=True
        )
