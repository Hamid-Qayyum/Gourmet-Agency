from django import forms
from .models import ShopFinancialTransaction # Import the model from this app
from decimal import Decimal
from django.core.validators import MinValueValidator

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