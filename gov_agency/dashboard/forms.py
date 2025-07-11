from django import forms
from .models import Note, MonthlySalesTarget 
import datetime

class NoteForm(forms.ModelForm):
    class Meta:
        model = Note
        fields = ['content']
        widgets = {
            'content': forms.TextInput(attrs={
                'class': 'input input-bordered w-full',
                'placeholder': 'Enter your new to-do item...'
            })
        }
        labels = {
            'content': '' # Hide the label for a cleaner look
        }



class SalesTargetForm(forms.Form):
    # Create choices for months and years dynamically
    MONTH_CHOICES = [(i, datetime.date(2000, i, 1).strftime('%B')) for i in range(1, 13)]
    YEAR_CHOICES = [(i, i) for i in range(datetime.date.today().year, datetime.date.today().year + 5)]

    month = forms.ChoiceField(choices=MONTH_CHOICES, widget=forms.Select(attrs={'class': 'select select-bordered'}))
    year = forms.ChoiceField(choices=YEAR_CHOICES, widget=forms.Select(attrs={'class': 'select select-bordered'}))
    target_quantity = forms.DecimalField(
        max_digits=14, decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'input input-bordered', 'placeholder': 'e.g., 1000.00'})
    )