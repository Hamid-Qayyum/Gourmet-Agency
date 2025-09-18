# utils.py (in your app)
from decimal import Decimal
from .models import ShopFinancialTransaction

def recalc_shop_balances(shop_id):
    qs = (
        ShopFinancialTransaction.objects
        .filter(shop_id=shop_id)
        .order_by("transaction_date", "pk")  # ascending oldest first
    )

    balance = Decimal("0.00")
    for tx in qs:
        debit = tx.debit_amount or Decimal("0.00")
        credit = tx.credit_amount or Decimal("0.00")
        balance = balance + debit - credit
        tx.balance = balance
        ShopFinancialTransaction.objects.filter(pk=tx.pk).update(balance=balance)
        print(f'[{tx.id}] debit={debit} credit={credit} new_balance={balance}')  # debug
    return balance