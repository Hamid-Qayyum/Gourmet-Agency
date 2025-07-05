from django import forms
from .models import Expense
from django.utils import timezone


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        # We don't include 'user' as it will be set automatically in the view.
        fields = ['title', 'amount', 'expense_date', 'description']
        
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'input input-bordered w-full',
                'placeholder': 'e.g., Office Rent, Fuel, etc.'
            }),
            'amount': forms.NumberInput(attrs={
                'class': 'input input-bordered w-full',
                'placeholder': 'e.g., 5000.00',
                'step': '0.01'
            }),
            'expense_date': forms.DateTimeInput(
                attrs={
                    'class': 'input input-bordered w-full',
                    'type': 'datetime-local' # Use modern browser datetime picker
                },
                format='%Y-%m-%dT%H:%M' 
            ),
            'description': forms.Textarea(attrs={
                'class': 'textarea textarea-bordered w-full h-24',
                'placeholder': 'Optional details about this expense...'
            }),
        }
        labels = {
            'title': 'Expense Title',
            'amount': 'Amount (Rs)',
            'expense_date': 'Date of Expense',
            'description': 'Description (Optional)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ensure the date format is correctly handled by the form widget
        self.fields['expense_date'].input_formats = ('%Y-%m-%dT%H:%M',)