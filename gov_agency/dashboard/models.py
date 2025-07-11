from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal


class Note(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notes")
    content = models.CharField(max_length=255)
    is_completed = models.BooleanField(default=False)
    position = models.PositiveIntegerField(default=0) # For ordering/sorting
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['position'] # Order by the position field

    def __str__(self):
        return self.content[:50]
    


class MonthlySalesTarget(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sales_targets")
    month = models.DateField(help_text="The first day of the month for this target.")
    target_quantity = models.DecimalField(
        max_digits=14, 
        decimal_places=2,
        default=Decimal('1000.00'),
        help_text="The sales target in master units (e.g., cartons) for this month."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # A user can only have one target for any given month.
        unique_together = ('user', 'month')
        ordering = ['-month']

    def __str__(self):
        return f"{self.user.username}'s target for {self.month.strftime('%B %Y')}: {self.target_quantity}"
