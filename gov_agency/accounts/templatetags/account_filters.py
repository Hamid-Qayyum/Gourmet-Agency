from django import template
from decimal import Decimal
from django.db.models import Sum
register = template.Library()

@register.filter
def sum_debit(queryset):
    return queryset.aggregate(total=Sum('debit_amount'))['total'] or Decimal('0.00')

@register.filter
def sum_credit(queryset):
    return queryset.aggregate(total=Sum('credit_amount'))['total'] or Decimal('0.00')