from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
from django.core.validators import MinValueValidator

class Claim(models.Model):
    """
    Represents a claim for expired or damaged stock, which is removed from inventory.
    """
    CLAIM_STATUS_CHOICES = [
        ('PENDING', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]

    # User who filed the claim
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="claims_filed"
    )
    
    # The specific product batch being claimed
    product_detail = models.ForeignKey(
        'stock.ProductDetail', # String reference to model in 'stock' app
        on_delete=models.PROTECT, # Don't delete a ProductDetail if it has claims
        related_name="claims"
    )
    
    # Quantity claimed, in the same 'MasterUnits.IndividualItems' format
    quantity_claimed_decimal = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Quantity claimed in 'MasterUnits.IndividualItems' format (e.g., 1.05)."
    )
    
    # Optional: Where the claim originated from (a registered shop)
    claimed_from_shop = models.ForeignKey(
        'stock.Shop', # String reference
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="shop_claims"
    )
    
    # Optional: Which vehicle was used to retrieve the claimed items
    retrieval_vehicle = models.ForeignKey(
        'stock.Vehicle', # String reference
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="claims_retrieved"
    )
    
    reason = models.TextField(help_text="Reason for the claim (e.g., Expired, Damaged).")
    status = models.CharField(max_length=20, choices=CLAIM_STATUS_CHOICES, default='APPROVED')
    claim_date = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Claim for {self.quantity_claimed_decimal} of {self.product_detail.product_base.name} on {self.claim_date.strftime('%Y-%m-%d')}"

    class Meta:
        ordering = ['-claim_date']
        verbose_name = "Stock Claim"
        verbose_name_plural = "Stock Claims"