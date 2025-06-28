from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator
from datetime import date, timedelta
from decimal import Decimal
from django.db.models import Sum

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
    
    def increase_stock(self, quantity_to_add_decimal: Decimal) -> bool:
        """
        Increases stock by a decimal amount representing master_units.items (e.g., returned stock).
        e.g., quantity_to_add_decimal = 0.2 means 2 items are being added back.
        Returns True if successful.
        """
        if not isinstance(quantity_to_add_decimal, Decimal) or quantity_to_add_decimal < Decimal('0.0'):
            # Allow adding 0 stock (no return), but not negative.
            if quantity_to_add_decimal == Decimal('0.0'):
                return True # No change, but operation is "successful"
            return False # Invalid quantity

        # Convert quantity_to_add_decimal into total individual items to add
        if self.items_per_master_unit is None or self.items_per_master_unit <= 0:
            return False # Cannot process without items_per_master_unit

        full_master_units_to_add = int(quantity_to_add_decimal)
        # Assumes .1 = 1 item, .2 = 2 items etc. for the decimal part
        decimal_part_as_items_to_add = int(round((quantity_to_add_decimal % 1) * Decimal('10.0')))
        total_individual_items_to_add = (full_master_units_to_add * self.items_per_master_unit) + decimal_part_as_items_to_add

        if total_individual_items_to_add < 0: # Should be caught by earlier check but as a safeguard
            return False

        # Convert current stock to total items, add new items, then convert back to decimal stock format
        current_total_items = self.total_items_in_stock
        new_total_items = current_total_items + total_individual_items_to_add

        # Convert new_total_items back to your decimal 'stock' representation
        new_full_master_units = new_total_items // self.items_per_master_unit
        remaining_loose_items = new_total_items % self.items_per_master_unit
        
        new_stock_decimal_part = Decimal(remaining_loose_items) / Decimal('10.0') # e.g. 7 items -> 0.7
        
        self.stock = Decimal(new_full_master_units) + new_stock_decimal_part
        self.save(update_fields=['stock'])
        return True
    
    def _get_individual_items_from_decimal(self, decimal_qty: Decimal, items_per_mu: int) -> int:
        """Helper to convert X.Y decimal (e.g., 1.1 cartons) to total individual items (e.g., 7 items)."""
        if decimal_qty is None or items_per_mu is None or items_per_mu <= 0:
            return 0
        full_units = int(decimal_qty)
        # Assumes .1 in decimal_qty means 1 item, .2 means 2 items, etc.
        decimal_part_items = int(round((decimal_qty % 1) * Decimal('10.0')))
        return (full_units * items_per_mu) + decimal_part_items

    

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
    


class SalesTransaction(models.Model):
    """
    Represents the header of a single sales transaction, which can contain multiple items.
    """
    # Choices for fields
    PAYMENT_TYPE_CHOICES = [
        ('CASH', 'Cash on Hand'),
        ('ONLINE', 'Online Transfer'),
        ('CREDIT', 'Credit'),
    ]
    SALE_STATUS_CHOICES = [
        ('PENDING_ITEMS', 'Pending Items'),     # Cart is being built, not yet finalized
        ('PENDING_DELIVERY', 'Pending Delivery'), # Finalized, vehicle assigned, awaiting delivery confirmation
        ('COMPLETED', 'Completed'),             # Delivered, or no delivery needed and paid
        ('PARTIALLY_RETURNED', 'Partially Returned'),
        ('FULLY_RETURNED', 'Fully Returned'),
        ('CANCELLED', 'Cancelled'),
    ]

    # Who processed this transaction
    user = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, # If user is deleted, keep the transaction but set user to NULL
        null=True, 
        blank=True, 
        related_name="processed_sales_transactions" # How to get transactions from a User object
    )
    # Customer information
    customer_shop = models.ForeignKey(
        'Shop', 
        on_delete=models.SET_NULL, # If Shop is deleted, keep transaction, set shop to NULL
        null=True, 
        blank=True, # Not all sales might be to a registered shop
        related_name='shop_sales_transactions'
    )
    customer_name_manual = models.CharField(
        max_length=200, 
        blank=True, 
        null=True,
        help_text="Customer's name if not selecting a registered shop."
    )
    
    # Transaction details
    transaction_time = models.DateTimeField(default=timezone.now)
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPE_CHOICES, default='CASH')
    status = models.CharField(max_length=20, choices=SALE_STATUS_CHOICES, default='PENDING_ITEMS')
    
    # Delivery details (if applicable)
    needs_vehicle = models.BooleanField(default=False)
    assigned_vehicle = models.ForeignKey(
        'Vehicle', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, # Only if needs_vehicle is True
        related_name='assigned_sales_transactions'
    )
    
    # Overall financial summary for this entire transaction
    # These will be calculated by summing up the totals from SalesTransactionItem records.
    grand_total_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    grand_total_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    
    notes = models.TextField(blank=True, null=True, help_text="General notes for this entire transaction.")

    def __str__(self):
        customer_display = self.customer_shop.name if self.customer_shop else self.customer_name_manual or "Walk-in Customer"
        return f"Transaction #{self.pk} for {customer_display} on {self.transaction_time.strftime('%Y-%m-%d')}"

    def update_grand_totals(self):
        """
        Recalculates grand totals based on all its items by iterating 
        and summing the item's calculated final revenue and cost properties.
        """
        items_queryset = self.items.all()  # Get all related SalesTransactionItem instances
        
        new_grand_total_revenue = Decimal('0.00')
        new_grand_total_cost = Decimal('0.00')

        for item in items_queryset:
            new_grand_total_revenue += item.total_item_final_revenue  # Use the @property
            new_grand_total_cost += item.total_item_final_cost      # Use the @property
        
        changed = False
        if self.grand_total_revenue != new_grand_total_revenue:
            self.grand_total_revenue = new_grand_total_revenue
            changed = True
        if self.grand_total_cost != new_grand_total_cost:
            self.grand_total_cost = new_grand_total_cost
            changed = True
        
        if changed:
            self.save(update_fields=['grand_total_revenue', 'grand_total_cost'])

    @property
    def calculated_grand_profit(self):
        return self.grand_total_revenue - self.grand_total_cost

    class Meta:
        ordering = ['-transaction_time']
        verbose_name = "Sales Transaction"
        verbose_name_plural = "Sales Transactions"


class SalesTransactionItem(models.Model):
    """
    Represents one line item (a specific product batch sold) within a SalesTransaction.
    """
    transaction = models.ForeignKey(
        SalesTransaction, 
        on_delete=models.CASCADE, # If the transaction header is deleted, its items are also deleted
        related_name="items" # How to get items from a SalesTransaction object (e.g., my_transaction.items.all())
    )
    # Which specific product batch was sold for this line item
    product_detail_snapshot = models.ForeignKey(
        'ProductDetail', 
        on_delete=models.PROTECT, # Prevent deleting ProductDetail if it's part of a sold item.
                                  # You might need a way to "deactivate" product details instead.
        help_text="The specific product batch (product name, expiry, etc.) sold."
    )
    
    # Quantity of THIS product batch sold, in your "master_unit.item" decimal format (e.g., 1.1)
    quantity_sold_decimal = models.DecimalField(
        max_digits=10, decimal_places=1,
        validators=[MinValueValidator(Decimal('0.1'))] 
    )
    
    # Prices PER INDIVIDUAL ITEM for this line item, snapshotted at the time of sale
    selling_price_per_item = models.DecimalField(max_digits=10, decimal_places=2)
    cost_price_per_item_at_sale = models.DecimalField(max_digits=10, decimal_places=2)

    # Snapshot details from ProductDetail for this line item (important for historical accuracy)
    expiry_date_at_sale = models.DateField()
    items_per_master_unit_at_sale = models.PositiveIntegerField() # e.g., 6 items per carton

    # Calculated totals for THIS line item (based on dispatched quantity)
    total_item_dispatched_revenue = models.DecimalField(max_digits=12, decimal_places=2)
    total_item_dispatched_cost = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Quantity returned FOR THIS LINE ITEM (in your "master_unit.item" decimal format)
    returned_quantity_decimal = models.DecimalField(
        max_digits=10, decimal_places=1,
        default=Decimal('0.0'),
        validators=[MinValueValidator(Decimal('0.0'))]
    )

    def _get_individual_items_from_decimal(self, decimal_qty: Decimal, items_per_mu: int) -> int:
        """Helper to convert X.Y decimal (e.g., 1.1 cartons) to total individual items (e.g., 7 items)."""
        if decimal_qty is None or items_per_mu is None or items_per_mu <= 0:
            return 0
        full_units = int(decimal_qty)
        # Assumes .1 in decimal_qty means 1 item, .2 means 2 items, etc.
        decimal_part_items = int(round((decimal_qty % 1) * Decimal('10.0')))
        return (full_units * items_per_mu) + decimal_part_items

    @property
    def dispatched_individual_items_count(self) -> int:
        """Total individual items initially dispatched for this line item."""
        return self._get_individual_items_from_decimal(self.quantity_sold_decimal, self.items_per_master_unit_at_sale)

    @property
    def returned_individual_items_count(self) -> int:
        """Total individual items returned for this line item."""
        return self._get_individual_items_from_decimal(self.returned_quantity_decimal, self.items_per_master_unit_at_sale)

    @property
    def actual_sold_individual_items_count(self) -> int:
        """Net individual items actually sold after returns for this line item."""
        return self.dispatched_individual_items_count - self.returned_individual_items_count

    @property
    def total_item_final_revenue(self) -> Decimal:
        """Final revenue for this line item after considering returns."""
        return Decimal(self.actual_sold_individual_items_count) * self.selling_price_per_item

    @property
    def total_item_final_cost(self) -> Decimal:
        """Final cost for this line item after considering returns."""
        return Decimal(self.actual_sold_individual_items_count) * self.cost_price_per_item_at_sale
        
    @property
    def line_item_profit(self) -> Decimal:
        """Profit for this line item after considering returns."""
        return self.total_item_final_revenue - self.total_item_final_cost

    def save(self, *args, **kwargs):
        # Populate snapshot fields if it's a new item and product_detail_snapshot is set
        if not self.pk and self.product_detail_snapshot:
            self.expiry_date_at_sale = self.product_detail_snapshot.expirey_date
            self.items_per_master_unit_at_sale = self.product_detail_snapshot.items_per_master_unit
            # cost_price_per_item_at_sale should be set from ProductDetail when item is added to sale (in view/form)
            # selling_price_per_item should be set from user input when item is added to sale (in view/form)

        # Calculate totals based on dispatched quantity for this line item
        dispatched_items_count = self._get_individual_items_from_decimal(
            self.quantity_sold_decimal or Decimal('0.0'),
            self.items_per_master_unit_at_sale or (self.product_detail_snapshot.items_per_master_unit if self.product_detail_snapshot else 0)
        )
        self.total_item_dispatched_revenue = dispatched_items_count * (self.selling_price_per_item or Decimal('0.0'))
        self.total_item_dispatched_cost = dispatched_items_count * (self.cost_price_per_item_at_sale or Decimal('0.0'))
        
        is_new_item_or_quantity_changed = self.pk is None or self._state.adding # or check if relevant fields changed
        
        super().save(*args, **kwargs)

        # After saving this item, update the parent SalesTransaction's totals
        if self.transaction and is_new_item_or_quantity_changed: # Only update if it's new or relevant fields changed
            self.transaction.update_grand_totals()

    def __str__(self):
        return f"{self.quantity_sold_decimal} of {self.product_detail_snapshot.product_base.name} in Transaction #{self.transaction_id}"

    class Meta:
        # You might want to prevent adding the exact same product_detail_snapshot 
        # twice in the same transaction, preferring to update the quantity on the existing line.
        # unique_together = [['transaction', 'product_detail_snapshot']]
        ordering = ['pk'] # Usually items are ordered by addition
        verbose_name = "Sales Transaction Item"
        verbose_name_plural = "Sales Transaction Items"



class Sale(models.Model): # Renamed from SaleRecord if you prefer
    PAYMENT_TYPE_CHOICES = [
        ('CASH', 'Cash on Hand'),
        ('ONLINE', 'Online Transfer'),
        ('CREDIT', 'Credit/Account'),
    ]
    SALE_STATUS_CHOICES = [
        ('PENDING_DELIVERY', 'Pending Delivery'),
        ('COMPLETED', 'Completed'),
        ('PARTIALLY_RETURNED', 'Partially Returned'), # If some items came back
        ('FULLY_RETURNED', 'Fully Returned'), # If all items came back
        ('CANCELLED', 'Cancelled'),
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="recorded_sales")
    product_detail_snapshot = models.ForeignKey(
        'ProductDetail',
        on_delete=models.PROTECT,
        related_name='sales_records',
        help_text="The specific product detail (batch) that was sold."
    )
    # Changed from name_of_customer to a ForeignKey to Shop
    customer_shop = models.ForeignKey(
        'Shop',
        on_delete=models.SET_NULL, # If shop is deleted, sale record remains, shop becomes NULL
        null=True,
        blank=True, # Sale might not always be to a registered shop
        related_name='purchases',
        help_text="The shop that made the purchase, if applicable."
    )
    # Fallback if not a registered shop, or for individual customers
    customer_name_manual = models.CharField(max_length=200, blank=True, null=True, help_text="Customer name if not a registered shop.")


    quantity_sold_decimal = models.DecimalField( # e.g., 1.1 for 1 carton + 1 item
        max_digits=10, decimal_places=1, default=0.0,
        validators=[MinValueValidator(Decimal('0.1'))],
        help_text="Quantity dispatched in 'master_unit.item' format."
    )
    selling_price_per_item = models.DecimalField( # Price per individual item
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    
    # Snapshot fields (populated in save or view)
    expiry_date_at_sale = models.DateField()
    stock_before_sale = models.DecimalField(max_digits=10, decimal_places=1)
    items_per_master_unit_at_sale = models.PositiveIntegerField()
    cost_price_per_item_at_sale = models.DecimalField(max_digits=10, decimal_places=2)

    # New fields for this phase
    needs_vehicle = models.BooleanField(default=False)
    assigned_vehicle = models.ForeignKey(
        'Vehicle',
        on_delete=models.SET_NULL,
        null=True,
        blank=True, # Vehicle only assigned if needs_vehicle is True
        related_name='deliveries'
    )
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPE_CHOICES, default='CASH')
    status = models.CharField(max_length=20, choices=SALE_STATUS_CHOICES, default='COMPLETED') # Default might change based on needs_vehicle

    returned_stock_decimal = models.DecimalField( # e.g., 0.2 for 2 items returned
        max_digits=10, decimal_places=1,
        null=True, blank=True,
        validators=[MinValueValidator(Decimal('0.0'))], # Can be 0
        help_text="Quantity returned by customer in 'master_unit.item' format."
    )

    # Calculated fields
    total_revenue_dispatch = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00')) # Based on quantity_sold_decimal
    total_cost_dispatch = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))    # Based on quantity_sold_decimal
    # Profit will be a property that considers returns

    sale_time = models.DateTimeField(default=timezone.now)


    def _get_total_individual_items_from_decimal(self, decimal_quantity: Decimal, items_per_mu: int) -> int:
        """Helper to convert X.Y decimal to total individual items."""
        if decimal_quantity is None or items_per_mu is None or items_per_mu <= 0:
            return 0
        full_units = int(decimal_quantity)
        # Assumes .1 = 1 item, .2 = 2 items, etc. (fractional part is base-10 for items)
        decimal_part_items = int(round((decimal_quantity % 1) * Decimal('10.0')))
        return (full_units * items_per_mu) + decimal_part_items

    @property
    def dispatched_individual_items_count(self):
        return self._get_total_individual_items_from_decimal(self.quantity_sold_decimal, self.items_per_master_unit_at_sale)

    @property
    def returned_individual_items_count(self):
        if self.returned_stock_decimal is None:
            return 0
        return self._get_total_individual_items_from_decimal(self.returned_stock_decimal, self.items_per_master_unit_at_sale)

    @property
    def actual_sold_individual_items_count(self):
        return self.dispatched_individual_items_count - self.returned_individual_items_count
        
    @property
    def final_total_revenue(self):
        return Decimal(self.actual_sold_individual_items_count) * self.selling_price_per_item

    @property
    def final_total_cost(self):
        return Decimal(self.actual_sold_individual_items_count) * self.cost_price_per_item_at_sale

    @property
    def final_profit(self):
        return self.final_total_revenue - self.final_total_cost

    def save(self, *args, **kwargs):
        # Populate snapshot fields from product_detail_snapshot if it's a new sale
        if not self.pk and self.product_detail_snapshot:
            self.expiry_date_at_sale = self.product_detail_snapshot.expirey_date
            # stock_before_sale should be set in the view just before decrementing stock
            self.items_per_master_unit_at_sale = self.product_detail_snapshot.items_per_master_unit
            self.cost_price_per_item_at_sale = self.product_detail_snapshot.price_per_item

        # Calculate totals based on dispatched quantity (initial sale)
        dispatched_items_count = self._get_total_individual_items_from_decimal(
            self.quantity_sold_decimal or Decimal('0.0'), 
            self.items_per_master_unit_at_sale or self.product_detail_snapshot.items_per_master_unit # Fallback
        )
        self.total_revenue_dispatch = dispatched_items_count * (self.selling_price_per_item or Decimal('0.0'))
        self.total_cost_dispatch = dispatched_items_count * (self.cost_price_per_item_at_sale or Decimal('0.0'))
        
        super().save(*args, **kwargs)

    def __str__(self):
        shop_name = self.customer_shop.name if self.customer_shop else self.customer_name_manual or "Walk-in Customer"
        return f"Sale of {self.quantity_sold_decimal} of {self.product_detail_snapshot.product_base.name} to {shop_name} on {self.sale_time.strftime('%Y-%m-%d')}"

    class Meta:
        ordering = ['-sale_time']



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

    @property
    def current_balance(self):
        """
        Calculates the current outstanding balance for the shop by summing
        all its related financial transactions from the 'accounts' app.
        Balance = Total Debits - Total Credits
        """
        # self.financial_transactions comes from the related_name in ShopFinancialTransaction model
        totals = self.financial_transactions.aggregate(
            total_debit=Sum('debit_amount'),
            total_credit=Sum('credit_amount')
        )
        
        total_debit = totals.get('total_debit') or Decimal('0.00')
        total_credit = totals.get('total_credit') or Decimal('0.00')
        
        return total_debit - total_credit

    class Meta:
        ordering = ['name'] # Order by name alphabetically
        verbose_name = "Shop"
        verbose_name_plural = "Shops"