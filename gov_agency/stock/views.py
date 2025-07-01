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
from django.contrib import messages
from django.db.models  import Q
from django.db import transaction # For atomic operations
from django.http import JsonResponse
from decimal import Decimal
from django.db.models import Sum,Count, F, ExpressionWrapper, fields, DecimalField
from django.utils import timezone
from datetime import timedelta, date
import json 
from django.db.models.functions import TruncMonth,TruncDay
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.urls import resolve








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
            Q(packing_type__icontains=query)|
            Q(notes__icontains=query)
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
        if selected_ids:
            ProductDetail.objects.filter(id__in=selected_ids, user=request.user).delete()
            messages.success(request, f"{len(selected_ids)} product detail(s) deleted successfully.")
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
    # Session key for the current "cart" of sale items
    current_transaction_items_session_key = f'current_transaction_items_{request.user.id}'
    
    # Initialize forms
    add_item_form = AddItemToSaleForm(user=request.user)
    finalize_sale_form = FinalizeSaleForm(user=request.user) # For final transaction details

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'add_item_to_transaction':
            add_item_form = AddItemToSaleForm(request.POST, user=request.user)
            if add_item_form.is_valid():
                product_detail_batch = add_item_form.cleaned_data['product_detail_batch']
                quantity_to_add = add_item_form.cleaned_data['quantity_to_add']
                selling_price_item = add_item_form.cleaned_data['selling_price_per_item']

                current_items = request.session.get(current_transaction_items_session_key, [])
                
                # Check if this exact product_detail_batch is already in the cart
                item_found = False
                for item in current_items:
                    if item['product_detail_id'] == product_detail_batch.id:
                        # Option: Update quantity and price if item exists
                        # item['quantity'] = str(Decimal(item['quantity']) + quantity_to_add) # If you want to sum quantities
                        # item['selling_price_per_item'] = str(selling_price_item) # Or update price
                        # For simplicity, let's prevent adding duplicates for now, or replace.
                        messages.warning(request, f"{product_detail_batch.product_base.name} (Exp: {product_detail_batch.expirey_date}) is already in the list. Remove to re-add with new quantity/price.")
                        item_found = True
                        break
                
                if not item_found:
                    current_items.append({
                        'product_detail_id': product_detail_batch.id,
                        'product_display_name': f"{product_detail_batch.product_base.name} (Exp: {product_detail_batch.expirey_date.strftime('%d-%b-%Y')})",
                        'quantity_decimal': str(quantity_to_add), # Store as string "1.1"
                        'selling_price_per_item': str(selling_price_item),
                        'cost_price_per_item': str(product_detail_batch.price_per_item), # Your cost
                        'items_per_master_unit': product_detail_batch.items_per_master_unit,
                        # Calculated subtotal for display in cart
                        # Requires converting quantity_decimal to individual items
                        'line_subtotal': str(product_detail_batch._get_items_from_decimal(quantity_to_add) * selling_price_item)
                    })
                    messages.success(request, f"Added {quantity_to_add} of {product_detail_batch.product_base.name} to transaction.")
                
                request.session[current_transaction_items_session_key] = current_items
                return redirect('stock:sales')

        elif action == 'remove_item_from_transaction':
            item_index_to_remove = request.POST.get('item_index')
            current_items = request.session.get(current_transaction_items_session_key, [])
            try:
                item_index_to_remove = int(item_index_to_remove)
                if 0 <= item_index_to_remove < len(current_items):
                    current_items.pop(item_index_to_remove)
                    request.session[current_transaction_items_session_key] = current_items
                    messages.info(request, "Item removed from current transaction.")
                else:
                    messages.error(request, "Invalid item index to remove.")
            except (ValueError, TypeError):
                messages.error(request, "Error removing item.")
            return redirect('stock:sales')

        elif action == 'finalize_transaction':
            current_items = request.session.get(current_transaction_items_session_key, [])
            if not current_items:
                messages.warning(request, "Cannot complete an empty transaction.")
                return redirect('stock:sales')

            finalize_sale_form = FinalizeSaleForm(request.POST, user=request.user)
            if finalize_sale_form.is_valid():
                try:
                    with transaction.atomic():
                        # Create SalesTransaction header
                        customer_shop_instance = finalize_sale_form.cleaned_data.get('customer_shop')
                        customer_name_manual_input = finalize_sale_form.cleaned_data.get('customer_name_manual')

                        sales_transaction_header = SalesTransaction.objects.create(
                            user=request.user,
                            customer_shop=finalize_sale_form.cleaned_data.get('customer_shop'),
                            customer_name_manual=finalize_sale_form.cleaned_data.get('customer_name_manual'),
                            payment_type=finalize_sale_form.cleaned_data['payment_type'],
                            needs_vehicle=finalize_sale_form.cleaned_data.get('needs_vehicle', False),
                            assigned_vehicle=finalize_sale_form.cleaned_data.get('assigned_vehicle') if finalize_sale_form.cleaned_data.get('needs_vehicle') else None,
                            notes=finalize_sale_form.cleaned_data.get('notes'),
                            status=SalesTransaction.SALE_STATUS_CHOICES[1][0] # PENDING_DELIVERY if vehicle, else COMPLETED
                                   if finalize_sale_form.cleaned_data.get('needs_vehicle') else SalesTransaction.SALE_STATUS_CHOICES[2][0]
                        )

                        for item_data in current_items:
                            pd_batch = ProductDetail.objects.select_for_update().get(pk=item_data['product_detail_id'])
                            stock_before_this_item_sale = pd_batch.stock # Capture before decrement

                            quantity_to_sell_for_item = Decimal(item_data['quantity_decimal'])
                            
                            if not pd_batch.decrease_stock(quantity_to_sell_for_item):
                                raise Exception(f"Stock update failed for {pd_batch.product_base.name} (Exp: {pd_batch.expirey_date}). Transaction rolled back.")

                            SalesTransactionItem.objects.create(
                                transaction=sales_transaction_header,
                                product_detail_snapshot=pd_batch,
                                quantity_sold_decimal=quantity_to_sell_for_item,
                                selling_price_per_item=Decimal(item_data['selling_price_per_item']),
                                cost_price_per_item_at_sale=Decimal(item_data['cost_price_per_item']),
                                # Snapshot fields like expiry_date_at_sale, items_per_master_unit_at_sale
                                # are now set in SalesTransactionItem's save method if product_detail_snapshot is provided
                                expiry_date_at_sale=pd_batch.expirey_date, # Explicitly set here too
                                items_per_master_unit_at_sale=pd_batch.items_per_master_unit # Explicitly set
                                # returned_quantity_decimal defaults to 0
                            )
                        
                        # After all items are saved, the grand_total_revenue is updated.
                        # We need to refresh the instance to get the latest calculated total.
                        sales_transaction_header.refresh_from_db()
                        
                        # Create a ledger entry if the payment type is CREDIT, regardless of customer type.
                        if sales_transaction_header.payment_type == 'CREDIT':
                            # Determine which customer identifier to use for the ledger
                            if customer_shop_instance:
                                # If a registered shop was selected, link to it
                                ShopFinancialTransaction.objects.create(
                                    shop=customer_shop_instance,
                                    user=request.user,
                                    source_sale=sales_transaction_header,
                                    transaction_type='CREDIT_SALE',
                                    debit_amount=sales_transaction_header.grand_total_revenue,
                                    notes=f"Credit from Sale Transaction #{sales_transaction_header.pk}"
                                )
                            elif customer_name_manual_input:
                                # If a manual name was used, create a ledger entry without a shop link
                                # and store the name in the snapshot field.
                                ShopFinancialTransaction.objects.create(
                                    shop=None, # Explicitly no shop
                                    customer_name_snapshot=customer_name_manual_input,
                                    user=request.user,
                                    source_sale=sales_transaction_header,
                                    transaction_type='CREDIT_SALE',
                                    debit_amount=sales_transaction_header.grand_total_revenue,
                                    notes=f"Credit from Sale Transaction #{sales_transaction_header.pk}"
                                )
                        
                        # SalesTransactionItem save will trigger SalesTransaction.update_grand_totals
                        messages.success(request, f"Transaction #{sales_transaction_header.pk} completed    !")
                        del request.session[current_transaction_items_session_key] # Clear the cart
                        # Redirect to receipt or back to sales page
                        return redirect('stock:all_transactions_list') 

                except ProductDetail.DoesNotExist:
                    messages.error(request, "Error: A product in the transaction no longer exists. Transaction cancelled.")
                except Exception as e:
                    messages.error(request, f"Error completing transaction: {str(e)}")
                # If any error, form will be re-rendered with errors, cart items still in session
            else: # finalize_sale_form is not valid
                messages.error(request, "Please correct the details for completing the sale.")
                # Errors in finalize_sale_form will be shown. Cart items remain in session.
                # Need to pass add_item_form again if it was cleared
                add_item_form = AddItemToSaleForm(user=request.user)


    # For GET request, load current transaction items from session
    current_transaction_items = request.session.get(current_transaction_items_session_key, [])
    current_transaction_subtotal = sum(Decimal(item['line_subtotal']) for item in current_transaction_items)


    context = {
        'add_item_form': add_item_form,
        'finalize_sale_form': finalize_sale_form,
        'current_transaction_items': current_transaction_items,
        'current_transaction_subtotal': current_transaction_subtotal,
    }
    return render(request, 'stock/sales_multiem.html', context) # New template name

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

    # Pagination (optional, but good for long lists)
    paginator = Paginator(transactions_list, 25) # Show 25 transactions per page
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
                    # --- Step 1: Process and save item returns and adjust stock ---
                    # We will loop and save each item individually to ensure stock is updated correctly.
                    # get_object_or_404 ensures we are only working on items for this transaction.
                    for form in return_formset:
                        if form.has_changed() and 'returned_quantity_decimal' in form.changed_data:
                            item_pk = form.instance.pk
                            item_instance = get_object_or_404(SalesTransactionItem, pk=item_pk, transaction=sales_transaction)
                            
                            original_returned_quantity = item_instance.returned_quantity_decimal
                            new_returned_quantity = form.cleaned_data['returned_quantity_decimal']
                            
                            stock_change_difference = new_returned_quantity - original_returned_quantity
                            
                            if stock_change_difference != Decimal('0.0'):
                                product_detail_to_update = item_instance.product_detail_snapshot
                                if stock_change_difference > 0:
                                    if not product_detail_to_update.increase_stock(stock_change_difference):
                                        raise Exception(f"Failed to increase stock for {product_detail_to_update.product_base.name}.")
                                else:
                                    if not product_detail_to_update.decrease_stock(abs(stock_change_difference)):
                                        raise Exception(f"Failed to decrease stock for {product_detail_to_update.product_base.name}.")
                            
                            # Save the new returned quantity to the item
                            item_instance.returned_quantity_decimal = new_returned_quantity
                            item_instance.save(update_fields=['returned_quantity_decimal'])

                    # --- Step 2: Recalculate and Save Grand Totals for the Transaction ---
                    # Now that all items are updated, explicitly tell the parent transaction to update itself.
                    # We call the method which will calculate and save.
                    sales_transaction.update_grand_totals()

                    # --- Step 3: Update the Payment Type and Status ---
                    # We re-fetch the transaction object to ensure we have the latest totals before proceeding.
                    final_transaction_state = SalesTransaction.objects.get(pk=sale_pk)

                    # Get the new payment type from the validated form
                    new_payment_type = payment_form.cleaned_data['payment_type']
                    final_transaction_state.payment_type = new_payment_type
                    
                    # Determine the new status based on the final item states
                    final_items = final_transaction_state.items.all()
                    total_dispatched = sum(item.dispatched_individual_items_count for item in final_items)
                    total_returned = sum(item.returned_individual_items_count for item in final_items)

                    if total_returned == 0:
                        final_transaction_state.status = 'COMPLETED'
                    elif total_returned >= total_dispatched:
                        final_transaction_state.status = 'FULLY_RETURNED'
                    else:
                        final_transaction_state.status = 'PARTIALLY_RETURNED'
                    
                    # Save the final status and payment type in one operation.
                    final_transaction_state.save(update_fields=['status', 'payment_type'])

                    # --- Step 4: Update Financial Ledger Entry ---
                    # Use the final transaction state for all ledger operations
                    existing_credit_entry = ShopFinancialTransaction.objects.filter(source_sale=final_transaction_state).first()
                    final_revenue = final_transaction_state.grand_total_revenue
                    
                    if final_transaction_state.payment_type == 'CREDIT' and final_transaction_state.customer_shop:
                        if existing_credit_entry:
                            existing_credit_entry.debit_amount = final_revenue
                            existing_credit_entry.save(update_fields=['debit_amount'])
                        else:
                            ShopFinancialTransaction.objects.create(
                                shop=final_transaction_state.customer_shop, user=request.user,
                                source_sale=final_transaction_state, transaction_type='CREDIT_SALE',
                                debit_amount=final_revenue
                            )
                    elif final_transaction_state.payment_type != 'CREDIT' and existing_credit_entry:
                        existing_credit_entry.delete()

                    messages.success(request, f"Delivery for Transaction #{final_transaction_state.pk} processed. Status: '{final_transaction_state.get_status_display()}'.")
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
        'transaction': sales_transaction,
    }
    return render(request, 'stock/process_delivery_return.html', context)






@login_required
def sales_report_view(request):
    today = timezone.localdate()
    # ... (date range setup: start_of_today_dt, end_of_today_dt, etc. - as before) ...
    # Ensure these are timezone-aware datetimes for comparison with transaction_time
    start_of_today_dt = timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.min.time()))
    end_of_today_dt = timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.max.time()))
    # ... similarly for week, month, year ...
    start_of_week_dt = timezone.make_aware(timezone.datetime.combine(today - timedelta(days=today.weekday()), timezone.datetime.min.time()))
    end_of_week_dt = timezone.make_aware(timezone.datetime.combine(start_of_week_dt.date() + timedelta(days=6), timezone.datetime.max.time()))
    start_of_month_dt = timezone.make_aware(timezone.datetime.combine(today.replace(day=1), timezone.datetime.min.time()))
    if today.month == 12:
        end_of_month_dt = timezone.make_aware(timezone.datetime.combine(today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1), timezone.datetime.max.time()))
    else:
        end_of_month_dt = timezone.make_aware(timezone.datetime.combine(today.replace(month=today.month + 1, day=1) - timedelta(days=1), timezone.datetime.max.time()))
    start_of_year_dt = timezone.make_aware(timezone.datetime.combine(today.replace(month=1, day=1), timezone.datetime.min.time()))
    end_of_year_dt = timezone.make_aware(timezone.datetime.combine(today.replace(month=12, day=31), timezone.datetime.max.time()))


    def get_transaction_stats(queryset):
        # Materialize queryset once if iterating multiple times for different properties
        materialized_qs = list(queryset) # Or queryset if only iterating once
        
        total_revenue = sum(tx.grand_total_revenue for tx in materialized_qs)
        total_profit = sum(tx.calculated_grand_profit for tx in materialized_qs)
        
        stats = {
            'transactions_count': len(materialized_qs),
            'total_grand_revenue': total_revenue or Decimal('0.00'),
            'total_grand_profit': total_profit or Decimal('0.00'),
        }
        return stats

    stats_today = get_transaction_stats(SalesTransaction.objects.filter(user=request.user, transaction_time__gte=start_of_today_dt, transaction_time__lte=end_of_today_dt))
    stats_this_week = get_transaction_stats(SalesTransaction.objects.filter(user=request.user, transaction_time__gte=start_of_week_dt, transaction_time__lte=end_of_week_dt))
    stats_this_month = get_transaction_stats(SalesTransaction.objects.filter(user=request.user, transaction_time__gte=start_of_month_dt, transaction_time__lte=end_of_month_dt))
    stats_this_year = get_transaction_stats(SalesTransaction.objects.filter(user=request.user, transaction_time__gte=start_of_year_dt, transaction_time__lte=end_of_year_dt))

    # --- Data for Charts (using SalesTransaction) ---
    daily_labels = []
    daily_revenue_data = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        start_of_day = timezone.make_aware(timezone.datetime.combine(day, timezone.datetime.min.time()))
        end_of_day = timezone.make_aware(timezone.datetime.combine(day, timezone.datetime.max.time()))
        tx_on_day = SalesTransaction.objects.filter(user=request.user, transaction_time__gte=start_of_day, transaction_time__lte=end_of_day)
        daily_revenue = sum(tx.grand_total_revenue for tx in tx_on_day) or Decimal('0.00')
        daily_labels.append(day.strftime("%b %d"))
        daily_revenue_data.append(float(daily_revenue))

    monthly_labels = []
    monthly_revenue_data = []
    for i in range(5, -1, -1):
        # ... (logic for first_day_of_target_month, last_day_of_target_month as before) ...
        target_month_date = today # Start from today for current month calculation
        for _ in range(i): # Go back i months
            first_day_of_prev_month = target_month_date.replace(day=1) - timedelta(days=1)
            target_month_date = first_day_of_prev_month
        first_day_of_target_month = target_month_date.replace(day=1)

        if first_day_of_target_month.month == 12:
            last_day_of_target_month = first_day_of_target_month.replace(year=first_day_of_target_month.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            last_day_of_target_month = first_day_of_target_month.replace(month=first_day_of_target_month.month + 1, day=1) - timedelta(days=1)
        
        start_of_target_month_dt = timezone.make_aware(timezone.datetime.combine(first_day_of_target_month, timezone.datetime.min.time()))
        end_of_target_month_dt = timezone.make_aware(timezone.datetime.combine(last_day_of_target_month, timezone.datetime.max.time()))

        tx_in_month = SalesTransaction.objects.filter(user=request.user, transaction_time__gte=start_of_target_month_dt, transaction_time__lte=end_of_target_month_dt)
        monthly_revenue = sum(tx.grand_total_revenue for tx in tx_in_month) or Decimal('0.00')
        monthly_labels.append(first_day_of_target_month.strftime("%b %Y"))
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