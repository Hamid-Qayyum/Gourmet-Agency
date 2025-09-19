from django import template

register = template.Library()

@register.filter
def has_lower_price(tx):
    return any(
        item.selling_price_per_item < item.product_detail_snapshot.selling_price_of_item
        for item in tx.items.all()
    )

@register.filter
def has_higher_price(tx):
    return any(
        item.selling_price_per_item > item.product_detail_snapshot.selling_price_of_item
        for item in tx.items.all()
    )