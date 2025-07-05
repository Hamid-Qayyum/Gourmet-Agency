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



@register.filter(name='sum')
def sum_list(queryset, attribute):
    """
    Sums a specific attribute of objects in a queryset.
    Usage: {{ my_queryset|sum:'attribute_name' }}
    """
    total = Decimal('0.00')
    if queryset:
        for item in queryset:
            total += getattr(item, attribute, Decimal('0.00'))
    return total