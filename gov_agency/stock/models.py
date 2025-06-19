from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator
from datetime import date, timedelta
from decimal import Decimal
# Create your models here.

class AddProduct(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE,  related_name="products")
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at =models.DateField(auto_now=True)

    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ['-created_at'] # Show newest first by default



class ProductDetail(models.Model):
    product_base = models.ForeignKey(AddProduct, null=False, blank=False, on_delete=models.CASCADE, related_name="details")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="product_details_created")
    packing_type = models.CharField(max_length=100,null=False, blank=False, help_text="e.g., Bottle, Box, Carton, PET Jar", default="Carton")

    quantity_in_packing = models.DecimalField(max_digits=10,null=False, blank=False, decimal_places=2 ,validators=[MinValueValidator(0.01)],
    help_text="e.g., 1 (for 1 liter bottle), 0.5 (for 500ml), 12 (for a dozen items)")

    unit_of_measure = models.CharField(max_length=50,null=False, blank=False, help_text="e.g., kg, liter, pieces, meters", default="liter")

    items_per_master_unit = models.PositiveIntegerField(validators=[MinValueValidator(1)],null=False, blank=False,
    help_text="e.g., Number of bottles per PET/Carton, or items per box.")

    price_per_item = models.DecimalField(max_digits=10, decimal_places=2, null=False, blank=False, validators=[MinValueValidator(0.1)],
    help_text="Price for one individual item (e.g., one bottle, one piece).")

    stock = models.DecimalField(max_digits=10,decimal_places=1, blank=False, null=False, validators=[MinValueValidator(0.1)])
    expirey_date = models.DateField(blank=False, null=False, default=date.today() + timedelta(days=30))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.product_base.name} - {self.packing_type} ({self.quantity_in_packing} {self.unit_of_measure})"
    
    class Meta:
        ordering = ['product_base__name', '-created_at']
        unique_together = [['product_base', 'packing_type', 'quantity_in_packing', 'unit_of_measure','expirey_date','stock']]
        verbose_name = "Product Detail/Variant"
        verbose_name_plural = "Product Details/Variants"


    @property
    def total_price_for_master_unit(self):
        if self.price_per_item and self.items_per_master_unit:
            return self.price_per_item * self.items_per_master_unit
        return None    

    @property
    def total_items_in_stock(self):
        if self.stock is None or self.items_per_master_unit is None or self.items_per_master_unit <= 0:
            return 0
        full_master_units = int(self.stock) 
        decimal_part_as_items = int(round((self.stock % 1) * 10)) 
        return (full_master_units * self.items_per_master_unit) + decimal_part_as_items

    
    @property
    def total_price_of_stock(self):
        if self.price_per_item:
            return self.price_per_item * self.total_items_in_stock
        else:
            return None
        

        
    def decrease_stock(self, quantity_to_sell_decimal: Decimal) -> bool:
        """
        Decreases stock by a decimal amount representing master_units.items.
        e.g., quantity_to_sell_decimal = 1.1 means 1 master unit and 1 item.
        Returns True if successful, False if not enough stock or invalid input.
        """
        if not isinstance(quantity_to_sell_decimal, Decimal) or quantity_to_sell_decimal <= Decimal('0.0'):
            return False # Invalid quantity

        # Convert quantity_to_sell_decimal into total individual items to sell
        # using the same logic as total_items_in_stock
        if self.items_per_master_unit is None or self.items_per_master_unit <= 0:
            return False # Cannot process without items_per_master_unit

        full_master_units_to_sell = int(quantity_to_sell_decimal)
        decimal_part_as_items_to_sell = int(round((quantity_to_sell_decimal % 1) * Decimal('10.0')))
        total_individual_items_to_sell = (full_master_units_to_sell * self.items_per_master_unit) + decimal_part_as_items_to_sell

        if self.total_items_in_stock < total_individual_items_to_sell:
            return False # Not enough stock

        # Now, directly subtract the decimal stock amounts if your system is consistent
        # If 1.1 sold from 2.7 stock, new stock should be 1.6
        # This direct subtraction works IF AND ONLY IF your interpretation of the decimal part
        # is consistently "tenths representing items".
        
        # More robust: Convert current stock to total items, subtract items_to_sell, convert back.
        current_total_items = self.total_items_in_stock
        new_total_items = current_total_items - total_individual_items_to_sell

        # Convert new_total_items back to your decimal 'stock' representation
        new_full_master_units = new_total_items // self.items_per_master_unit
        remaining_loose_items = new_total_items % self.items_per_master_unit
        
        new_stock_decimal_part = Decimal(remaining_loose_items) / Decimal('10.0') # e.g. 7 items -> 0.7
        
        self.stock = Decimal(new_full_master_units) + new_stock_decimal_part
        self.save(update_fields=['stock'])
        return True
    

    def sell_one_item(self):
        if self.stock % 1 == 0:
        # e.g., 2.0, 1.0 → full carton
            self.stock -= Decimal('0.5')
        else:
        # e.g., 1.5, 1.4, etc. → partial
            self.stock -= Decimal('0.1')

        if self.stock < 0:
            self.stock = Decimal('0.0')  # prevent negative

    @property
    def display_stock(self):
        return f"{self.stock} cartons"
    

class Sale(models.Model):

    name_of_customer = models.CharField(null=False, max_length=100, blank=False , default="Not Provided")
    """
    Represents a single sale transaction based on the user's diagram.
    """
    product_detail_snapshot = models.ForeignKey('ProductDetail', on_delete=models.CASCADE,related_name='sales_records',
    help_text="The specific product detail (batch) that was sold.")

    # "expiry = foreignkey(product_detail)" - Stored at time of sale, copied from product_detail_snapshot
    expiry_date_at_sale = models.DateField(
        help_text="Expiry date of the product batch at the time of sale."
    )
    stock_before_sale = models.DecimalField(max_digits=10, decimal_places=1,
    help_text="Stock level of the product_detail (in master units) just before this sale transaction.")

    items_per_master_unit_at_sale = models.PositiveIntegerField(
    help_text="Items per master unit for the sold product batch at the time of sale.")

    cost_price_per_item_at_sale = models.DecimalField(max_digits=10, decimal_places=2,
    help_text="Your cost for one individual item of this product at the time of sale.")

    quantity_items_sold =  models.DecimalField(max_digits=10, decimal_places=1,validators=[MinValueValidator(Decimal('0.1'))],default=0.0,
    help_text="Quantity sold in 'master_unit.item' format (e.g., 1.1 for 1 carton and 1 item).")

    selling_price_per_item = models.DecimalField(max_digits=10, decimal_places=2,validators=[MinValueValidator(Decimal('0.01'))],
    help_text="The price each individual item was sold to the customer for.")


    user = models.ForeignKey(User,on_delete=models.SET_NULL,null=True,blank=True,related_name='recorded_sales')
    sale_time = models.DateTimeField(default=timezone.now)

    total_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    def __str__(self):
        return f"Sale of {self.quantity_items_sold} x {self.product_detail_snapshot.product_base.name} on {self.sale_time.strftime('%Y-%m-%d')}"


    def _get_total_individual_items_from_decimal_quantity(self, decimal_quantity: Decimal) -> int:
        """Helper to convert 1.1 (1 carton, 1 item) to total individual items."""
        if self.items_per_master_unit_at_sale is None or self.items_per_master_unit_at_sale <= 0:
            if self.product_detail_snapshot and self.product_detail_snapshot.items_per_master_unit:
                items_per_mu = self.product_detail_snapshot.items_per_master_unit
            else:
                return int(round(decimal_quantity * 10)) # Fallback to assuming .1 is 1 item always
        else:
            items_per_mu = self.items_per_master_unit_at_sale

        full_units = int(decimal_quantity)
        decimal_part_items = int(round((decimal_quantity % 1) * Decimal('10.0')))
        return (full_units * items_per_mu) + decimal_part_items
    

    @property
    def total_individual_items_sold_in_transaction(self):
        return self._get_total_individual_items_from_decimal_quantity(self.quantity_items_sold)
    

    @property
    def calculated_profit(self):
        if self.total_revenue is not None and self.total_cost is not None:
            return self.total_revenue - self.total_cost
        return Decimal('0.00')

    def save(self, *args, **kwargs):
        # Populate snapshot fields if creating a new sale and product_detail_snapshot is set
        if not self.pk and self.product_detail_snapshot: # If new instance and product_detail is linked
            self.expiry_date_at_sale = self.product_detail_snapshot.expirey_date
            self.stock_before_sale = self.product_detail_snapshot.stock # Stock before this sale's deduction
            self.items_per_master_unit_at_sale = self.product_detail_snapshot.items_per_master_unit
            self.cost_price_per_item_at_sale = self.product_detail_snapshot.price_per_item

        # Calculate totals
        if self.quantity_items_sold and self.selling_price_per_item:
            total_individual_items_sold_count = self._get_total_individual_items_from_decimal_quantity(self.quantity_items_sold)

            self.total_revenue = Decimal(total_individual_items_sold_count) * self.selling_price_per_item
        if self.quantity_items_sold and self.cost_price_per_item_at_sale:
            self.total_cost = Decimal(total_individual_items_sold_count) * self.cost_price_per_item_at_sale
        
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-sale_time']
        verbose_name = "Sale Record"
        verbose_name_plural = "Sale Records"


# vehical  model 
class Vehicle(models.Model):
    VEHICLE_TYPE_CHOICES = [
        ('TRUCK', 'Truck'),
        ('VAN', 'Van'),
        ('CAR', 'Car'),
        ('MOTORCYCLE', 'Motorcycle'),
        ('OTHER', 'Other'),
    ]

    # Link to the user who added/manages this vehicle entry
    # If vehicles are global, you might not need this or make it optional.
    # For now, let's assume a user "owns" or "manages" the vehicle entry.
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="vehicles")
    
    vehicle_number = models.CharField(max_length=20, unique=True, help_text="e.g., ABC-123 or S1234XYZ")
    vehicle_type = models.CharField(max_length=20, choices=VEHICLE_TYPE_CHOICES, default='TRUCK')
    driver_name = models.CharField(max_length=100, blank=True, null=True)
    driver_phone = models.CharField(max_length=20, blank=True, null=True)
    capacity_kg = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, help_text="Optional: Vehicle capacity in kilograms")
    notes = models.TextField(blank=True, null=True)
    
    is_active = models.BooleanField(default=True, help_text="Is this vehicle currently in service?")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.vehicle_number} ({self.get_vehicle_type_display()})"

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Vehicle"
        verbose_name_plural = "Vehicles"



# shop model ...........
class Shop(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="shops_managed")
    name = models.CharField(max_length=150, unique=True)
    location_address = models.TextField(blank=True, null=True)
    contact_person = models.CharField(max_length=100, blank=True, null=True)
    contact_phone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(max_length=100, blank=True, null=True)
    
    # You could add more fields like:
    # shop_type = models.CharField(max_length=50, blank=True, null=True, help_text="e.g., Retail, Wholesale")
    # registration_number = models.CharField(max_length=50, blank=True, null=True)
    
    is_active = models.BooleanField(default=True, help_text="Is this shop currently operational?")
    notes = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name'] # Order by name alphabetically
        verbose_name = "Shop"
        verbose_name_plural = "Shops"