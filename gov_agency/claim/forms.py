# claim/forms.py

from django import forms
from .models import Claim
from stock.models import ProductDetail, Shop, Vehicle
from decimal import Decimal

class AddClaimItemForm(forms.Form):
    product_detail = forms.ModelChoiceField(
        queryset=ProductDetail.objects.all(), # We will filter this in the view
        label="Select Product",
        widget=forms.Select(attrs={'class': 'select select-bordered w-full'})
    )
    quantity = forms.DecimalField(
        label="Quantity (e.g., 1.05)",
        max_digits=10, decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'input input-bordered w-full', 'step': '0.01', 'placeholder': '0.00'})
    )
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        # Add a flag for exchanged items to filter stock
        for_exchange = kwargs.pop('for_exchange', False)
        super().__init__(*args, **kwargs)
        if user:
            queryset = ProductDetail.objects.filter(user=user).select_related('product_base')
            if for_exchange: # Only show items with stock if we are giving them away
                queryset = queryset.filter(stock__gt=Decimal('0.00'))
            self.fields['product_detail'].queryset = queryset.order_by('product_base__name', 'expirey_date')
            self.fields['product_detail'].label_from_instance = lambda obj: f"{obj.product_base.name} {obj.quantity_in_packing} {obj.unit_of_measure} (Exp: {obj.expirey_date.strftime('%d-%b-%Y')})"
        self.fields['product_detail'].empty_label = "--- Select a Product ---"

class FinalizeClaimForm(forms.ModelForm):
    class Meta:
        model = Claim
        fields = ['claimed_from_shop', 'retrieval_vehicle', 'reason']
        widgets = {
            'claimed_from_shop': forms.Select(attrs={'class': 'select select-bordered w-full'}),
            'retrieval_vehicle': forms.Select(attrs={'class': 'select select-bordered w-full'}),
            'reason': forms.Textarea(attrs={'class': 'textarea textarea-bordered w-full h-24', 'placeholder': 'Reason for claim...'}),
        }
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['claimed_from_shop'].queryset = Shop.objects.filter(user=user)
            self.fields['retrieval_vehicle'].queryset = Vehicle.objects.filter(user=user, is_active=True)
        self.fields['claimed_from_shop'].empty_label = "--- Select Shop (Optional) ---"
        self.fields['retrieval_vehicle'].empty_label = "--- Select Vehicle (Optional) ---"