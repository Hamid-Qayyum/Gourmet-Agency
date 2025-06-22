from django import template
from decimal import Decimal, InvalidOperation

register = template.Library()

@register.filter(name='subtract')
def subtract(value, arg):
    try:
        return Decimal(str(value)) - Decimal(str(arg)) # Convert to string first for robustness with Decimals
    except (TypeError, ValueError, InvalidOperation):
        try: # Fallback for simple numbers if Decimal conversion fails initially
            return value - arg
        except TypeError:
            return None # Or handle error appropriately, e.g., return value
    return None # Should not be reached if try works

@register.filter(name='multiply') # You had this in comments, good to have if needed
def multiply(value, arg):
    try:
        return Decimal(str(value)) * Decimal(str(arg))
    except (TypeError, ValueError, InvalidOperation):
        try:
            return value * arg
        except TypeError:
            return None
    return None