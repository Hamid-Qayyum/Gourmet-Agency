from django.shortcuts import render,get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Q, F, ExpressionWrapper, DecimalField
from decimal import Decimal
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth.models import User 




# Import models from both apps
from stock.models import Vehicle, Shop, SalesTransaction
from .models import ShopFinancialTransaction
from .forms import ReceiveCashForm, EditFinancialTransactionForm # Import the new forms


@login_required
def transactions_hub_view(request):
    # Fetch all active vehicles. Can be scoped to user if vehicles are user-specific.
    vehicles = Vehicle.objects.filter(is_active=True, user=request.user ).order_by('vehicle_number')
    
    context = {
        'vehicles': vehicles,
    }
    return render(request, 'accounts/transactions_hub.html', context)


@login_required
def vehicle_ledger_summary_view(request, vehicle_pk):
    vehicle = get_object_or_404(Vehicle, pk=vehicle_pk) # Can add user filter if needed

    # Find unique shops that had sales assigned to this vehicle
    associated_shops = Shop.objects.filter(user=request.user,
        shop_sales_transactions__assigned_vehicle=vehicle
    ).distinct().order_by('name')

    # Find unique manual customers that had sales assigned to this vehicle
    manual_customers_for_vehicle = SalesTransaction.objects.filter(
        user = request.user,
        assigned_vehicle=vehicle,
        customer_shop__isnull=True,
        customer_name_manual__isnull=False
    ).values_list('customer_name_manual', flat=True).distinct().order_by('customer_name_manual')
    
    # Get balances for these manual customers
    manual_customers_data = []
    if manual_customers_for_vehicle:
        ledger_entries = ShopFinancialTransaction.objects.filter(
            customer_name_snapshot__in=manual_customers_for_vehicle
        ).values('customer_name_snapshot').annotate(
            balance=Sum(F('debit_amount') - F('credit_amount'))
        )
        manual_customers_data = list(ledger_entries)

    context = {
        'grouping_object': vehicle,
        'grouping_type': 'Vehicle',
        'associated_shops': associated_shops,
        'manual_customers': manual_customers_data,
    }
    return render(request, 'accounts/ledger_summary.html', context)


@login_required
def store_ledger_summary_view(request):
    # Find unique shops that had sales with NO vehicle assigned
    associated_shops = Shop.objects.filter(user = request.user,
    shop_sales_transactions__assigned_vehicle__isnull=True
    ).distinct().order_by('name')

    # Find unique manual customers that had sales with NO vehicle
    manual_customers_for_store = SalesTransaction.objects.filter(
        user=request.user,
        assigned_vehicle__isnull=True,
        customer_shop__isnull=True,
        customer_name_manual__isnull=False
    ).values_list('customer_name_manual', flat=True).distinct().order_by('customer_name_manual')

    # Get balances for these manual customers
    manual_customers_data = []
    if manual_customers_for_store:
        ledger_entries = ShopFinancialTransaction.objects.filter(
            customer_name_snapshot__in=manual_customers_for_store
        ).values('customer_name_snapshot').annotate(
            balance=Sum(F('debit_amount') - F('credit_amount'))
        )
        manual_customers_data = list(ledger_entries)

    context = {
        'grouping_type': 'Store / Walk-in',
        'associated_shops': associated_shops,
        'manual_customers': manual_customers_data,
    }
    return render(request, 'accounts/ledger_summary.html', context)

@login_required
def shop_ledger_view(request, shop_pk):
    shop = get_object_or_404(Shop, pk=shop_pk) # Get the specific shop
    
    # This view will now handle POST requests from the 'Receive Cash' modal
    receive_cash_form = ReceiveCashForm() # For the modal
    form_had_errors = False

    if request.method == 'POST':
        # This assumes the POST is for receiving cash.
        # We can add a hidden 'action' input if other forms are added to this page later.
        form_to_process = ReceiveCashForm(request.POST)
        if form_to_process.is_valid():
            try:
                # The form only has credit_amount and notes. We need to set the rest.
                new_receipt = form_to_process.save(commit=False)
                new_receipt.shop = shop
                new_receipt.user = request.user
                new_receipt.transaction_type = 'CASH_RECEIPT'
                new_receipt.debit_amount = Decimal('0.00') # Cash received is a credit to the shop's account
                new_receipt.save()
                
                messages.success(request, f"Cash receipt of {new_receipt.credit_amount} recorded for {shop.name}.")
                return redirect('accounts:shop_ledger', shop_pk=shop.pk)
            except Exception as e:
                messages.error(request, f"Error recording cash receipt: {str(e)}")
                form_had_errors = True
                receive_cash_form = form_to_process # Pass back form with errors
        else:
            messages.error(request, "Please correct the errors in the cash receipt form.")
            form_had_errors = True
            receive_cash_form = form_to_process # Pass back form with errors


    # Fetch all financial transactions for this shop to display in the ledger table
    ledger_entries = ShopFinancialTransaction.objects.filter(shop=shop).order_by('-transaction_date', '-pk')

    context = {
        'shop': shop,
        'ledger_entries': ledger_entries,
        'receive_cash_form': receive_cash_form,
        'form_had_errors_for_modal': form_had_errors,
        # For the Edit modal, we'll pass an empty instance of the Edit form
        'edit_transaction_form': EditFinancialTransactionForm(),
    }
    return render(request, 'accounts/shop_ledger.html', context)

# We also need views to handle the POSTs for Edit and Delete
@login_required
def edit_financial_transaction_view(request, transaction_pk):
    transaction_instance = get_object_or_404(ShopFinancialTransaction, pk=transaction_pk, shop__user=request.user) # Security check
    shop_pk_for_redirect = transaction_instance.shop.pk

    if request.method == 'POST':
        form = EditFinancialTransactionForm(request.POST, instance=transaction_instance)
        if form.is_valid():
            form.save()
            messages.success(request, "Financial transaction updated successfully.")
        else:
            error_string = ". ".join([f"{field}: {', '.join(errors)}" for field, errors in form.errors.items()])
            messages.error(request, f"Failed to update transaction. {error_string}")
        return redirect('accounts:shop_ledger', shop_pk=shop_pk_for_redirect)
    return redirect('accounts:shop_ledger', shop_pk=shop_pk_for_redirect)


@login_required
def delete_financial_transaction_view(request, transaction_pk):
    transaction_instance = get_object_or_404(ShopFinancialTransaction, pk=transaction_pk, shop__user=request.user)
    shop_pk_for_redirect = transaction_instance.shop.pk

    if request.method == 'POST':
        # Business logic: Prevent deleting credit entries linked to a sale.
        if transaction_instance.source_sale:
            messages.error(request, "Cannot delete a financial entry linked to a sale. Please process a return for that sale instead.")
            return redirect('accounts:shop_ledger', shop_pk=shop_pk_for_redirect)
        
        transaction_instance.delete()
        messages.success(request, "Financial transaction deleted successfully.")
    return redirect('accounts:shop_ledger', shop_pk=shop_pk_for_redirect)

# And a simple AJAX view to get data for the edit modal
@login_required
def ajax_get_financial_transaction_data(request, transaction_pk):
    try:
        tx = get_object_or_404(ShopFinancialTransaction, pk=transaction_pk, shop__user=request.user)
        data = {
            'pk': tx.pk,
            'transaction_date': tx.transaction_date.strftime('%Y-%m-%dT%H:%M'), # Format for datetime-local input
            'debit_amount': str(tx.debit_amount),
            'credit_amount': str(tx.credit_amount),
            'notes': tx.notes or "",
            'is_from_sale': bool(tx.source_sale), # To tell JS if fields should be readonly
        }
        return JsonResponse({'success': True, 'data': data})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)