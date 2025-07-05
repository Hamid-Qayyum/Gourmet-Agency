from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
from django.core.validators import MinValueValidator

class Expense(models.Model):
    """
    Represents a single expense record.
    """
    user = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, # Keep record if user is deleted
        null=True, 
        blank=True,
        related_name="expenses"
    )
    
    title = models.CharField(
        max_length=200,
        help_text="A short title for the expense, e.g., 'Office Rent', 'Fuel for Vehicle ABC-123'."
    )
    
    amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="The total amount of the expense."
    )
    
    expense_date = models.DateTimeField(
        default=timezone.now,
        help_text="The date and time the expense was incurred or recorded."
    )
    
    description = models.TextField(
        blank=True, 
        null=True,
        help_text="Optional: More details about the expense."
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} - Rs {self.amount} on {self.expense_date.strftime('%Y-%m-%d')}"

    class Meta:
        ordering = ['-expense_date'] # Show most recent expenses first
        verbose_name = "Expense"
        verbose_name_plural = "Expenses"