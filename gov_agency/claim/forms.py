from django import forms
from .models import Claim
from stock.models import ProductDetail, Shop, Vehicle # Import from stock app
from decimal import Decimal

class ClaimForm(forms.ModelForm):
      # as it might be pre-set or not applicable for store claims.
    retrieval_vehicle = forms.ModelChoiceField(
        queryset=Vehicle.objects.none(),
        required=False, # It's not always required from the user's perspective
        label="Retrieval Vehicle (if any)",
        widget=forms.Select(attrs={'class': 'select select-bordered w-full'})
    )
    class Meta:
        model = Claim
        fields = [
            'product_detail',
            'quantity_claimed_decimal',
            'claimed_from_shop',
            'retrieval_vehicle',
            'reason',
        ]
        widgets = {
            'product_detail': forms.Select(attrs={'class': 'select select-bordered w-full'}),
            'quantity_claimed_decimal': forms.NumberInput(attrs={
                'class': 'input input-bordered w-full', 'step': '0.01', 'placeholder': 'e.g., 1.05'
            }),
            'claimed_from_shop': forms.Select(attrs={'class': 'select select-bordered w-full'}),
            'retrieval_vehicle': forms.Select(attrs={'class': 'select select-bordered w-full'}),
            'reason': forms.Textarea(attrs={'class': 'textarea textarea-bordered w-full h-24', 'placeholder': 'Reason for claim...'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        preselected_vehicle = kwargs.pop('vehicle_instance', None) 
        print(preselected_vehicle)
        super().__init__(*args, **kwargs)
        if user:
            # Populate dropdowns with user-specific (or all active) items
            # Show only product batches that have stock to claim from
            product_queryset = ProductDetail.objects.filter(user=user, stock__gt=Decimal('0.0')).select_related('product_base')
            self.fields['product_detail'].queryset = product_queryset
            self.fields['product_detail'].label_from_instance = lambda obj: f"{obj.product_base.name} {obj.quantity_in_packing} {obj.unit_of_measure} (Exp: {obj.expirey_date.strftime('%d-%b-%Y')}, Stock: {obj.stock})"
            
            # Assuming shops and vehicles might be global or user-scoped
            self.fields['claimed_from_shop'].queryset = Shop.objects.filter(user=user, is_active=True).order_by('name')
            self.fields['retrieval_vehicle'].queryset = Vehicle.objects.filter(user=user, is_active=True).order_by('vehicle_number')

        self.fields['product_detail'].empty_label = "--- Select Product Batch to Claim ---"
        self.fields['claimed_from_shop'].empty_label = "--- Select Shop (Optional) ---"
        self.fields['retrieval_vehicle'].empty_label = "--- Select Vehicle (Optional, Store Claim if blank) ---"

        if preselected_vehicle:
            self.fields['retrieval_vehicle'].initial = preselected_vehicle

    def clean_quantity_claimed_decimal(self):
        claimed_qty = self.cleaned_data.get('quantity_claimed_decimal')
        product_detail = self.cleaned_data.get('product_detail')

        if product_detail and claimed_qty:
            # Convert decimal quantity to total individual items for validation
            items_to_claim = product_detail._get_items_from_decimal(claimed_qty)
            
            # Validate loose items part of the input
            loose_items_input = int(round((claimed_qty % 1) * 100))
            if loose_items_input >= product_detail.items_per_master_unit:
                 raise forms.ValidationError(f"Loose items part ({loose_items_input}) cannot exceed items per master unit ({product_detail.items_per_master_unit}).")

            # Validate against total available stock
            if items_to_claim > product_detail.total_items_in_stock:
                self.add_error('quantity_claimed_decimal', 
                               f"Cannot claim {items_to_claim} items. Only {product_detail.total_items_in_stock} available in this batch.")
        
        return claimed_qty