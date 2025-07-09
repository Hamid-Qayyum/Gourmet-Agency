from django.shortcuts import render,redirect, get_object_or_404
from .forms import RegisterForm, AddProductForm, ProductDetailForm,VehicleForm, ShopForm,ProcessReturnForm
from .forms import SalesTransactionItemReturnForm,AddItemToSaleForm,FinalizeSaleForm,SalesTransactionItemReturnFormSet # Import the formset
from .forms import UpdatePaymentTypeForm, AddStockForm
from django.contrib.auth import login, logout
from .utils import authenticate 
from django.contrib.auth.models import User 
from django.contrib.auth.decorators import login_required
from .models import AddProduct, ProductDetail,Sale, Vehicle, Shop, SalesTransaction, SalesTransactionItem
from accounts.models import ShopFinancialTransaction  # model from account app
from claim.models import Claim
from django.contrib import messages
from django.db.models  import Q,ProtectedError
from django.db import transaction # For atomic operations
from django.http import JsonResponse
from decimal import Decimal
from django.db.models import Sum,Count,F, ExpressionWrapper, fields, DecimalField
from django.utils import timezone
from datetime import timedelta, date
import json 
from django.db.models.functions import TruncMonth,TruncDay
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.urls import resolve
from django.http import HttpResponse
from openpyxl import Workbook
from openpyxl.utils import get_column_letter
from openpyxl.styles import Font
from expense.models import Expense
from django.db.models.functions import TruncDate,TruncMonth










# Create your views here.

# login view.........
def user_login(request):
    if request.method == 'POST':
        email = request.POST.get("email")
        password = request.POST.get("password")
        user = authenticate(email=email, password=password)
        if user is not None:
            login(request,user)
            return redirect('/dashboard')
    return render(request, 'registration/login.html')
            
# sign up view ............
def register_user(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request,user)
            return redirect('/dashboard')
    else:
        form = RegisterForm()    
    return render(request, 'registration/sign_up.html', {'form': form})

# dashboard view .......................................................................................................
@login_required
def dashboard(request):
    print("dashbord")
    messages.success(request, "hello dashboard")
    print("checking")
    return render(request,'stock/admin_dashboard.html')


# add product view .......................................................................................................
@login_required
def create_product(request):
    form_in_modal_has_errors = False  # Flag to tell template to open modal on page load if errors exist

    if request.method == 'POST':
        form = AddProductForm(request.POST)
        if form.is_valid():
            product_instance = form.save(commit=False)
            product_instance.user = request.user 
            try:
                product_instance.save() 
                messages.success(request, f"Product '{product_instance.name}' added successfully.")
                return redirect('stock:create_product') 
            except Exception as e:
                messages.error(request, f"Could not save product. An error occurred: {str(e)}")
                form_in_modal_has_errors = True
        else:
            messages.error(request, "Please correct the errors indicated in the form.")
            form_in_modal_has_errors = True
    else:
        form = AddProductForm()

    products_list = AddProduct.objects.filter(user=request.user).order_by('-created_at')
    context = {
        'form': form,
        'products': products_list,
        'form_in_modal_has_errors': form_in_modal_has_errors,
    }
    return render(request, 'stock/create_product.html', context)

@login_required
def confirm_delete_product_view(request, product_id):
    product = get_object_or_404(AddProduct, id=product_id, user=request.user) # Ensure user ownership
    context = {
        'product': product
    }
    return render(request, 'stock/confirm_delete_product.html', context)


@login_required
def delete_product_view(request, product_id):
    product_to_delete = get_object_or_404(AddProduct, id=product_id, user=request.user)
    if request.method == 'POST':
        product_name = product_to_delete.name
        product_to_delete.delete()
        messages.error(request, f"Product '{product_name}' deleted successfully.")
        return redirect('stock:create_product')
    return redirect('stock:confirm_delete_product', product_id=product_id)

# product detail views .........................................................................................................................
@login_required
def add_product_details(request):
    form_had_errors = False
    query = request.GET.get('q','')

    if request.method == 'POST':
        # This POST is for adding a new ProductDetail via the modal
        form = ProductDetailForm(request.POST, user = request.user)
        if form.is_valid():
            detail = form.save(commit=False)
            detail.user = request.user
            detail.save()
            messages.success(request, f"Details for '{detail.product_base.name}' added successfully!")
            redirect_url = redirect('stock:add_product_details').url
            if query:
                redirect_url += f'?q={query}'
            return redirect(redirect_url)
        else:
            messages.error(request, "Please correct the errors in the form.")
            form_had_errors = True
    else:
        form = ProductDetailForm(user = request.user)

    # Fetch product details for the current user   
    product_details_qs = ProductDetail.objects.filter(user=request.user).select_related('product_base').order_by('-created_at')

    if query:
        product_details_qs = product_details_qs.filter(
            Q(product_base__name__icontains=query)|
            Q(packing_type__icontains=query)
        )

    # Check if the current user has any base products to select from for the form
    user_has_base_products =  AddProduct.objects.filter(user=request.user).order_by('-created_at')
    if not user_has_base_products and request.method == 'GET' and not query:
        messages.warning(request, "You need to create a base product first (in 'Add Products') before adding details.")
    

    context = {
        'form': form,
        'product_details': product_details_qs,
        'form_had_errors': form_had_errors,
        'search_query': query,
        'user_has_base_products': user_has_base_products,
    }
    return render(request, 'stock/add_product_details.html', context)



@login_required
def product_detail_delete_selected_view(request):
    if request.method == 'POST':
        selected_ids = request.POST.getlist('selected_details_ids')
        products_to_delete = ProductDetail.objects.filter(id__in=selected_ids, user=request.user)
        if selected_ids:
            try:
                ProductDetail.objects.filter(id__in=selected_ids, user=request.user).delete()
                messages.success(request, f"{len(selected_ids)} product detail(s) deleted successfully.")
            except ProtectedError as e:
                protected_sales_items = e.protected_objects
                protected_transaction_ids = {item.transaction.id for item in protected_sales_items}
                conflicting_sales = SalesTransaction.objects.filter(id__in=protected_transaction_ids).distinct()
                messages.error(request, "Deletion failed because these products are part of existing sales records. Please review and handle these sales first.")
                context = {
                    'products_to_delete': products_to_delete,
                    'conflicting_sales': conflicting_sales,
                }
                return render(request, 'stock/deletion_blocked_by_sales.html', context)
    return redirect('stock:add_product_details')

@login_required
def product_detail_update_view(request, pk):
    instance  = get_object_or_404(ProductDetail, pk=pk, user=request.user)
    if request.method == 'POST':
        form = ProductDetailForm(request.POST, instance=instance , user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, f"Details for '{instance .product_base.name}' updated successfully!")
            query = request.GET.get('q_after_update', '')
            redirect_url = redirect('stock:add_product_details').url
            if query: redirect_url += f'?q={query}'
            return redirect(redirect_url)
        else:
            messages.error(request, "Error updating. Please check the data and try again.")
            return redirect('stock:add_product_details')
    else:
        return redirect('stock:add_product_details')
    

@login_required
def add_stock_to_product_detail_view(request, pk):
    # Get the ProductDetail instance, ensuring user ownership
    product_detail = get_object_or_404(ProductDetail, pk=pk, user=request.user)
    
    if request.method == 'POST':
        form = AddStockForm(request.POST, product_detail_instance=product_detail)
        if form.is_valid():
            new_stock_quantity = form.cleaned_data['new_stock_quantity']
            new_expiry_date = form.cleaned_data['new_expiry_date']

            try:
                with transaction.atomic():
                    # Check if a batch with the exact same new expiry date already exists for this product
                    existing_batch =  ProductDetail.objects.select_for_update().get(pk=pk, user=request.user)
                    if existing_batch:
                        # Add stock to the existing batch with the same expiry date
                        existing_batch.increase_stock(new_stock_quantity)   
                        existing_batch.expirey_date = new_expiry_date
                        existing_batch.save(update_fields=['stock', 'expirey_date', 'updated_at'])
                        messages.success(request, f"Added {new_stock_quantity} stock to existing batch of {existing_batch.product_base.name} (Exp: {new_expiry_date}). New stock: {existing_batch.stock}.")
                    else:
                        # Create a new ProductDetail instance for the new batch
                        new_batch = ProductDetail.objects.create(
                            product_base=product_detail.product_base,
                            user=request.user,
                            packing_type=product_detail.packing_type,
                            quantity_in_packing=product_detail.quantity_in_packing,
                            unit_of_measure=product_detail.unit_of_measure,
                            items_per_master_unit=product_detail.items_per_master_unit,
                            price_per_item=product_detail.price_per_item,
                            stock=new_stock_quantity,
                            expirey_date=new_expiry_date
                        )
                        messages.success(request, f"New stock batch created for {new_batch.product_base.name} with quantity {new_stock_quantity} and expiry {new_expiry_date}.")
                    
                return redirect('stock:add_product_details')
            except Exception as e:
                messages.error(request, f"An error occurred while adding stock: {str(e)}")
        else:
            # This is tricky for a modal. We redirect with a generic error.
            # A better UX would use AJAX for this form submission.
            error_string = ". ".join([f"{field}: {', '.join(errors)}" for field, errors in form.errors.items()])
            messages.error(request, f"Failed to add stock. {error_string}")
            return redirect('stock:add_product_details')
    
    # This view is for POST only from the modal
    return redirect('stock:add_product_details')


#  sales views...................................................................................................................

@login_required
def sales_processing_view(request):
    """
    Handles the entire multi-item sales process, including adding items to a
    session-based cart and finalizing the transaction with an overall discount.
    """
    # Session key for the current "cart" of sale items
    current_transaction_items_session_key = f'current_transaction_items_{request.user.id}'
    
    # Initialize forms for both GET and POST requests
    add_item_form = AddItemToSaleForm(user=request.user)
    finalize_sale_form = FinalizeSaleForm(user=request.user)

    if request.method == 'POST':
        action = request.POST.get('action')

        # --- ACTION 1: ADD ITEM TO THE CURRENT TRANSACTION ---
        if action == 'add_item_to_transaction':
            add_item_form = AddItemToSaleForm(request.POST, user=request.user)
            if add_item_form.is_valid():
                product_detail_batch = add_item_form.cleaned_data['product_detail_batch']
                quantity_to_add = add_item_form.cleaned_data['quantity_to_add']
                selling_price_item = add_item_form.cleaned_data['selling_price_per_item']
                current_items = request.session.get(current_transaction_items_session_key, [])

                # Check for duplicates
                if any(item['product_detail_id'] == product_detail_batch.id for item in current_items):
                    messages.warning(request, f"{product_detail_batch.product_base.name} is already in the list. Remove to re-add with new quantity/price.")
                else:
                    # Calculate gross subtotal for this line (no discount here)
                    individual_items_count = product_detail_batch._get_items_from_decimal(quantity_to_add)
                    gross_subtotal = individual_items_count * selling_price_item
                    
                    current_items.append({
                        'product_detail_id': product_detail_batch.id,
                        'product_display_name': f"{product_detail_batch.product_base.name} (Exp: {product_detail_batch.expirey_date.strftime('%d-%b-%Y')})",
                        'quantity_decimal': str(quantity_to_add),
                        'selling_price_per_item': str(selling_price_item),
                        'cost_price_per_item': str(product_detail_batch.price_per_item),
                        'line_subtotal': str(gross_subtotal.quantize(Decimal('0.01'))) # Store the gross (undiscounted) subtotal
                    })
                    messages.success(request, f"Added {quantity_to_add} of {product_detail_batch.product_base.name} to transaction.")
                
                request.session[current_transaction_items_session_key] = current_items
            return redirect('stock:sales')

        # --- ACTION 2: REMOVE ITEM FROM THE CURRENT TRANSACTION ---
        elif action == 'remove_item_from_transaction':
            item_index_to_remove = request.POST.get('item_index')
            current_items = request.session.get(current_transaction_items_session_key, [])
            try:
                item_index = int(item_index_to_remove)
                if 0 <= item_index < len(current_items):
                    current_items.pop(item_index)
                    request.session[current_transaction_items_session_key] = current_items
                    messages.info(request, "Item removed from transaction.")
                else:
                    messages.error(request, "Invalid item index to remove.")
            except (ValueError, TypeError):
                messages.error(request, "Error removing item.")
            return redirect('stock:sales')

        # --- ACTION 3: FINALIZE THE ENTIRE TRANSACTION ---
        elif action == 'finalize_transaction':
            current_items = request.session.get(current_transaction_items_session_key, [])
            if not current_items:
                messages.warning(request, "Cannot complete an empty transaction.")
                return redirect('stock:sales')

            finalize_sale_form = FinalizeSaleForm(request.POST, user=request.user)
            if finalize_sale_form.is_valid():
                try:
                    with transaction.atomic():
                        # Create the SalesTransaction header instance from the form
                        # This automatically includes the new 'total_discount_amount'
                        sales_transaction_header = finalize_sale_form.save(commit=False)
                        sales_transaction_header.user = request.user
                        sales_transaction_header.status = 'PENDING_DELIVERY' if sales_transaction_header.needs_vehicle else 'COMPLETED'
                        sales_transaction_header.save() # First save to get a primary key

                        # Loop through items in session to create SalesTransactionItem objects
                        for item_data in current_items:
                            pd_batch = ProductDetail.objects.select_for_update().get(pk=item_data['product_detail_id'])
                            
                            if not pd_batch.decrease_stock(Decimal(item_data['quantity_decimal'])):
                                raise Exception(f"Stock update failed for {pd_batch}. Transaction rolled back.")

                            SalesTransactionItem.objects.create(
                                transaction=sales_transaction_header,
                                product_detail_snapshot=pd_batch,
                                quantity_sold_decimal=Decimal(item_data['quantity_decimal']),
                                selling_price_per_item=Decimal(item_data['selling_price_per_item']),
                                cost_price_per_item_at_sale=Decimal(item_data['cost_price_per_item']),
                            )
                        
                        # After creating all items, call the method to calculate final totals
                        sales_transaction_header.update_grand_totals()
                        sales_transaction_header.refresh_from_db()

                        # Create a ledger entry if the payment type is CREDIT
                        if sales_transaction_header.payment_type == 'CREDIT':
                            ShopFinancialTransaction.objects.create(
                                shop=sales_transaction_header.customer_shop,
                                customer_name_snapshot=sales_transaction_header.customer_name_manual,
                                user=request.user,
                                source_sale=sales_transaction_header,
                                transaction_type='CREDIT_SALE',
                                debit_amount=sales_transaction_header.grand_total_revenue, # This is now the final, discounted amount
                                notes=f"Credit from Sale Transaction #{sales_transaction_header.pk}"
                            )
                        
                        messages.success(request, f"Transaction #{sales_transaction_header.pk} completed successfully!")
                        del request.session[current_transaction_items_session_key] # Clear the cart
                        return redirect('stock:sales')

                except ProductDetail.DoesNotExist:
                    messages.error(request, "Error: A product in the transaction could not be found. Transaction cancelled.")
                except Exception as e:
                    messages.error(request, f"An unexpected error occurred: {str(e)}")
            else:
                messages.error(request, "Please correct the errors in the final sale details below.")

    # --- For GET requests or if a POST fails validation ---
    current_transaction_items = request.session.get(current_transaction_items_session_key, [])
    current_transaction_subtotal = sum(Decimal(item['line_subtotal']) for item in current_transaction_items)

    context = {
        'add_item_form': add_item_form,
        'finalize_sale_form': finalize_sale_form,
        'current_transaction_items': current_transaction_items,
        'current_transaction_subtotal': current_transaction_subtotal,
    }
    return render(request, 'stock/sales_multiem.html', context)




@login_required
def bulk_delete_sales_view(request):
    """
    Handles the deletion of a specific list of sales transactions,
    typically those that are blocking a product deletion.
    """
    if request.method == 'POST':
        sales_ids_str = request.POST.get('sales_ids_to_delete')
        if sales_ids_str:
            try:
                # Convert the string of IDs '1,2,3' into a list of integers
                sales_ids = [int(id_str) for id_str in sales_ids_str.split(',') if id_str.isdigit()]
                
                # Fetch the transactions belonging to the current user to ensure security
                transactions_to_delete = SalesTransaction.objects.filter(pk__in=sales_ids, user=request.user)
                
                count = transactions_to_delete.count()
                
                if count > 0:
                    transactions_to_delete.delete()
                    messages.success(request, f"Successfully deleted {count} conflicting sales record(s). You may now try deleting the product(s) again.")
                else:
                    messages.warning(request, "No matching sales records were found to delete.")

            except Exception as e:
                messages.error(request, f"An error occurred while deleting sales: {str(e)}")
        else:
            messages.warning(request, "No sales IDs were provided for deletion.")

    # Always redirect back to the product details page, as the user's task is now to re-attempt the product deletion.
    return redirect('stock:add_product_details')




# AJAX endpoint to get details for a selected product_detail_batch
# This is used by JavaScript to auto-fill parts of the SaleForm
@login_required
def ajax_get_batch_details_for_sale(request, pk): # Renamed from get_sale_product_batch_details_json
    try:
        detail = get_object_or_404(ProductDetail, pk=pk, user=request.user)
        
        # Ensure properties total_items_in_stock and display_stock are robust in ProductDetail model
        data = {
            'pk': detail.pk,
            'product_name_display': str(detail.product_base.name),
            'expiry_date_display': detail.expirey_date.strftime('%Y-%m-%d'),
            'current_stock_master_units_display': str(detail.stock), # e.g., "2.5"
            'current_stock_master_units_unit': "units" , # You might want a unit field on ProductDetail or AddProduct
            'total_individual_items_available': detail.total_items_in_stock,
            'cost_price_per_item': str(detail.price_per_item),
            'suggested_selling_price_per_item': str(round(detail.price_per_item * Decimal('1.20'), 2)), # 20% markup
        }
        return JsonResponse({'success': True, 'data': data})
    except ProductDetail.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Product batch not found or not authorized.'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'An error occurred in AJAX: {str(e)}'}, status=500)


@login_required
def all_transactions_list_view(request):
    transactions_list = SalesTransaction.objects.filter(
        user=request.user # Or remove/adjust if admins see all
    ).select_related(
        'customer_shop', 
        'assigned_vehicle'
    ).prefetch_related(
        'items__product_detail_snapshot__product_base' # For product summary
    ).order_by('-transaction_time')

    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    if start_date and not end_date:
        # **Special Case**: If only start_date is provided, filter for that single day.
        # The '__date' lookup matches the date part of a DateTimeField.
        transactions_list = transactions_list.filter(transaction_time__date=start_date)
    else:
        # Standard range filter: apply if dates are present.
        # This works if both are present, or if only end_date is present.
        if start_date:
            transactions_list = transactions_list.filter(transaction_time__date__gte=start_date)
        if end_date:
            transactions_list = transactions_list.filter(transaction_time__date__lte=end_date)
    # Pagination (optional, but good for long lists)
    paginator = Paginator(transactions_list, 50) # Show 50 transactions per page
    page_number = request.GET.get('page')
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1) # If page is not an integer, deliver first page.
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        page_obj = paginator.page(paginator.num_pages)

    context = {
        'page_obj': page_obj, # Use page_obj in template for pagination
        'transactions': page_obj.object_list, # The transactions for the current page
    }
    return render(request, 'stock/all_transactions_list.html', context)


@login_required
def export_sales_to_excel(request):
    """
    Handles the export of sales transactions to an Excel (.xlsx) file.
    Can be filtered by a date range OR a specific list of transaction IDs.
    """
    # Start with the base queryset for the logged-in user
    transactions_list = SalesTransaction.objects.filter(user=request.user)

    # --- NEW: Check for a specific list of IDs first ---
    ids_to_export_str = request.GET.get('ids')
    if ids_to_export_str:
        try:
            # Convert comma-separated string of IDs to a list of integers
            ids_list = [int(id_str) for id_str in ids_to_export_str.split(',') if id_str.isdigit()]
            if ids_list:
                transactions_list = transactions_list.filter(pk__in=ids_list)
        except (ValueError, TypeError):
            # If IDs are invalid, ignore and proceed to date filters
            pass
    else:
        # --- EXISTING DATE FILTER LOGIC ---
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')

        if start_date and not end_date:
            transactions_list = transactions_list.filter(transaction_time__date=start_date)
        else:
            if start_date:
                transactions_list = transactions_list.filter(transaction_time__date__gte=start_date)
            if end_date:
                transactions_list = transactions_list.filter(transaction_time__date__lte=end_date)

    # Apply optimizations and ordering
    transactions_list = transactions_list.select_related(
        'customer_shop', 'assigned_vehicle'
    ).prefetch_related( # Prefetch items and their nested details for performance
        'items__product_detail_snapshot__product_base'
    ).order_by('-transaction_time')

    # Create the Excel Workbook and Worksheet in memory
    wb = Workbook()
    ws = wb.active
    ws.title = "Sales Report"

    # Define the Headers
    columns = [
        "Tx ID", "Date", "Time", "Customer", "Payment", "Status",
        "Total Revenue", "Total Profit", "Notes",  # Transaction-level info
        "Product Name", "Price Per Unit", "Quantity Sold", "Returned", "Discount", "Unit", # Item-level info
    ]
    ws.append(columns)

    # Style the header row (bold font)
    bold_font = Font(bold=True)
    for col_num in range(1, len(columns) + 1):
        cell = ws.cell(row=1, column=col_num)
        cell.font = bold_font

    # Loop through the queryset and append data rows
    for tx in transactions_list:
        # Using .all() on a prefetched queryset is efficient (no extra DB hit here)
        all_items = tx.items.all()
        customer_name = tx.customer_shop.name if tx.customer_shop else tx.customer_name_manual or "N/A"

        # If a transaction has no items, we might still want to log it
        if not all_items:
            row = [
                tx.pk,
                tx.transaction_time.date(),
                tx.transaction_time.time().strftime('%H:%M:%S'),
                customer_name,
                tx.get_payment_type_display(),
                tx.get_status_display(),
                tx.grand_total_revenue, # Use number format for better sorting in Excel
                tx.calculated_grand_profit,
                tx.notes,
            ]
            ws.append(row)
        else:
            # If there are items, create a row for each one
            for item in all_items:
                row = [
                    tx.pk,
                    tx.transaction_time.date(),
                    tx.transaction_time.time().strftime('%H:%M:%S'),
                    customer_name,
                    tx.get_payment_type_display(),
                    tx.get_status_display(),
                    tx.grand_total_revenue,
                    tx.calculated_grand_profit,
                    tx.notes,
                    item.product_detail_snapshot.product_base.name,
                    item.selling_price_per_item,
                    item.quantity_sold_decimal,
                    item.returned_quantity_decimal,
                    f'{tx.total_discount_amount}', 
                    f'{item.product_detail_snapshot.quantity_in_packing} {item.product_detail_snapshot.unit_of_measure}',
                ]
                ws.append(row)

    # Auto-size columns for better readability
    for col_num, column_title in enumerate(columns, 1):
        column_letter = get_column_letter(col_num)
        ws.column_dimensions[column_letter].autosize = True

    # Prepare the HTTP response to serve the file
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    # Define a dynamic filename
    filename = "sales_report.xlsx"
    if ids_to_export_str:
        filename = "conflicting_sales_export.xlsx"
    elif start_date and end_date:
        filename = f"sales_{start_date}_to_{end_date}.xlsx"
    elif start_date:
        filename = f"sales_{start_date}.xlsx"
        
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    # Save the workbook to the response
    wb.save(response)

    return response




@login_required
def update_note(request):
    tx_id = request.POST.get('tx_id')
    new_note = request.POST.get('note', '')
    url = request.POST.get('next')
    tx = get_object_or_404(SalesTransaction, pk=tx_id)
    if tx:
        tx.notes = new_note
        tx.save()
    else:
        messages.error(request, f"no Transaction found")
    if url == 'shop_purchase_history':
        shop_pk = request.POST.get('shop_pk') 
        return redirect('stock:shop_purchase_history', shop_pk=shop_pk)
    return redirect('stock:all_transactions_list')  # or the same page





@login_required
def pending_deliveries_view(request):
    pending_sales_transactions = SalesTransaction.objects.filter(
        user=request.user, # Transactions processed by this user
        status=SalesTransaction.SALE_STATUS_CHOICES[1][0] # 'PENDING_DELIVERY'
    ).select_related(
        'customer_shop', 
        'assigned_vehicle'
    ).prefetch_related( # To get items and their product details efficiently
        'items__product_detail_snapshot__product_base' 
    ).order_by('transaction_time') # Oldest pending first

    context = {
        'pending_transactions': pending_sales_transactions, # Changed context variable name
    }
    return render(request, 'stock/pending_deliveries.html', context)





@login_required
def process_delivery_return_view(request, sale_pk):
    """
    Handles the processing of returns and final settlement for a sales transaction.
    This view correctly updates returned quantities, stock, discount amount, totals,
    status, and financial ledger entries in the correct logical order.
    """
    # Get the single source-of-truth object for this transaction at the start.
    sales_transaction = get_object_or_404(
        SalesTransaction, 
        pk=sale_pk, 
        user=request.user, 
        status__in=['PENDING_DELIVERY', 'PARTIALLY_RETURNED']
    )
    
    # The queryset for the formset is based on this single transaction instance.
    items_queryset = SalesTransactionItem.objects.filter(transaction=sales_transaction)

    if request.method == 'POST':
        # Initialize forms with POST data and the correct instances.
        return_formset = SalesTransactionItemReturnFormSet(request.POST, queryset=items_queryset)
        payment_form = UpdatePaymentTypeForm(request.POST, instance=sales_transaction)

        if return_formset.is_valid() and payment_form.is_valid():
            try:
                with transaction.atomic():
                    # --- Step 1: Update Item Returns and Adjust Stock ---
                    # Loop through each item form. If it has changed, update the returned quantity
                    # and adjust the stock of the corresponding ProductDetail.
                    for form in return_formset:
                        if form.has_changed() and 'returned_quantity_decimal' in form.changed_data:
                            # Use form.save(commit=False) to get the instance with the new data without saving yet.
                            item_instance = form.save(commit=False)
                            
                            # Fetch the original state from the DB to calculate the stock change
                            original_item = SalesTransactionItem.objects.get(pk=item_instance.pk)
                            stock_change_difference = item_instance.returned_quantity_decimal - original_item.returned_quantity_decimal
                            
                            if stock_change_difference != Decimal('0.0'):
                                product_detail_to_update = item_instance.product_detail_snapshot
                                if stock_change_difference > 0: # More items returned
                                    product_detail_to_update.increase_stock(stock_change_difference)
                                else: # A return was undone (less common)
                                    product_detail_to_update.decrease_stock(abs(stock_change_difference))
                            
                            # Save the item, but tell it NOT to update the parent transaction yet.
                            # This prevents premature calculations.
                            item_instance.save(update_parent=False)

                    # --- Step 2: Apply Final Form Data to the Transaction Object ---
                    # Get the final payment type and the NEW discount amount from the form.
                    new_payment_type = payment_form.cleaned_data['payment_type']
                    new_discount_amount = payment_form.cleaned_data['total_discount_amount']

                    # Apply these new values directly to our main transaction object in memory.
                    sales_transaction.payment_type = new_payment_type
                    sales_transaction.total_discount_amount = new_discount_amount
                    
                    # --- Step 3: Trigger a SINGLE, FINAL Recalculation ---
                    # Now, call update_grand_totals. It will use the correct item returns (from Step 1)
                    # and the new discount amount (from Step 2) to perform a perfect calculation.
                    # This method saves the new grand_total_revenue and grand_total_cost.
                    sales_transaction.update_grand_totals()
                    
                    # --- Step 4: Update the Transaction Status ---
                    # We must refresh the object from the DB to get the freshly calculated totals.
                    sales_transaction.refresh_from_db()

                    final_items = sales_transaction.items.all()
                    total_dispatched = sum(item.dispatched_individual_items_count for item in final_items)
                    total_returned = sum(item.returned_individual_items_count for item in final_items)

                    if total_returned == 0:
                        sales_transaction.status = 'COMPLETED'
                    elif total_returned >= total_dispatched:
                        sales_transaction.status = 'FULLY_RETURNED'
                    else:
                        sales_transaction.status = 'PARTIALLY_RETURNED'
                    
                    # --- Step 5: Perform the FINAL save to the database ---
                    # This saves the status and permanently stores the new payment type and discount.
                    sales_transaction.save(
                        update_fields=[
                            'status', 
                            'payment_type', 
                            'total_discount_amount'
                        ]
                    )

                    # --- Step 6: Update Financial Ledger Entry ---
                    # This logic will now work correctly as it uses the final, correct transaction state.
                    existing_credit_entry = ShopFinancialTransaction.objects.filter(source_sale=sales_transaction).first()
                    if sales_transaction.payment_type == 'CREDIT' and sales_transaction.customer_shop:
                        final_revenue = sales_transaction.grand_total_revenue
                        if existing_credit_entry:
                            existing_credit_entry.debit_amount = final_revenue
                            existing_credit_entry.save(update_fields=['debit_amount'])
                        else:
                            ShopFinancialTransaction.objects.create(
                                shop=sales_transaction.customer_shop, user=request.user,
                                source_sale=sales_transaction, transaction_type='CREDIT_SALE',
                                debit_amount=final_revenue
                            )
                    elif sales_transaction.payment_type != 'CREDIT' and existing_credit_entry:
                        existing_credit_entry.delete()

                    messages.success(request, f"Delivery for Transaction #{sales_transaction.pk} processed successfully.")
                    return redirect('stock:pending_deliveries')

            except Exception as e:
                messages.error(request, f"A critical error occurred: {str(e)}")
        else: # Forms are not valid
            messages.error(request, "Please correct the errors shown below.")
    
    # For GET request or if POST had errors
    else: 
        return_formset = SalesTransactionItemReturnFormSet(queryset=items_queryset)
        payment_form = UpdatePaymentTypeForm(instance=sales_transaction)

    context = {
        'return_formset': return_formset,
        'payment_form': payment_form,
        'transaction': sales_transaction
    }
    return render(request, 'stock/process_delivery_return.html', context)  






@login_required
def sales_report_view(request):
    today = timezone.localdate()
    # ... (date range setup: start_of_today_dt, end_of_today_dt, etc. - as before) ...
    # Ensure these are timezone-aware datetimes for comparison with transaction_time
    start_of_today  = timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.min.time()))
    end_of_today  = timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.max.time()))

    # ... similarly for week, month, year ...
    start_of_week = start_of_today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6, hours=23, minutes=59, seconds=59)

    start_of_month = start_of_today.replace(day=1)
    next_month = start_of_month.replace(day=28) + timedelta(days=4)
    end_of_month = next_month - timedelta(days=next_month.day)
    end_of_month = timezone.make_aware(timezone.datetime.combine(end_of_month.date(), timezone.datetime.max.time()))
    
    start_of_year = start_of_today.replace(month=1, day=1)
    end_of_year = start_of_year.replace(year=start_of_year.year + 1) - timedelta(days=1)
    end_of_year = timezone.make_aware(timezone.datetime.combine(end_of_year.date(), timezone.datetime.max.time()))


    def get_period_stats(start_dt, end_dt):
        """
        Helper function to get sales and expense stats for a given period.
        """
        transactions = SalesTransaction.objects.filter(
            user=request.user, 
            transaction_time__range=(start_dt, end_dt)
        )
        expenses = Expense.objects.filter(
            user=request.user, 
            expense_date__range=(start_dt, end_dt)
        )
        claims = Claim.objects.filter(
            user=request.user,
            status='COMPLETED',
            claim_date__range=(start_dt, end_dt)
        )
        stock_claim_loss = sum(claim.value_of_items_given for claim in claims) or Decimal('0.00')
        
        total_revenue = sum(tx.grand_total_revenue for tx in transactions)
        total_profit = sum(tx.calculated_grand_profit for tx in transactions)
        total_expense = expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
                
        net_profit = total_profit - total_expense - stock_claim_loss
        
        return {
            'transactions_count': transactions.count(),
            'total_grand_revenue': total_revenue,
            'total_grand_profit': total_profit,
            'total_expense': total_expense,
            'stock_claim_loss': stock_claim_loss,
            'net_profit': net_profit,
        }

    stats_today = get_period_stats(start_of_today, end_of_today)
    stats_this_week = get_period_stats(start_of_week, end_of_week)
    stats_this_month = get_period_stats(start_of_month, end_of_month)
    stats_this_year = get_period_stats(start_of_year, end_of_year)

    # --- Data for Charts (using SalesTransaction) ---
    daily_labels = []
    daily_revenue_data = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        start = timezone.make_aware(timezone.datetime.combine(day, timezone.datetime.min.time()))
        end = timezone.make_aware(timezone.datetime.combine(day, timezone.datetime.max.time()))

        tx_on_day = SalesTransaction.objects.filter(user=request.user, transaction_time__range=(start, end))
        daily_revenue = sum(tx.grand_total_revenue for tx in tx_on_day) or Decimal('0.00')

        daily_labels.append(day.strftime("%a")) # Short day name e.g., "Mon"
        daily_revenue_data.append(float(daily_revenue))



    # ... Monthly chart data logic ...
    monthly_labels = []
    monthly_revenue_data = []
    for i in range(5, -1, -1):
        # ... (logic for first_day_of_target_month, last_day_of_target_month as before) ...

        target_month_date = today # Start from today for current month calculation
        
        for _ in range(i):
            first_day_of_prev_month = target_month_date.replace(day=1) - timedelta(days=1)
            target_month_date = first_day_of_prev_month
        start_of_target_month = target_month_date.replace(day=1)
        next_m = start_of_target_month.replace(day=28) + timedelta(days=4)
        end_of_target_month = next_m - timedelta(days=next_m.day)
        
        start_dt = timezone.make_aware(timezone.datetime.combine(start_of_target_month, timezone.datetime.min.time()))
        end_dt = timezone.make_aware(timezone.datetime.combine(end_of_target_month, timezone.datetime.max.time()))
        
        tx_in_month = SalesTransaction.objects.filter(user=request.user, transaction_time__range=(start_dt, end_dt))
        monthly_revenue = sum(tx.grand_total_revenue for tx in tx_in_month) or Decimal('0.00')
        
        monthly_labels.append(start_of_target_month.strftime("%b %Y"))
        monthly_revenue_data.append(float(monthly_revenue))
        
    context = {
        'stats_today': stats_today,
        'stats_this_week': stats_this_week,
        'stats_this_month': stats_this_month,
        'stats_this_year': stats_this_year,
        'report_generation_time': timezone.now(),
        'daily_chart_labels': json.dumps(daily_labels),
        'daily_chart_revenue': json.dumps(daily_revenue_data),
        'monthly_chart_labels': json.dumps(monthly_labels),
        'monthly_chart_revenue': json.dumps(monthly_revenue_data),
    }
    return render(request, 'stock/sales_report.html', context)


# Recepit View ...................................

@login_required
def sale_receipt_view(request, sale_pk): # sale_pk is now the PK of SalesTransaction
    # Fetch the SalesTransaction, ensuring it belongs to the current user
    # Pre-fetch related items and their product details for efficiency
    sales_transaction = get_object_or_404(
        SalesTransaction.objects.select_related(
            'user', 
            'customer_shop', 
            'assigned_vehicle'
        ).prefetch_related(
            'items__product_detail_snapshot__product_base' # Prefetch items and their nested details
        ),
        pk=sale_pk,
        user=request.user # Or adjust if admins can print any receipt
    )

    # Company details (as before, or from a settings/profile model)
    context = {
        'transaction': sales_transaction, # Pass the whole transaction object
        'company_name': "Your Agency/Company Name",
        'company_address': "123 Main St, City, Country",
        'company_phone': "555-1234",
    }
    return render(request, 'stock/sale_receipt.html', context)

# vehical views ............................................................................................................
@login_required
def manage_vehicles_view(request):
    add_form_in_modal_has_errors = False 
    add_vehicle_form = VehicleForm() # For the "Add New Vehicle" modal

    if request.method == 'POST':
        # This assumes POST to this view is for creating new vehicle.
        # Update actions will POST to vehicle_update_action_view.
        filled_add_form = VehicleForm(request.POST)
        if filled_add_form.is_valid():
            vehicle_instance = filled_add_form.save(commit=False)
            vehicle_instance.user = request.user
            vehicle_instance.save()
            messages.success(request, f"Vehicle '{vehicle_instance.vehicle_number}' added successfully!")
            return redirect('stock:manage_vehicles')
        else:
            messages.error(request, "Error adding vehicle. Please correct the form.")
            add_form_in_modal_has_errors = True
            add_vehicle_form = filled_add_form # Pass form with errors back to "Add" modal
    
    vehicles_list = Vehicle.objects.filter(user=request.user).order_by('-created_at')
    context = {
        'add_form': add_vehicle_form, # Use a specific name for the add form
        'vehicles': vehicles_list,
        'add_form_in_modal_has_errors': add_form_in_modal_has_errors,
    }
    return render(request, 'stock/add_vehicles.html', context)


@login_required
def vehicle_update_action_view(request, vehicle_pk):
    instance = get_object_or_404(Vehicle, pk=vehicle_pk, user=request.user)
    if request.method == 'POST':
        form = VehicleForm(request.POST, instance=instance)
        if form.is_valid():
            # The user field is already set on instance and is not part of VehicleForm fields by default
            # If you needed to change the user, you'd handle it explicitly.
            # For now, assume only user who created can update.
            # vehicle_to_update = form.save(commit=False)
            # vehicle_to_update.user = request.user # Ensure user is still correct if it was part of form
            form.save() # This updates the instance
            messages.success(request, f"Vehicle '{instance.vehicle_number}' updated successfully!")
            return redirect('stock:manage_vehicles')
        else:
            # This is tricky for a modal on another page without full page reload for the update form.
            # Ideally, the update modal form would submit via AJAX to this view.
            # If it fails, this view returns JSON errors, and JS updates the modal.
            # For a non-AJAX POST from the modal:
            # We can't easily re-render the list page with the update modal open and errors.
            # So, we redirect with a generic error. The user would have to re-open the modal.
            error_message = "Failed to update vehicle. Please correct the errors: "
            for field, errors in form.errors.items():
                error_message += f"{field}: {', '.join(errors)} "
            messages.error(request, error_message.strip())
            # To pass form errors back to modal on list page is complex without AJAX for the update itself.
            # Simplest is redirect. User will lose their unsaved changes in modal.
            return redirect('stock:manage_vehicles') 
    else:
        # This view is primarily for POST. A GET request isn't typical for modal updates.
        return redirect('stock:manage_vehicles')
    
@login_required
def ajax_get_vehicle_data(request, vehicle_pk):
    try:
        vehicle = get_object_or_404(Vehicle, pk=vehicle_pk, user=request.user)
        data = {
            'pk': vehicle.pk,
            'vehicle_number': vehicle.vehicle_number,
            'vehicle_type': vehicle.vehicle_type,
            'driver_name': vehicle.driver_name or "",
            'driver_phone': vehicle.driver_phone or "",
            'capacity_kg': str(vehicle.capacity_kg) if vehicle.capacity_kg is not None else "",
            'notes': vehicle.notes or "",
            'is_active': vehicle.is_active,
        }
        return JsonResponse({'success': True, 'data': data})
    except Vehicle.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Vehicle not found or not authorized.'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    




@login_required
def delete_vehicle_action_view(request, vehicle_pk):
    # Fetch the vehicle, ensuring it belongs to the current user
    vehicle_to_delete = get_object_or_404(Vehicle, pk=vehicle_pk, user=request.user)

    if request.method == 'POST': # This will be from the modal's form
        vehicle_number = vehicle_to_delete.vehicle_number
        try:
            vehicle_to_delete.delete()
            messages.success(request, f"Vehicle '{vehicle_number}' has been deleted successfully.")
        except Exception as e:
            messages.error(request, f"Error deleting vehicle '{vehicle_number}': {str(e)}")
        return redirect('stock:manage_vehicles') # Redirect back to the vehicle list
    else:
        # Direct GET access to this URL is not intended with the modal approach
        messages.warning(request, "Invalid request for vehicle deletion.")
        return redirect('stock:manage_vehicles')
    



# shop views.................................................................................................
@login_required
def manage_shops_view(request):
    add_form_in_modal_has_errors = False 
    add_shop_form = ShopForm() # For the "Add New Shop" modal

    if request.method == 'POST':
        # This assumes POST to this view is for creating new shop.
        # Update actions will POST to shop_update_action_view.
        filled_add_form = ShopForm(request.POST)
        if filled_add_form.is_valid():
            shop_instance = filled_add_form.save(commit=False)
            shop_instance.user = request.user
            shop_instance.save()
            messages.success(request, f"Shop '{shop_instance.name}' added successfully!")
            return redirect('stock:manage_shops')
        else:
            messages.error(request, "Error adding shop. Please correct the form.")
            add_form_in_modal_has_errors = True
            add_shop_form = filled_add_form # Pass form with errors back to "Add" modal
    
    shops_list = Shop.objects.filter(user=request.user).order_by('name')
    context = {
        'add_form': add_shop_form, # Use a specific name for the add form
        'shops': shops_list,
        'add_form_in_modal_has_errors': add_form_in_modal_has_errors,
    }
    return render(request, 'stock/add_shops.html', context)

@login_required
def delete_shop_action_view(request, shop_pk):
    shop_to_delete = get_object_or_404(Shop, pk=shop_pk, user=request.user)

    if request.method == 'POST': # From modal confirmation
        shop_name = shop_to_delete.name
        try:
            shop_to_delete.delete()
            messages.success(request, f"Shop '{shop_name}' has been deleted successfully.")
        except Exception as e:
            # Handle potential ProtectedError if shops are linked to other models that prevent deletion
            messages.error(request, f"Error deleting shop '{shop_name}': {str(e)}. It might be linked to other records.")
        return redirect('stock:manage_shops')
    else:
        messages.warning(request, "Invalid request for shop deletion.")
        return redirect('stock:manage_shops')
    

@login_required
def shop_update_action_view(request, shop_pk):
    instance = get_object_or_404(Shop, pk=shop_pk, user=request.user)
    if request.method == 'POST':
        form = ShopForm(request.POST, instance=instance)
        if form.is_valid():
            form.save() # This updates the instance
            messages.success(request, f"Shop '{instance.name}' updated successfully!")
            return redirect('stock:manage_shops')
        else:
            error_message = "Failed to update shop. Please correct the errors: "
            for field, errors in form.errors.items(): # Concatenate all errors
                error_message += f"Field '{field}': {', '.join(errors)} "
            messages.error(request, error_message.strip())
            # Redirect back, user will have to click edit again.
            # For better UX, the modal form would POST via AJAX to this view.
            return redirect('stock:manage_shops') 
    else:
        # This view is primarily for POST from the modal.
        return redirect('stock:manage_shops')
    

@login_required
def ajax_get_shop_data(request, shop_pk):
    try:
        shop = get_object_or_404(Shop, pk=shop_pk, user=request.user)
        data = {
            'pk': shop.pk,
            'name': shop.name,
            'location_address': shop.location_address or "",
            'contact_person': shop.contact_person or "",
            'contact_phone': shop.contact_phone or "",
            'email': shop.email or "",
            'notes': shop.notes or "",
            'is_active': shop.is_active,
        }
        return JsonResponse({'success': True, 'data': data})
    except Shop.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Shop not found or not authorized.'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)



@login_required
def list_shops_for_sales_view(request):
    # This view should be fine if it only lists Shop instances.
    # The links it generates will point to shop_purchase_history_view.
    shops = Shop.objects.filter(user=request.user, is_active=True).order_by('name')
    context = {'shops': shops}
    return render(request, 'stock/list_shops_for_sales.html', context)

@login_required
def shop_purchase_history_view(request, shop_pk):
    shop = get_object_or_404(Shop, pk=shop_pk) # Potentially add user=request.user if shops are user-scoped

    # Fetch SalesTransaction records associated with this shop and processed by the current user
    shop_transactions = SalesTransaction.objects.filter(
        customer_shop=shop,
        user=request.user 
    ).select_related(
        'assigned_vehicle' # No need to select_related product_detail here, items are separate
    ).prefetch_related(
        'items__product_detail_snapshot__product_base'
    ).order_by('-transaction_time')

    # Recalculate totals based on the new structure
    shop_total_revenue = sum(tx.grand_total_revenue for tx in shop_transactions)
    shop_total_profit = sum(tx.calculated_grand_profit for tx in shop_transactions)

    context = {
        'shop': shop,
        'shop_transactions': shop_transactions, # Changed context variable name
        'shop_total_revenue': shop_total_revenue,
        'shop_total_profit': shop_total_profit,
    }
    return render(request, 'stock/shop_purchase_history.html', context)


@login_required
def sales_by_group_hub_view(request):
    """
    Displays a navigation hub with cards for each vehicle and one for the "Store".
    """
    # Get all active vehicles and annotate them with their sales count for display.
    vehicles = Vehicle.objects.filter(
        user=request.user, 
        is_active=True
    ).annotate(
        sales_count=Count('assigned_sales_transactions')
    ).order_by('vehicle_number')

    # Get the count of sales not assigned to any vehicle.
    store_sales_count = SalesTransaction.objects.filter(
        user=request.user,
        assigned_vehicle__isnull=True
    ).count()

    context = {
        'vehicles': vehicles,
        'store_sales_count': store_sales_count,
    }
    return render(request, 'stock/sales_by_group_hub.html', context)





@login_required
def performance_summary_hub_view(request):
    """
    Displays a navigation hub with cards for each vehicle and one for the "Store"
    to link to the performance summary page.
    """
    vehicles = Vehicle.objects.filter(user=request.user, is_active=True).order_by('vehicle_number')
    context = {
        'vehicles': vehicles,
    }
    return render(request, 'stock/performance_summary_hub.html', context)


@login_required
def group_performance_summary_view(request, vehicle_pk=None):
    """
    Calculates and displays daily and monthly sales totals for a specific
    vehicle or for the store (sales with no vehicle).
    """
    user = request.user
    
    # Filter the base queryset based on the selected group
    if vehicle_pk:
        grouping_object = get_object_or_404(Vehicle, pk=vehicle_pk, user=user)
        grouping_name = f"Performance Summary for: {grouping_object.vehicle_number}"
        base_query = SalesTransaction.objects.filter(user=user, assigned_vehicle=grouping_object)
    else:
        grouping_object = None
        grouping_name = "Performance Summary for: Store"
        base_query = SalesTransaction.objects.filter(user=user, assigned_vehicle__isnull=True)

    # --- Daily Sales Calculation ---
    # Group transactions by day and sum the revenue for each day
    daily_summary = base_query.annotate(
        day=TruncDate('transaction_time')
    ).values('day').annotate(
        total_revenue=Sum('grand_total_revenue')
    ).order_by('-day')

    # --- Monthly Sales Calculation ---
    # Group transactions by month and sum the revenue for each month
    monthly_summary = base_query.annotate(
        month=TruncMonth('transaction_time')
    ).values('month').annotate(
        total_revenue=Sum('grand_total_revenue')
    ).order_by('-month')

    context = {
        'grouping_name': grouping_name,
        'daily_summary': daily_summary,
        'monthly_summary': monthly_summary,
    }
    return render(request, 'stock/group_performance_summary.html', context)



@login_required
def sales_group_details_view(request, vehicle_pk=None):
    """
    Displays a filtered list of sales transactions for a specific group
    (either a vehicle or the store).
    """
    user = request.user
    
    # Start with the base query for all sales for the user.
    base_query = SalesTransaction.objects.filter(user=user).select_related(
        'customer_shop', 'assigned_vehicle'
    ).prefetch_related('items__product_detail_snapshot__product_base')

    # Filter the query based on the group selected.
    if vehicle_pk:
        # User selected a specific vehicle.
        grouping_object = get_object_or_404(Vehicle, pk=vehicle_pk, user=user)
        grouping_name = f"Sales for Vehicle: {grouping_object.vehicle_number}"
        transactions_list = base_query.filter(assigned_vehicle=grouping_object)
    else:
        # User selected the "Store".
        grouping_object = None
        grouping_name = "Store Sales (No Vehicle)"
        transactions_list = base_query.filter(assigned_vehicle__isnull=True)

    # --- Date Filtering (Optional but recommended) ---
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    if start_date:
        transactions_list = transactions_list.filter(transaction_time__date__gte=start_date)
    if end_date:
        transactions_list = transactions_list.filter(transaction_time__date__lte=end_date)
    
    # Final ordering
    transactions_list = transactions_list.order_by('-transaction_time')

    # --- Pagination ---
    paginator = Paginator(transactions_list, 50) # 50 sales per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'grouping_name': grouping_name,
        'page_obj': page_obj,
        'transactions': page_obj.object_list,
    }
    # We can reuse the main transaction list template.
    return render(request, 'stock/all_transactions_list.html', context)