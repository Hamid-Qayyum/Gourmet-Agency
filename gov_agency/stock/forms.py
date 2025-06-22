from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import AddProduct,ProductDetail,Sale, Vehicle, Shop,SalesTransaction,SalesTransactionItem
from decimal import Decimal
from django.core.validators import MinValueValidator
from django.forms import modelformset_factory



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
    



class AddItemToSaleForm(forms.Form):
    """Form to add a single product batch and its quantity to the current sale."""
    product_detail_batch = forms.ModelChoiceField(
        queryset=ProductDetail.objects.none(), # Populated based on the user in the view
        label="Select Product Batch",
        widget=forms.Select(attrs={'class': 'select select-bordered w-full', 'id': 'add_item_product_batch_select'})
    )
    
    # Readonly display fields (populated by JS)
    available_stock_display = forms.CharField(label="Stock (MasterUnits.Items)", required=False, widget=forms.TextInput(attrs={'readonly': True, 'class': 'input input-bordered input-sm w-full bg-base-200', 'id': 'add_item_available_stock'}))
    total_items_available_display = forms.CharField(label="Total Items Available", required=False, widget=forms.TextInput(attrs={'readonly': True, 'class': 'input input-bordered input-sm w-full bg-base-200', 'id': 'add_item_total_items'}))
    cost_price_display = forms.CharField(label="Your Cost/Item", required=False, widget=forms.TextInput(attrs={'readonly': True, 'class': 'input input-bordered input-sm w-full bg-base-200', 'id': 'add_item_cost_price'}))

    # User inputs for this item
    quantity_to_add = forms.DecimalField(
        label="Quantity to Add (e.g., 1.1 for 1 Carton + 1 Item)",
        max_digits=10, decimal_places=1,
        validators=[MinValueValidator(Decimal('0.1'))],
        initial=Decimal('0.1'),
        widget=forms.NumberInput(attrs={'class': 'input input-bordered w-full', 'id': 'add_item_quantity_to_add', 'step': '0.1'})
    )
    selling_price_per_item = forms.DecimalField(
        label="Selling Price per INDIVIDUAL Item for this batch",
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        widget=forms.NumberInput(attrs={'class': 'input input-bordered w-full', 'id': 'add_item_selling_price', 'step': '0.01'})
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['product_detail_batch'].queryset = ProductDetail.objects.filter(
                user=user, stock__gt=Decimal('0.0') # Only show batches with stock
            ).select_related('product_base').order_by('product_base__name', 'expirey_date')
            self.fields['product_detail_batch'].label_from_instance = lambda obj: f"{obj.product_base.name} (Exp: {obj.expirey_date.strftime('%d-%b-%Y')}, Stock: {obj.stock})"
        self.fields['product_detail_batch'].empty_label = "--- Select Product Batch to Add ---"

    def clean(self):
        cleaned_data = super().clean()
        product_detail_batch = cleaned_data.get('product_detail_batch')
        quantity_to_add_decimal = cleaned_data.get('quantity_to_add')

        if product_detail_batch and quantity_to_add_decimal:
            # Convert decimal quantity (e.g., 1.1) to total individual items
            items_per_mu = product_detail_batch.items_per_master_unit
            if not (items_per_mu and items_per_mu > 0):
                 self.add_error('product_detail_batch', "Selected product has invalid configuration.")
                 return cleaned_data

            full_units_to_add = int(quantity_to_add_decimal)
            decimal_part_items_to_add = int(round((quantity_to_add_decimal % 1) * Decimal('10.0')))
            total_individual_items_being_added = (full_units_to_add * items_per_mu) + decimal_part_items_to_add

            if total_individual_items_being_added <= 0:
                self.add_error('quantity_to_add', "Quantity must result in at least one item.")
            
            # Check against ProductDetail's total_items_in_stock property
            if hasattr(product_detail_batch, 'total_items_in_stock'):
                if total_individual_items_being_added > product_detail_batch.total_items_in_stock:
                    self.add_error('quantity_to_add', 
                                   f"Not enough. Adding {quantity_to_add_decimal} ({total_individual_items_being_added} items), but only {product_detail_batch.total_items_in_stock} items available.")
            else:
                self.add_error(None, "Stock verification error on ProductDetail model.")
        return cleaned_data


class FinalizeSaleForm(forms.Form):
    """Form for final details when completing a sale with multiple items."""
    customer_shop = forms.ModelChoiceField(
        queryset=Shop.objects.none(), required=False, label="Select Registered Shop (Optional)",
        widget=forms.Select(attrs={'class': 'select select-bordered w-full'})
    )
    customer_name_manual = forms.CharField(
        max_length=200, required=False, label="Or Enter Customer Name",
        widget=forms.TextInput(attrs={'class': 'input input-bordered w-full', 'placeholder': 'e.g., John Doe'})
    )
    payment_type = forms.ChoiceField(
        choices=SalesTransaction.PAYMENT_TYPE_CHOICES,
        widget=forms.Select(attrs={'class': 'select select-bordered w-full'})
    )
    needs_vehicle = forms.BooleanField(
        required=False, label="Assign Vehicle for Delivery?",
        widget=forms.CheckboxInput(attrs={'class': 'checkbox checkbox-primary', 'id': 'finalize_sale_needs_vehicle'})
    )
    assigned_vehicle = forms.ModelChoiceField(
        queryset=Vehicle.objects.none(), required=False, label="Assign Vehicle",
        widget=forms.Select(attrs={'class': 'select select-bordered w-full', 'id': 'finalize_sale_assigned_vehicle'})
    )
    notes = forms.CharField(widget=forms.Textarea(attrs={'class': 'textarea textarea-bordered w-full h-20', 'placeholder': 'Optional notes for the entire sale...'}), required=False)


    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['customer_shop'].queryset = Shop.objects.filter(user=user).order_by('name') # Or global if applicable
            self.fields['assigned_vehicle'].queryset = Vehicle.objects.filter(user=user, is_active=True).order_by('vehicle_number')
        self.fields['customer_shop'].empty_label = "--- Select Registered Shop ---"
        self.fields['assigned_vehicle'].empty_label = "--- Select Vehicle (If Needed) ---"

    def clean(self):
        cleaned_data = super().clean()
        customer_shop = cleaned_data.get('customer_shop')
        customer_name_manual = cleaned_data.get('customer_name_manual')
        needs_vehicle = cleaned_data.get('needs_vehicle')
        assigned_vehicle = cleaned_data.get('assigned_vehicle')

        if not customer_shop and not customer_name_manual:
            self.add_error('customer_shop', "Please select a shop or enter a customer name.")
        if needs_vehicle and not assigned_vehicle:
            self.add_error('assigned_vehicle', "Please assign a vehicle if delivery is needed.")
        return cleaned_data


class SalesTransactionItemReturnForm(forms.ModelForm):
    """Form for a single SalesTransactionItem to input returned quantity."""
    # Make product display read-only for context
    product_display = forms.CharField(
        label="Product Batch",
        required=False, # Not part of model, just for display
        widget=forms.TextInput(attrs={'readonly': True, 'class': 'input input-sm input-bordered w-full bg-base-200'})
    )
    dispatched_quantity_display = forms.CharField(
        label="Qty Dispatched",
        required=False,
        widget=forms.TextInput(attrs={'readonly': True, 'class': 'input input-sm input-bordered w-full bg-base-200'})
    )

    class Meta:
        model = SalesTransactionItem
        fields = ['returned_quantity_decimal'] # Only this field is editable
        widgets = {
            'returned_quantity_decimal': forms.NumberInput(attrs={
                'class': 'input input-sm input-bordered w-full',
                'step': '0.1',
                'min': '0.0' # Client-side validation
            })
        }
        labels = {
            'returned_quantity_decimal': 'Quantity Returned (e.g., 0.2)'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['product_display'].initial = f"{self.instance.product_detail_snapshot.product_base.name} (Exp: {self.instance.expiry_date_at_sale.strftime('%d-%b-%y')})"
            self.fields['dispatched_quantity_display'].initial = str(self.instance.quantity_sold_decimal)
            # Set max value for returned quantity based on dispatched quantity for this item
            self.fields['returned_quantity_decimal'].widget.attrs['max'] = str(self.instance.quantity_sold_decimal)
        
        # Reorder fields if needed
        field_order = ['product_display', 'dispatched_quantity_display', 'returned_quantity_decimal']
        self.order_fields(field_order)


    def clean_returned_quantity_decimal(self):
        returned_qty = self.cleaned_data.get('returned_quantity_decimal')
        if returned_qty is None: # If field was optional and left blank
            returned_qty = Decimal('0.0')
        
        if self.instance and self.instance.pk: # Ensure instance exists (it should for an update)
            dispatched_qty = self.instance.quantity_sold_decimal
            if returned_qty > dispatched_qty:
                raise forms.ValidationError(f"Returned quantity ({returned_qty}) cannot exceed dispatched quantity ({dispatched_qty}) for this item.")
            if returned_qty < Decimal('0.0'):
                raise forms.ValidationError("Returned quantity cannot be negative.")
        return returned_qty

# Create a FormSet based on the SalesTransactionItemReturnForm
# We will typically instantiate this in the view with a queryset of items for a specific transaction
SalesTransactionItemReturnFormSet = modelformset_factory(
    SalesTransactionItem, 
    form=SalesTransactionItemReturnForm, 
    extra=0, # Don't show extra blank forms
    can_delete=False # We are not deleting items here, only updating return quantity
)


class SaleForm(forms.Form): # Not a ModelForm because of dynamic/conditional fields
    product_detail_batch = forms.ModelChoiceField(
        queryset=ProductDetail.objects.none(), 
        label="Select Product Batch",
        widget=forms.Select(attrs={'class': 'select select-bordered w-full', 'id': 'sale_form_product_batch'})
    )
    # Customer selection: Shop or Manual Name
    customer_shop = forms.ModelChoiceField(
        queryset=Shop.objects.none(), # To be populated based on user if shops are user-specific
        required=False,
        label="Select Registered Shop (Optional)",
        widget=forms.Select(attrs={'class': 'select select-bordered w-full', 'id': 'sale_form_customer_shop'})
    )
    customer_name_manual = forms.CharField(
        max_length=200, required=False, label="Or Enter Customer Name",
        widget=forms.TextInput(attrs={'class': 'input input-bordered w-full', 'placeholder': 'e.g., John Doe or Local Store'})
    )

    # Readonly display fields (populated by JS)
    current_stock_display = forms.CharField(label="Current Stock", required=False, widget=forms.TextInput(attrs={'readonly': True, 'class': 'input input-bordered w-full bg-base-200', 'id': 'sale_form_current_stock'}))
    total_items_available_display = forms.CharField(label="Total Items Available", required=False, widget=forms.TextInput(attrs={'readonly': True, 'class': 'input input-bordered w-full bg-base-200', 'id': 'sale_form_total_items'}))
    cost_price_display = forms.CharField(label="Your Cost/Item", required=False, widget=forms.TextInput(attrs={'readonly': True, 'class': 'input input-bordered w-full bg-base-200', 'id': 'sale_form_cost_price'}))

    quantity_to_sell = forms.DecimalField(
        label="Quantity to Sell (e.g., 1.1 for 1 Carton, 1 Item)",
        max_digits=10, decimal_places=1,
        validators=[MinValueValidator(Decimal('0.1'))],
        widget=forms.NumberInput(attrs={'class': 'input input-bordered w-full', 'id': 'sale_form_quantity_to_sell', 'step': '0.1'})
    )
    selling_price_per_item = forms.DecimalField(
        label="Selling Price per INDIVIDUAL Item",
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        widget=forms.NumberInput(attrs={'class': 'input input-bordered w-full', 'id': 'sale_form_selling_price', 'step': '0.01'})
    )
    payment_type = forms.ChoiceField(
        choices=Sale.PAYMENT_TYPE_CHOICES,
        widget=forms.Select(attrs={'class': 'select select-bordered w-full'})
    )
    needs_vehicle = forms.BooleanField(
        required=False, 
        label="Assign Vehicle for Delivery?",
        widget=forms.CheckboxInput(attrs={'class': 'checkbox checkbox-primary', 'id': 'sale_form_needs_vehicle'})
    )
    assigned_vehicle = forms.ModelChoiceField(
        queryset=Vehicle.objects.none(), # Populated based on user
        required=False, # Only required if needs_vehicle is checked (handled in JS/view)
        label="Assign Vehicle",
        widget=forms.Select(attrs={'class': 'select select-bordered w-full', 'id': 'sale_form_assigned_vehicle'})
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['product_detail_batch'].queryset = ProductDetail.objects.filter(
                user=user, stock__gt=Decimal('0.0')
            ).select_related('product_base').order_by('product_base__name', 'expirey_date')
            self.fields['product_detail_batch'].label_from_instance = lambda obj: f"{obj.product_base.name} (Exp: {obj.expirey_date.strftime('%d-%b-%Y')}, Stock: {obj.stock})"
            
            # Assuming shops and vehicles are also user-specific. If global, remove user filter.
            self.fields['customer_shop'].queryset = Shop.objects.filter(user=user).order_by('name')
            self.fields['assigned_vehicle'].queryset = Vehicle.objects.filter(user=user, is_active=True).order_by('vehicle_number')
        
        self.fields['product_detail_batch'].empty_label = "--- Select Product Batch ---"
        self.fields['customer_shop'].empty_label = "--- Select Registered Shop (Optional) ---"
        self.fields['assigned_vehicle'].empty_label = "--- Select Vehicle (If Needed) ---"

    def clean(self):
        cleaned_data = super().clean()
        product_detail_batch = cleaned_data.get('product_detail_batch')
        quantity_to_sell_decimal = cleaned_data.get('quantity_to_sell')
        needs_vehicle = cleaned_data.get('needs_vehicle')
        assigned_vehicle = cleaned_data.get('assigned_vehicle')
        customer_shop = cleaned_data.get('customer_shop')
        customer_name_manual = cleaned_data.get('customer_name_manual')

        if not customer_shop and not customer_name_manual:
            self.add_error('customer_shop', "Either select a registered shop or enter a customer name.")
            self.add_error('customer_name_manual', " ") # Add to both for visibility

        if product_detail_batch and quantity_to_sell_decimal:
            items_per_mu = product_detail_batch.items_per_master_unit
            if not (items_per_mu and items_per_mu > 0):
                 self.add_error('product_detail_batch', "Selected product has invalid configuration (items per master unit).")
                 return cleaned_data # Stop further validation for this field

            full_units_to_sell = int(quantity_to_sell_decimal)
            decimal_part_items_to_sell = int(round((quantity_to_sell_decimal % 1) * Decimal('10.0')))
            total_individual_items_being_sold = (full_units_to_sell * items_per_mu) + decimal_part_items_to_sell
            
            if total_individual_items_being_sold <= 0:
                self.add_error('quantity_to_sell', "Quantity to sell must result in at least one item.")

            if product_detail_batch.total_items_in_stock < total_individual_items_being_sold:
                self.add_error('quantity_to_sell', 
                               f"Not enough items. Selling {quantity_to_sell_decimal} ({total_individual_items_being_sold} items), but only {product_detail_batch.total_items_in_stock} items available.")
        
        if needs_vehicle and not assigned_vehicle:
            self.add_error('assigned_vehicle', "Please assign a vehicle if delivery is needed.")
            
        return cleaned_data
    

class ProcessReturnForm(forms.Form):
    returned_stock_decimal = forms.DecimalField(
        label="Quantity Returned (e.g., 0.2 for 2 items)",
        max_digits=10,
        decimal_places=1,
        required=False, # Can be zero if all items were delivered and none returned
        initial=Decimal('0.0'),
        validators=[MinValueValidator(Decimal('0.0'))], # Allow 0
        widget=forms.NumberInput(attrs={
            'class': 'input input-bordered w-full',
            'step': '0.1',
            'placeholder': 'e.g., 0.0 or 0.3'
        }),
        help_text="Enter in 'Carton.Item' format, e.g., 0.2 for 2 items if 1 carton has >2 items."
    )
    # You could add a notes field for the return here if needed
    # return_notes = forms.CharField(widget=forms.Textarea, required=False)

    def __init__(self, *args, **kwargs):
        self.sale_instance = kwargs.pop('sale_instance', None) # Pass the Sale instance
        super().__init__(*args, **kwargs)

    def clean_returned_stock_decimal(self):
        returned_quantity = self.cleaned_data.get('returned_stock_decimal')
        
        if returned_quantity is None: # If not required and left blank
            return Decimal('0.0') 
            
        if self.sale_instance and returned_quantity > self.sale_instance.quantity_sold_decimal:
            raise forms.ValidationError(
                f"Returned quantity ({returned_quantity}) cannot exceed dispatched quantity ({self.sale_instance.quantity_sold_decimal})."
            )
        return returned_quantity


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