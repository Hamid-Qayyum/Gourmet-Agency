# claim/models.py

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
from django.core.validators import MinValueValidator

# The Claim "Header"
class Claim(models.Model):
    CLAIM_STATUS_CHOICES = [
        ('PENDING', 'Pending - Being Built'),
        ('AWAITING_PROCESSING', 'Awaiting Stock Adjustment'),
        ('COMPLETED', 'Completed'),
    ]
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="claims_filed")
    claimed_from_shop = models.ForeignKey('stock.Shop', on_delete=models.SET_NULL, null=True, blank=True, related_name="shop_claims")
    retrieval_vehicle = models.ForeignKey('stock.Vehicle', on_delete=models.SET_NULL, null=True, blank=True, related_name="claims_retrieved")
    reason = models.TextField(help_text="Reason for the claim (e.g., Expired, Damaged).")
    status = models.CharField(max_length=30, choices=CLAIM_STATUS_CHOICES, default='PENDING')
    claim_date = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Claim #{self.pk} from {self.claimed_from_shop or 'N/A'} on {self.claim_date.strftime('%Y-%m-%d')}"
    
    @property
    def value_of_items_given(self):
        """Calculates the total cost of items given out in exchange."""
        total_cost = Decimal('0.00')
        exchanged_items = self.items.filter(item_type='EXCHANGED')
        for item in exchanged_items:
            total_cost += item.total_cost
        return total_cost

    class Meta:
        ordering = ['-claim_date']

# The NEW "Claim Item" model
class ClaimItem(models.Model):
    ITEM_TYPE_CHOICES = [
        ('CLAIMED', 'Item Returned by Customer'), # Stock IN
        ('EXCHANGED', 'Item Given in Exchange'),   # Stock OUT
    ]
    claim = models.ForeignKey(Claim, on_delete=models.CASCADE, related_name="items")
    product_detail = models.ForeignKey('stock.ProductDetail', on_delete=models.PROTECT, related_name="claim_items")
    item_type = models.CharField(max_length=20, choices=ITEM_TYPE_CHOICES)
    quantity_decimal = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    # Snapshot the cost for financial tracking
    cost_price_at_claim = models.DecimalField(max_digits=10, decimal_places=2)

    @property
    def total_cost(self):
        """Calculates the total cost of this line item."""
        individual_items = self.product_detail._get_items_from_decimal(self.quantity_decimal)
        return (Decimal(individual_items) * self.cost_price_at_claim).quantize(Decimal('0.01'))

    def __str__(self):
        return f"{self.get_item_type_display()}: {self.quantity_decimal} of {self.product_detail.product_base.name}"