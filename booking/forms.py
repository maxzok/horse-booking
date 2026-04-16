from django import forms
from datetime import timedelta
from .models import Booking, Client, ClientSubscription


class BookingForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ["client", "trainer", "horse", "service_type", "start_time", "notes"]
        widgets = {
            "start_time": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        trainer = cleaned_data.get("trainer")
        horse = cleaned_data.get("horse")
        start_time = cleaned_data.get("start_time")
        service_type = cleaned_data.get("service_type")

        if all([trainer, horse, start_time, service_type]):
            end_time = start_time + timedelta(minutes=service_type.duration)
            from .utils import check_availability

            available, msg = check_availability(
                trainer, horse, start_time, end_time, self.instance.id
            )
            if not available:
                raise forms.ValidationError(msg)
        return cleaned_data
