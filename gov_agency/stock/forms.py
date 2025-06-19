from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import AddProduct,ProductDetail,Sale, Vehicle, Shop
from decimal import Decimal
from django.core.validators import MinValueValidator




class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']



class AddProductForm(forms.ModelForm):
    class Meta:
        model = AddProduct
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'input input-bordered w-full', # DaisyUI class
                'placeholder': 'Enter product name',
                'id': 'id_product_name_modal'
            }),
            'description': forms.Textarea(attrs={
                'class': 'textarea textarea-bordered w-full h-24', # DaisyUI class
                'placeholder': 'Optional description',
                'id': 'id_product_description_modal'
            }),
        }



class ProductDetailForm(forms.ModelForm):
    product_base = forms.ModelChoiceField(
        queryset=AddProduct.objects.all(), widget=forms.Select(attrs={'class': 'form-select daisy-select w-full'}))
    class Meta:
        model = ProductDetail
        fields =  [
            'product_base', 
            'packing_type', 
            'quantity_in_packing', 
            'unit_of_measure', 
            'items_per_master_unit', 
            'price_per_item', 
            'stock',
            'expirey_date'
        ]
        widgets = {
            'product_base': forms.Select(attrs={
                'class': 'select select-bordered w-full' # DaisyUI class
            }),
            'packing_type': forms.TextInput(attrs={
                'class': 'input input-bordered w-full', 
                'placeholder': 'e.g., Bottle, Box, Carton'
            }),
            'quantity_in_packing': forms.NumberInput(attrs={
                'class': 'input input-bordered w-full', 
                'placeholder': 'e.g., 1 or 0.5 or 12',
                'step': '0.01' # For decimal fields
            }),
            'unit_of_measure': forms.TextInput(attrs={
                'class': 'input input-bordered w-full', 
                'placeholder': 'e.g., liter, kg, pieces'
            }),
            'items_per_master_unit': forms.NumberInput(attrs={
                'class': 'input input-bordered w-full', 
                'placeholder': 'e.g., 12 (bottles per carton)',
                'step': '1' # For integer fields
            }),
            'price_per_item': forms.NumberInput(attrs={
                'class': 'input input-bordered w-full', 
                'placeholder': 'e.g., 10.99',
                'step': '0.1' 
            }),
            'expirey_date': forms.DateInput(attrs={
                'type':'date',
                'class': 'date  w-full', 
                'placeholder': 'Enter expiery date...'
            }),
            'stock': forms.NumberInput(attrs={
                'class': 'input input-bordered w-full', 
                'placeholder': 'Stock...'
            }),
        }
        labels = {
            'product_base': 'Base Product Name',
            'packing_type': 'Type of Packaging',
            'quantity_in_packing': 'Quantity in Pack',
            'unit_of_measure': 'Unit (Liters, kg, pcs)',
            'items_per_master_unit': 'Items per Master Unit',
            'price_per_item': 'Price per Single Item',
            'expirey_date': 'Expirey Date',
            'stock':'New Stock'
        }


    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args,**kwargs)
        if self.user:
            self.fields['product_base'].queryset = AddProduct.objects.filter(user=self.user).order_by('name')
        self.fields['product_base'].empty_label = None

    def clean_price_per_item(self):
        price = self.cleaned_data.get('price_per_item')
        if price and price <= 0:
            raise forms.ValidationError("Price must be greater than zero.")
        return price
    
    def clean_stock(self):
        stock = self.cleaned_data.get('stock')
        items_per_carton = self.cleaned_data.get('items_per_master_unit')
        if stock and items_per_carton:
            full_cartons = int(stock)
            remaining_items = (stock - Decimal(full_cartons)) * 10  # .5 means 5 items
            if remaining_items >= items_per_carton:
                raise forms.ValidationError("Remaining items cannot be greater than or equal to items per carton.")
            return stock
            


    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('some_field') == 'value' and cleaned_data.get('other_field') < 10:
            raise forms.ValidationError("Specific error based on multiple fields.")
        return cleaned_data
    




class SaleForm(forms.Form):

    product_detail_batch = forms.ModelChoiceField(
        queryset=ProductDetail.objects.none(), # To be populated based on the user
        label="Select Product Batch",
        widget=forms.Select(attrs={'class': 'select select-bordered w-full', 'id': 'sale_form_product_batch'})
        )
    name_of_customer = forms.CharField(
        max_length=200,
        required=False,
        label="Customer Name (Optional)",
        widget=forms.TextInput(attrs={'class': 'input input-bordered w-full', 'placeholder': 'Enter customer name'})
    )

    # "stock = auto_filled (from product_detail)" - Display only field
    current_stock_display = forms.CharField(
        label="Current Stock (Master Units)",
        required=False,
        widget=forms.TextInput(attrs={'class': 'input input-bordered w-full', 'readonly': True, 'id': 'sale_form_current_stock'})
    )

    # "number_of_items = auto_filled (from product_detail)" - Display only field (total individual items)
    total_items_available_display = forms.CharField(
        label="Total Individual Items Available",
        required=False,
        widget=forms.TextInput(attrs={'class': 'input input-bordered w-full', 'readonly': True, 'id': 'sale_form_total_items'})
    )

    # "price_of_eact_product = auto_filled(product_detail)" - This is your cost price. Display only.
    cost_price_display = forms.CharField(
        label="Your Cost Price per Item",
        required=False,
        widget=forms.TextInput(attrs={'class': 'input input-bordered w-full', 'readonly': True, 'id': 'sale_form_cost_price'})
    )
    
    # "number_of_products_to_sell= float field" - Changed to IntegerField for items
    quantity_items_to_sell = forms.DecimalField(
        max_digits=10,
        decimal_places=1,
        validators=[MinValueValidator(Decimal('0.1'))],
        label="Number of Items to Sell",
        widget=forms.NumberInput(attrs={'class': 'input input-bordered w-full', 'placeholder': 'e.g., 1.1 or 2.5'})
    )

    # "selling_price_of_eact_product = float field" - Changed to DecimalField
    selling_price_per_item = forms.DecimalField(
        label="Selling Price per Item",
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        widget=forms.NumberInput(attrs={'class': 'input input-bordered w-full', 'placeholder': 'e.g., 12.50', 'step': '0.01'})
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None) # Get the user passed from the view
        super().__init__(*args, **kwargs)
        
        if user:
            # Populate the product_detail_batch choices for product details
            # owned by the user and having stock > 0.
            self.fields['product_detail_batch'].queryset = ProductDetail.objects.filter(
                user=user, 
                stock__gt=Decimal('0.0') # Only show batches with some stock
            ).select_related('product_base').order_by('product_base__name', 'expirey_date')
            
            # Customize how each choice is displayed in the dropdown
            self.fields['product_detail_batch'].label_from_instance = lambda obj: f"{obj.product_base.name} (Exp: {obj.expirey_date.strftime('%d-%b-%Y')}, Stock: {obj.stock} {obj.product_base.name}s)"
        
        self.fields['product_detail_batch'].empty_label = "--- Select Product ---"

    def clean(self):
        cleaned_data = super().clean()
        product_detail_batch = cleaned_data.get('product_detail_batch')
        quantity_items_to_sell = cleaned_data.get('quantity_items_to_sell')

        if product_detail_batch and quantity_items_to_sell:
            # Ensure quantity to sell does not exceed available individual items
            # Relies on ProductDetail having a property `total_items_in_stock`
            if hasattr(product_detail_batch, 'total_items_in_stock'):
                available_items = product_detail_batch.total_items_in_stock
                if quantity_items_to_sell > available_items:
                    self.add_error('quantity_items_to_sell', 
                                   f"Not enough items in stock. Only {available_items} individual items available for this batch.")
            else:
                self.add_error(None, "Could not verify stock levels due to missing information on ProductDetail model.")   
        return cleaned_data
    



# vehicle form.......
class VehicleForm(forms.ModelForm):
    class Meta:
        model = Vehicle
        # Exclude 'user', 'created_at', 'updated_at' as they are handled automatically
        fields = [
            'vehicle_number', 
            'vehicle_type', 
            'driver_name', 
            'driver_phone', 
            'capacity_kg', 
            'notes',
            'is_active'
        ]
        widgets = {
            'vehicle_number': forms.TextInput(attrs={
                'class': 'input input-bordered w-full',
                'placeholder': 'e.g., LEA-1234'
            }),
            'vehicle_type': forms.Select(attrs={
                'class': 'select select-bordered w-full'
            }),
            'driver_name': forms.TextInput(attrs={
                'class': 'input input-bordered w-full',
                'placeholder': "Driver's full name"
            }),
            'driver_phone': forms.TextInput(attrs={
                'class': 'input input-bordered w-full',
                'placeholder': 'e.g., +1234567890'
            }),
            'capacity_kg': forms.NumberInput(attrs={
                'class': 'input input-bordered w-full',
                'placeholder': 'e.g., 1000.00',
                'step': '0.01'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'textarea textarea-bordered w-full h-24',
                'placeholder': 'Any additional notes about the vehicle...'
            }),
            'is_active': forms.CheckboxInput(attrs={ # DaisyUI will style this
                'class': 'checkbox checkbox-primary align-middle' 
            })
        }
        labels = {
            'vehicle_number': 'Vehicle Registration Number',
            'vehicle_type': 'Type of Vehicle',
            'driver_name': "Driver's Name",
            'driver_phone': "Driver's Phone Number",
            'capacity_kg': 'Capacity (kg, Optional)',
            'is_active': 'Vehicle is Active',
        }





class ShopForm(forms.ModelForm):
    class Meta:
        model = Shop
        # Exclude 'user', 'created_at', 'updated_at'
        fields = [
            'name', 
            'location_address', 
            'contact_person', 
            'contact_phone', 
            'email',
            'is_active',
            'notes'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'input input-bordered w-full',
                'placeholder': 'Enter shop name'
            }),
            'location_address': forms.Textarea(attrs={
                'class': 'textarea textarea-bordered w-full h-20',
                'placeholder': 'Full address of the shop'
            }),
            'contact_person': forms.TextInput(attrs={
                'class': 'input input-bordered w-full',
                'placeholder': "Shop manager or owner's name"
            }),
            'contact_phone': forms.TextInput(attrs={
                'class': 'input input-bordered w-full',
                'placeholder': 'e.g., +1234567890'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'input input-bordered w-full',
                'placeholder': 'shop@example.com'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'textarea textarea-bordered w-full h-24',
                'placeholder': 'Any additional notes about the shop...'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'checkbox checkbox-primary align-middle'
            })
        }
        labels = {
            'name': 'Shop Name',
            'location_address': 'Location / Address',
            'contact_person': 'Contact Person',
            'contact_phone': 'Contact Phone',
            'email': 'Shop Email Address',
            'is_active': 'Shop is Active',
        }