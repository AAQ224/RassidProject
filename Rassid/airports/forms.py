from django import forms
from .models import SubscriptionRequest

class AirportSignupForm(forms.ModelForm):
    def clean_admin_phone(self):
        import re
        phone = self.cleaned_data.get('admin_phone', '').strip()
        # Accepts Saudi mobile numbers: +9665XXXXXXXX or 05XXXXXXXX
        pattern = r'^(\+9665\d{8}|05\d{8})$'
        if not re.match(pattern, phone):
            raise forms.ValidationError('Enter a valid Saudi mobile number (e.g. +9665XXXXXXXX or 05XXXXXXXX)')
        return phone

    class Meta:
        model = SubscriptionRequest
        fields = [
            'airport_name', 'airport_code', 'country', 'city',
            'admin_email', 'admin_phone', 'selected_plan',
            'official_license', 'commercial_record', 'image'
        ]
        widgets = {
            'airport_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter Airport Name'}),
            'airport_code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'IATA Code (e.g. RUH)'}),
            'country': forms.TextInput(attrs={'class': 'form-control'}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'admin_email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Official Contact Email'}),
            'admin_phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+966...'}),
            'selected_plan': forms.Select(attrs={'class': 'form-control'}),
            'official_license': forms.FileInput(attrs={'class': 'form-control-file'}),
            'commercial_record': forms.FileInput(attrs={'class': 'form-control-file'}),
            'image': forms.FileInput(attrs={'class': 'form-control-file'}),
        }

    def clean_image(self):
        image = self.cleaned_data.get('image')
        if not image:
            from django.core.exceptions import ValidationError
            raise ValidationError('Airport image is required.')
        return image