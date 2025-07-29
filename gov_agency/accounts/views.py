from django.shortcuts import render,get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Sum,When, Case,Value, IntegerField,Q, F, ExpressionWrapper, DecimalField
from decimal import Decimal
from django.http import JsonResponse,HttpResponseBadRequest
from django.contrib import messages
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from urllib.parse import quote # For safely encoding names in URLs
from .models import ShopFinancialTransaction,CustomAccount,CustomAccountTransaction
from .forms import EditFinancialTransactionForm,CustomAccountForm,CustomTransactionEntryForm
from stock.models import SalesTransaction
from expense.models import Expense
from .models import ShopFinancialTransaction, DailySummary # <-- Import the new model
from .forms import DateFilterForm 

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
    associated_shops_query  = Shop.objects.filter(user=request.user,
        shop_sales_transactions__assigned_vehicle=vehicle
    ).distinct().order_by('name')
    associated_shops = associated_shops_query.annotate(
        # Calculate the current balance for each shop
    balance=Sum('financial_transactions__debit_amount') - Sum('financial_transactions__credit_amount')
    ).annotate(
        # Create a temporary 'sort_priority' field
        sort_priority=Case(
            When(balance=Decimal('0.00'), then=Value(1)), # Zero balance gets priority 1
            default=Value(0),                                     # Non-zero balance gets priority 0
            output_field=IntegerField(),
        )
    ).order_by('sort_priority', 'name') # Sort by priority, then by name

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
    associated_shops_query = Shop.objects.filter(user = request.user,
    shop_sales_transactions__assigned_vehicle__isnull=True
    ).distinct().order_by('name')

    associated_shops = associated_shops_query.annotate(
        # Use 'balance' here as well for consistency
        balance=Sum('financial_transactions__debit_amount') - Sum('financial_transactions__credit_amount')
    ).annotate(
        sort_priority=Case(
            When(balance=Decimal('0.00'), then=Value(1)),
            default=Value(0),
            output_field=IntegerField(),
        )
    ).order_by('sort_priority', 'name')
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


@login_required
def manual_customer_ledger_view(request, customer_name):
    # This view is very similar to shop_ledger_view, but filters on the name string.
    # Note: This approach assumes customer names are unique enough for this context.
    
    # We don't have a single object to fetch, the 'customer_name' string is our identifier.
    
    if request.method == 'POST':
        # Handle the "Receive Cash" form submission for this manual customer
        form = ReceiveCashForm(request.POST)
        if form.is_valid():
            try:
                new_receipt = form.save(commit=False)
                new_receipt.shop = None # No registered shop
                new_receipt.customer_name_snapshot = customer_name # Set the manual customer name
                new_receipt.user = request.user
                new_receipt.transaction_type = 'CASH_RECEIPT'
                new_receipt.debit_amount = Decimal('0.00')
                new_receipt.save()
                messages.success(request, f"Cash receipt recorded for {customer_name}.")
                return redirect('accounts:manual_customer_ledger', customer_name=customer_name)
            except Exception as e:
                messages.error(request, f"Error recording cash receipt: {str(e)}")
        else:
            messages.error(request, "Please correct the errors in the cash receipt form.")
    
    # Create an empty form instance for the "Receive Cash" modal for GET requests
    receive_cash_form = ReceiveCashForm()

    # Fetch all financial transactions for this specific manual customer name
    ledger_entries = ShopFinancialTransaction.objects.filter(
        customer_name_snapshot=customer_name,
        shop__isnull=True, # Ensure we only get manual entries
        user=request.user # Scope to the logged-in user's transactions
    ).order_by('-transaction_date', '-pk')

    # Calculate summary stats for this manual customer
    totals = ledger_entries.aggregate(
        total_debit=Sum('debit_amount'),
        total_credit=Sum('credit_amount')
    )
    total_debit = totals.get('total_debit') or Decimal('0.00')
    total_credit = totals.get('total_credit') or Decimal('0.00')
    current_balance = total_debit - total_credit

    context = {
        'customer_name': customer_name,
        'ledger_entries': ledger_entries,
        'receive_cash_form': receive_cash_form,
        'edit_transaction_form': EditFinancialTransactionForm(), # For the edit modal
        'form_had_errors_for_modal': request.method == 'POST', # A simple way to signal error state
        'total_debit': total_debit,
        'total_credit': total_credit,
        'current_balance': current_balance,
    }
    return render(request, 'accounts/manual_customer_ledger.html', context)




# We also need views to handle the POSTs for Edit and Delete
@login_required
def edit_financial_transaction_view(request, transaction_pk):
    # This view is for handling the POST from the edit modal.
    # We add a 'next' query parameter to know where to redirect back to.
    next_url = request.GET.get('next', reverse('accounts:transactions_hub')) # Default fallback
    
    # Security check: Ensure the transaction's shop (if any) or user matches.
    # This query ensures a user can only edit their own financial records.
    transaction_instance = get_object_or_404(ShopFinancialTransaction, pk=transaction_pk, user=request.user)
    
    if request.method == 'POST':
        form = EditFinancialTransactionForm(request.POST, instance=transaction_instance)
        if form.is_valid():
            form.save()
            messages.success(request, "Financial transaction updated successfully.")
        else:
            # Create a detailed error message to show the user
            error_string = ". ".join([f"{field}: {', '.join(errors)}" for field, errors in form.errors.items()])
            messages.error(request, f"Failed to update transaction: {error_string}")
        
        return redirect(next_url) # Redirect back to the page the user came from
    
    # GET requests to this URL are not intended for direct viewing
    return redirect(next_url)

@login_required
def delete_financial_transaction_view(request, transaction_pk):
    # This view also uses a 'next' query parameter for redirection.
    next_url = request.GET.get('next', reverse('accounts:transactions_hub'))
    
    transaction_instance = get_object_or_404(ShopFinancialTransaction, pk=transaction_pk, user=request.user)
    
    if request.method == 'POST':
        # Business logic: Prevent deleting credit entries linked to a sale.
        if transaction_instance.source_sale:
            messages.error(request, "Cannot delete a financial entry linked to a sale. Please process a return or create a credit note instead.")
            return redirect(next_url)
        
        transaction_instance.delete()
        messages.success(request, "Financial transaction deleted successfully.")
    
    return redirect(next_url)

# And a simple AJAX view to get data for the edit modal
@login_required
def ajax_get_financial_transaction_data(request, transaction_pk):
    try:
        tx = get_object_or_404(ShopFinancialTransaction, pk=transaction_pk, user=request.user)
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
    











@login_required
def custom_account_hub_view(request):
    """The page that lists all custom account 'cards' and allows creating new ones."""
    if request.method == 'POST':
        form = CustomAccountForm(request.POST)
        if form.is_valid():
            account = form.save(commit=False)
            account.user = request.user
            account.save()
            messages.success(request, f"New account '{account.name}' created.")
            return redirect('accounts:custom_account_hub')
        else:
            messages.error(request, "Error creating account.")
    
    accounts = CustomAccount.objects.filter(user=request.user)
    add_account_form = CustomAccountForm()
    context = {
        'accounts': accounts,
        'add_form': add_account_form,
        'form_had_errors': 'form' in locals() and form.errors,
    }
    return render(request, 'accounts/custom_account_hub.html', context)

@login_required
def custom_account_ledger_view(request, account_pk):
    """The detailed ledger page for one custom account."""
    account = get_object_or_404(CustomAccount, pk=account_pk, user=request.user)
    
    if request.method == 'POST':
        form = CustomTransactionEntryForm(request.POST)
        if form.is_valid():
            entry = form.save(commit=False)
            entry.account = account # Link to the correct CustomAccount
            entry.user = request.user
            entry.save()
            messages.success(request, "New ledger entry added.")
            return redirect('accounts:custom_account_ledger', account_pk=account.pk)
        else:
            messages.error(request, "Error adding entry. Please check the form.")
    
    add_entry_form = CustomTransactionEntryForm()
    ledger_entries = account.transactions.all().order_by('-transaction_date')
    
    context = {
        'account': account,
        'ledger_entries': ledger_entries,
        'add_form': add_entry_form,
        'form_had_errors': 'form' in locals() and form.errors,
        'edit_form': CustomTransactionEntryForm(), # For the edit modal structure
    }
    return render(request, 'accounts/custom_account_ledger.html', context)


@login_required
def update_custom_transaction_view(request, pk):
    """Handles the POST submission from the 'Edit Custom Transaction' modal."""
    # Get the 'next' URL for redirection, defaulting to the hub if not provided
    next_url = request.GET.get('next', reverse('accounts:custom_account_hub'))
    
    # Security Check: Ensure the transaction belongs to the currently logged-in user.
    transaction_instance = get_object_or_404(CustomAccountTransaction, pk=pk, user=request.user)
    
    if request.method == 'POST':
        # Initialize the form with the submitted data and the specific transaction instance
        form = CustomTransactionEntryForm(request.POST, instance=transaction_instance)
        if form.is_valid():
            form.save() # This updates the transaction instance
            messages.success(request, "Custom transaction updated successfully.")
        else:
            # Create a detailed error message to show the user upon redirection
            error_string = ". ".join([f"{field}: {', '.join(errors)}" for field, errors in form.errors.items()])
            messages.error(request, f"Failed to update transaction: {error_string}")
        
        return redirect(next_url) # Redirect back to the page the user came from
    
    # GET requests to this URL are not intended for direct viewing
    return redirect(next_url)


@login_required
def delete_custom_transaction_view(request, pk):
    """Handles the POST submission from the 'Delete Custom Transaction' confirmation modal."""
    next_url = request.GET.get('next', reverse('accounts:custom_account_hub'))
    
    # Security Check: Fetch the transaction ensuring it belongs to the user
    transaction_instance = get_object_or_404(CustomAccountTransaction, pk=pk, user=request.user)
    
    if request.method == 'POST':
        entity_name = transaction_instance.account.name
        try:
            transaction_instance.delete()
            messages.success(request, f"Transaction for '{entity_name}' deleted successfully.")
        except Exception as e:
            messages.error(request, f"An error occurred while deleting the transaction: {str(e)}")
        
    return redirect(next_url) # Redirect back to the page the user came from


@login_required
def ajax_get_custom_transaction_data(request, pk):
    """Serves data for a specific custom transaction to populate the update modal via JS."""
    try:
        # Security Check: User can only get data for transactions they created.
        tx = get_object_or_404(CustomAccountTransaction, pk=pk, user=request.user)
        
        data = {
            'pk': tx.pk,
            'entity_name': tx.account.name,
            'transaction_date': tx.transaction_date.strftime('%Y-%m-%dT%H:%M'), # Format for datetime-local input
            'debit_amount': str(tx.debit_amount),
            'credit_amount': str(tx.credit_amount),
            'notes': tx.notes or "",
        }
        return JsonResponse({'success': True, 'data': data})
    except CustomAccount.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Transaction not found or not authorized.'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'An unexpected server error occurred: {str(e)}'}, status=500)
    



@login_required
def update_custom_account_card_view(request, account_pk):
    """Handles the POST request to update a custom account's details."""
    # Ensure the user can only edit their own accounts
    account = get_object_or_404(CustomAccount, pk=account_pk, user=request.user)
    
    if request.method == 'POST':
        form = CustomAccountForm(request.POST, instance=account)
        if form.is_valid():
            form.save()
            messages.success(request, f"Account '{account.name}' updated successfully.")
        else:
            messages.error(request, "Error updating account. Please check the details.")
            
    # Always redirect back to the hub page
    return redirect('accounts:custom_account_hub')

@login_required
def delete_custom_account_card_view(request, account_pk):
    """Handles the POST request to delete a custom account."""
    # Ensure the user can only delete their own accounts
    account = get_object_or_404(CustomAccount, pk=account_pk, user=request.user)
    
    if request.method == 'POST':
        account_name = account.name
        try:
            account.delete()
            messages.success(request, f"Account '{account_name}' and all its transactions have been deleted.")
        except Exception as e:
            messages.error(request, f"An error occurred while deleting the account: {str(e)}")

    # Always redirect back to the hub page
    return redirect('accounts:custom_account_hub')







# daily summary views ...
@login_required
def daily_summary_list_view(request):
    """
    Displays a list of daily financial summaries and allows for generating
    a new summary for today.
    """
    summaries = DailySummary.objects.filter(user=request.user)
    
    # Handle date filtering
    filter_form = DateFilterForm(request.GET)
    if filter_form.is_valid():
        date_filter = filter_form.cleaned_data.get('date_filter')
        if date_filter:
            summaries = summaries.filter(summary_date=date_filter)

    context = {
        'summaries': summaries,
        'filter_form': filter_form,
    }
    return render(request, 'accounts/daily_summary_list.html', context)


@login_required
def generate_today_summary_view(request):
    if request.method == 'POST':
        today = timezone.localdate()
        # --- GATHER DATA (This part is unchanged) ---
        sales_today = SalesTransaction.objects.filter(user=request.user, transaction_time__date=today)
        expenses_today = Expense.objects.filter(user=request.user, expense_date__date=today)
        shop_financial_entries_today = ShopFinancialTransaction.objects.filter(user=request.user, transaction_date__date=today)
        custom_account_entries_today = CustomAccountTransaction.objects.filter(user=request.user, transaction_date__date=today)

        # --- CALCULATE REPORTING & CASH FLOW COMPONENTS ---
        total_revenue = sales_today.aggregate(total=Sum('grand_total_revenue'))['total'] or Decimal('0.00')
        total_profit = sum(sale.calculated_grand_profit for sale in sales_today) or Decimal('0.00')
        total_expense = expenses_today.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        online_sales_today = sales_today.filter(payment_type='ONLINE').aggregate(total=Sum('grand_total_revenue'))['total'] or Decimal('0.00')
        
        # --- NEW CALCULATION: Total Debits for Today ---
        # Get all debit amounts from both ledger models for today
        debit_from_shops = shop_financial_entries_today.aggregate(total=Sum('debit_amount'))['total'] or Decimal('0.00')
        debit_from_custom = custom_account_entries_today.aggregate(total=Sum('debit_amount'))['total'] or Decimal('0.00')
        
        total_debit_today = debit_from_shops + debit_from_custom
        # Cash received calculation is unchanged
        cash_from_shops = sum(entry.credit_amount for entry in shop_financial_entries_today if entry.transaction_type == 'CASH_RECEIPT')
        cash_from_custom_accounts = custom_account_entries_today.aggregate(total=Sum('credit_amount'))['total'] or Decimal('0.00')
        
        total_cash_received = cash_from_shops + cash_from_custom_accounts
        
        # --- FINAL NET CALCULATIONS (These formulas are already correct) ---
        cash_from_cash_sales = sales_today.filter(payment_type='CASH').aggregate(total=Sum('grand_total_revenue'))['total'] or Decimal('0.00')
        net_physical_cash = (cash_from_cash_sales + total_cash_received ) - total_expense
        
        cash_from_direct_sales = sales_today.filter(payment_type__in=['CASH', 'ONLINE']).aggregate(total=Sum('grand_total_revenue'))['total'] or Decimal('0.00')
        net_total_settlement = (cash_from_direct_sales + total_cash_received) - total_expense
        
        # --- SAVE THE SUMMARY ---
        summary, created = DailySummary.objects.update_or_create(
            user=request.user,
            summary_date=today,
            defaults={
                'total_revenue': total_revenue,
                'total_profit': total_profit,
                'total_debit_today': total_debit_today, # <-- Save the new value
                'online_sales_today': online_sales_today,
                'total_expense': total_expense,
                'total_cash_received': total_cash_received,
                'net_physical_cash': net_physical_cash,
                'net_total_settlement': net_total_settlement,
            }
        )
        
        if created:
            messages.success(request, f"Successfully generated financial summary for {today.strftime('%B %d, %Y')}.")
        else:
            messages.info(request, f"Successfully updated financial summary for {today.strftime('%B %d, %Y')}.")

    return redirect('accounts:daily_summary_list')

@login_required
def delete_daily_summary_view(request, summary_pk):
    """
    Deletes a specific daily summary record.
    """
    summary = get_object_or_404(DailySummary, pk=summary_pk, user=request.user)
    if request.method == 'POST':
        summary_date_str = summary.summary_date.strftime('%B %d, %Y')
        summary.delete()
        messages.error(request, f"Deleted the financial summary for {summary_date_str}.")
    return redirect('accounts:daily_summary_list')