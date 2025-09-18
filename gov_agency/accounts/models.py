from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
from django.core.validators import MinValueValidator
from django.db.models import Sum  # <-- ADD THIS LINE

# Create your models here.


class ShopFinancialTransaction(models.Model):
    """
    Represents a single ledger entry (debit or credit) for a specific shop.
    """
    TRANSACTION_TYPE_CHOICES = [
        ('CREDIT_SALE', 'Credit from Sale'),
        ('CASH_RECEIPT', 'Cash Receipt'),
        ('ONLINE', 'Online Payment'),
        ('OPENING_BALANCE', 'Opening Balance'),     
    ]

    # Links to the Shop model in your 'stock' app
    shop = models.ForeignKey(
        'stock.Shop', # Use string 'app_name.ModelName' to prevent circular imports
        on_delete=models.CASCADE, 
        related_name="financial_transactions", # e.g., my_shop.financial_transactions.all()
        null=True,
        blank=True,
        help_text="The registered shop this transaction belongs to, if applicable."
    )

    customer_name_snapshot = models.CharField(
        max_length=200,
        blank=True, 
        null=True,
        help_text="Customer name for this transaction, if not a registered shop."
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
        help_text="Amount the shop now owes you (e.g., from a credit sale)."
    )
    
    # A credit decreases the amount the shop owes you.
    credit_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        help_text="Amount the shop paid you (e.g., cash received)."
    )
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    
    notes = models.CharField(max_length=255, blank=True, null=True)
    transaction_date = models.DateTimeField(default=timezone.now)

    def get_customer_display_name(self):
        """Returns the shop name or the manual customer name."""
        if self.shop:
            return self.shop.name
        return self.customer_name_snapshot or "Unknown Customer"

    def __str__(self):
        return f"{self.get_transaction_type_display()} for {self.get_customer_display_name()} on {self.transaction_date.strftime('%Y-%m-%d')} customer name is {self.customer_name_snapshot}"
    
    def save(self, *args, **kwargs):
        # Get the latest previous balance for this shop or manual customer
        if self.shop:
            last_transaction = ShopFinancialTransaction.objects.filter(
                shop=self.shop
            ).exclude(pk=self.pk).order_by("-transaction_date", "-pk").first()
        else:
            last_transaction = ShopFinancialTransaction.objects.filter(
                shop__isnull=True,
                customer_name_snapshot=self.customer_name_snapshot
            ).exclude(pk=self.pk).order_by("-transaction_date", "-pk").first()

        previous_balance = last_transaction.balance if last_transaction else Decimal("0.00")

        # Calculate new balance
        self.balance = previous_balance + self.debit_amount - self.credit_amount

        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-transaction_date', '-pk'] # Order by most recent first
        verbose_name = "Shop Financial Transaction"
        verbose_name_plural = "Shop Financial Transactions"





class CustomAccount(models.Model):
    """Represents an independent customer or entity for financial tracking."""
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="custom_accounts"
    )
    name = models.CharField(
        max_length=200,
        help_text="A unique name for this person or entity."
    )
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    @property
    def current_balance(self):
        """Calculates the current balance from its related transactions."""
        totals = self.transactions.aggregate(
            total_debit=Sum('debit_amount'),
            total_credit=Sum('credit_amount')
        )
        total_debit = totals.get('total_debit') or Decimal('0.00')
        total_credit = totals.get('total_credit') or Decimal('0.00')
        return total_debit - total_credit

    class Meta:
        ordering = ['name']
        # A user cannot have two custom accounts with the same name
        unique_together = [['user', 'name']]
        verbose_name = "Custom Account"
        verbose_name_plural = "Custom Accounts"


class CustomAccountTransaction(models.Model):
    """Represents a single debit or credit ledger entry for a CustomAccount."""
    account = models.ForeignKey(
        CustomAccount,
        on_delete=models.CASCADE,
        related_name="transactions" # e.g., my_account.transactions.all()
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True
    )
    debit_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        help_text="Amount owed TO you by this entity (increases their balance)."
    )
    credit_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        help_text="Amount paid BY you or received FROM this entity (decreases their balance)."
    )
    notes = models.CharField(max_length=255, blank=True, null=True)
    transaction_date = models.DateTimeField(default=timezone.now)
    store_in_daily_summery = models.BooleanField(default=False)

    def __str__(self):
        return f"Transaction for {self.account.name} on {self.transaction_date.strftime('%Y-%m-%d')}"

    class Meta:
        ordering = ['-transaction_date', '-pk']
        verbose_name = "Custom Account Transaction"
        verbose_name_plural = "Custom Account Transactions"




class DailySummary(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="daily_summaries")
    summary_date = models.DateField(help_text="The specific date this summary represents.")
    
    # --- REPORTING METRICS (Value of business done) ---
    total_revenue = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    total_profit = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    total_debit_today = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), help_text="Value of ONLY credit sales made today.")
    online_sales_today = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))

    # --- CASH FLOW METRICS (Actual cash movement) ---
    total_expense = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), help_text="Total cash paid out for expenses.")
    total_cash_received = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), help_text="Cash received from paying off past credit sales.")
    
    # 1. Physical cash in hand
    net_physical_cash = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), help_text="Net for physical cash only: (CASH Sales + Credit Payments) - Expenses.")
    online_received_cash = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    # 2. Total settlement including bank/online transactions
    net_total_settlement = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), help_text="Net including online: (CASH+ONLINE Sales + Credit Payments) - Expenses.")
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Summary for {self.summary_date.strftime('%Y-%m-%d')} by {self.user.username}"

    class Meta:
        ordering = ['-summary_date']
        verbose_name = "Daily Financial Summary"
        verbose_name_plural = "Daily Financial Summaries"
        unique_together = [['user', 'summary_date']]