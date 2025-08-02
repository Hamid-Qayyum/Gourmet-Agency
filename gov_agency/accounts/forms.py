from django import forms
from .models import ShopFinancialTransaction, CustomAccount,CustomAccountTransaction
from decimal import Decimal
from django.core.validators import MinValueValidator
from django.utils import timezone


class ReceiveCashForm(forms.ModelForm):
    """
    A simple form specifically for recording a cash receipt from a shop.
    This will create a 'credit' entry in the shop's ledger.
    """
    class Meta:
        model = ShopFinancialTransaction
        # The user will only see and fill out these two fields in the modal.
        fields = ['credit_amount', 'notes'] 
        
        widgets = {
            'credit_amount': forms.NumberInput(attrs={
                'class': 'input input-bordered w-full',
                'step': '0.01',
                'placeholder': 'Amount Received from Shop'
            }),
            'notes': forms.TextInput(attrs={
                'class': 'input input-bordered w-full',
                'placeholder': 'Optional notes (e.g., "Partial payment", "Invoice #123")'
            }),
        }
        labels = {
            'credit_amount': 'Cash Amount Received',
            'notes': 'Notes / Reference',
        }
    
    def clean_credit_amount(self):
        """Ensure the received amount is a positive number."""
        amount = self.cleaned_data.get('credit_amount')
        if amount is None or amount <= Decimal('0.00'):
            raise forms.ValidationError("Received amount must be greater than zero.")
        return amount



class EditFinancialTransactionForm(forms.ModelForm):
    """
    Form for editing an existing financial transaction.
    It will make amounts from sales read-only to maintain integrity.
    """
    transaction_date = forms.DateTimeField(
        label="Date & Time of Transaction",
        widget=forms.DateTimeInput(
            attrs={'type': 'datetime-local', 'class': 'input input-bordered w-full'},
            format='%Y-%m-%dT%H:%M'  # This part tells Django how to format the date FOR the input field
        ),
        input_formats=['%Y-%m-%dT%H:%M']
    )
    class Meta:
        model = ShopFinancialTransaction
        # These are the fields that could potentially be edited.
        fields = ['transaction_date', 'debit_amount', 'credit_amount', 'notes']
        widgets = {
            # Use a widget that supports both date and time if needed
                'debit_amount': forms.NumberInput(attrs={'class': 'input input-bordered w-full', 'step': '0.01'}),
            'credit_amount': forms.NumberInput(attrs={'class': 'input input-bordered w-full', 'step': '0.01'}),
            'notes': forms.TextInput(attrs={'class': 'input input-bordered w-full'}),
        }
        labels = {
            'debit_amount': 'Debit Amount (Owed by Shop)',
            'credit_amount': 'Credit Amount (Paid by Shop)',
            'notes': 'Edit Reason / Notes'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Important logic: If the transaction was auto-generated from a sale,
        # prevent editing the core financial amounts. Only notes can be changed.
        # This preserves the integrity of your sales records.
        if self.instance and self.instance.source_sale:
            self.fields['debit_amount'].widget.attrs['readonly'] = True
            self.fields['debit_amount'].widget.attrs['class'] += ' bg-base-200' # Visually indicate it's readonly
            
            self.fields['credit_amount'].widget.attrs['readonly'] = True
            self.fields['credit_amount'].widget.attrs['class'] += ' bg-base-200'

            self.fields['transaction_date'].widget.attrs['readonly'] = True
            self.fields['transaction_date'].widget.attrs['class'] += ' bg-base-200'

            # Add a help text to explain why it's read-only
            self.fields['debit_amount'].help_text = "This amount is linked to a sale and cannot be changed here. To correct it, you must process a return for that sale."






class CustomAccountForm(forms.ModelForm):
    """Form for creating a new custom account (the 'card')."""
    class Meta:
        model = CustomAccount
        fields = ['name', 'phone_number', 'notes']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'input input-bordered w-full', 'placeholder': 'e.g., John Doe, Office Expenses'}),
            'phone_number': forms.TextInput(attrs={'class': 'input input-bordered w-full', 'placeholder': 'Optional phone number'}),
            'notes': forms.Textarea(attrs={'class': 'textarea textarea-bordered w-full h-24', 'placeholder': 'Optional notes about this account...'}),
        }

class CustomTransactionEntryForm(forms.ModelForm):
    """Form for adding a debit/credit entry to a CustomAccount ledger."""
    YES_NO_CHOICES = [
        (True, 'Yes'),
        (False, 'No')
    ]

    store_in_daily_summery = forms.ChoiceField(
        choices=YES_NO_CHOICES,
        label="Do You Want To Include It In Daily Summary?",
        widget=forms.Select(attrs={'class': 'select select-bordered w-full'}),
        # Coerce will convert the form's string value ('True'/'False') back to a Python boolean
    )
    class Meta:
        model = CustomAccountTransaction
        fields = ['debit_amount', 'credit_amount', 'notes', 'transaction_date', 'store_in_daily_summery']
        widgets = {
            'debit_amount': forms.NumberInput(attrs={'class': 'input input-bordered w-full', 'step': '0.01', 'value': '0.00'}),
            'credit_amount': forms.NumberInput(attrs={'class': 'input input-bordered w-full', 'step': '0.01', 'value': '0.00'}),
            'notes': forms.TextInput(attrs={'class': 'input input-bordered w-full', 'placeholder': 'e.g., "Loan given", "Payment for supplies"'}),
            'transaction_date': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'input input-bordered w-full','readonly': 'readonly'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set format for datetime widget
        self.fields['transaction_date'].widget.format = '%Y-%m-%dT%H:%M'
        self.fields['transaction_date'].input_formats = ['%Y-%m-%dT%H:%M']
        if not self.instance.pk:
             self.fields['transaction_date'].initial = timezone.now().strftime('%Y-%m-%dT%H:%M')
             self.fields['store_in_daily_summery'].initial = False

    def clean(self):
        cleaned_data = super().clean()
        debit = cleaned_data.get('debit_amount') or Decimal('0.00')
        credit = cleaned_data.get('credit_amount') or Decimal('0.00')
        if debit <= 0 and credit <= 0:
            raise forms.ValidationError("You must enter a value greater than zero for either Debit or Credit.")
        if debit > 0 and credit > 0:
            raise forms.ValidationError("You cannot enter both Debit and Credit. Use two separate entries.")
        return cleaned_data
    



class DateFilterForm(forms.Form):
    date_filter = forms.DateField(
        required=False,
        label="Filter by Date",
        widget=forms.DateInput(
            attrs={
                'class': 'input input-sm input-bordered w-full max-w-xs',
                'type': 'date'
            }
        )
    )