from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
from django.core.validators import MinValueValidator
# Create your models here.


class ShopFinancialTransaction(models.Model):
    """
    Represents a single ledger entry (debit or credit) for a specific shop.
    """
    TRANSACTION_TYPE_CHOICES = [
        ('CREDIT_SALE', 'Credit from Sale'),
        ('CASH_RECEIPT', 'Cash Receipt'),
        ('OPENING_BALANCE', 'Opening Balance'),
        ('MANUAL_ADJUSTMENT', 'Manual Adjustment'),
    ]

    # Links to the Shop model in your 'stock' app
    shop = models.ForeignKey(
        'stock.Shop', # Use string 'app_name.ModelName' to prevent circular imports
        on_delete=models.CASCADE, 
        related_name="financial_transactions" # e.g., my_shop.financial_transactions.all()
    )
    
    # User who recorded this financial transaction
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL, # Keep record if user is deleted
        null=True
    )
    
    # Optional: Link to the original SalesTransaction if this entry was auto-generated from a sale
    source_sale = models.OneToOneField(
        'stock.SalesTransaction', # Use string reference here too
        on_delete=models.SET_NULL, # If sale is deleted, this financial record might remain for auditing
        null=True, 
        blank=True,
        related_name="financial_ledger_entry" # e.g., my_sale.financial_ledger_entry
    )

    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES)
    
    # A debit increases the amount the shop owes you.
    debit_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        help_text="Amount the shop now owes you (e.g., from a credit sale). Increases balance."
    )
    
    # A credit decreases the amount the shop owes you.
    credit_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        help_text="Amount the shop paid you (e.g., cash received). Decreases balance."
    )
    
    notes = models.CharField(max_length=255, blank=True, null=True)
    transaction_date = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.get_transaction_type_display()} for {self.shop.name} on {self.transaction_date.strftime('%Y-%m-%d')}"

    class Meta:
        ordering = ['-transaction_date', '-pk'] # Order by most recent first
        verbose_name = "Shop Financial Transaction"
        verbose_name_plural = "Shop Financial Transactions"