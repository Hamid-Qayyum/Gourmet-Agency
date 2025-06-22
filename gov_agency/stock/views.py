from django.shortcuts import render,redirect, get_object_or_404
from .forms import RegisterForm, AddProductForm, ProductDetailForm, SaleForm, VehicleForm, ShopForm,ProcessReturnForm
from django.contrib.auth import login, logout
from .utils import authenticate 
from django.contrib.auth.models import User 
from django.contrib.auth.decorators import login_required
from .models import AddProduct, ProductDetail,Sale, Vehicle, Shop
from django.contrib import messages
from django.db.models  import Q
from django.db import transaction # For atomic operations
from django.http import JsonResponse
from decimal import Decimal
from django.db.models import Sum,Count, F, ExpressionWrapper, fields, DecimalField
from django.utils import timezone
from datetime import timedelta, date
import json 
from django.db.models.functions import TruncMonth, TruncDay






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
    user_has_base_products =  AddProduct.objects.filter(user=request.user).exists()
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

#  sales views...................................................................................................................
@login_required
def sales_processing_view(request):
    form = SaleForm(user=request.user) # Pass user to filter choices
    form_had_errors = False

    if request.method == 'POST':
        form = SaleForm(request.POST, user=request.user) # Pass user for validation context
        if form.is_valid():
            product_detail_batch = form.cleaned_data['product_detail_batch']
            quantity_sold_decimal_input = form.cleaned_data['quantity_to_sell']
            selling_price_item = form.cleaned_data['selling_price_per_item']
            customer_shop_instance = form.cleaned_data.get('customer_shop')
            customer_name_manual_input = form.cleaned_data.get('customer_name_manual')
            payment_type_input = form.cleaned_data['payment_type']
            needs_vehicle_input = form.cleaned_data.get('needs_vehicle', False)
            assigned_vehicle_instance = form.cleaned_data.get('assigned_vehicle')

            # Determine initial sale status
            if needs_vehicle_input and assigned_vehicle_instance:
                initial_sale_status = Sale.SALE_STATUS_CHOICES[0][0] # 'PENDING_DELIVERY'
            else:
                initial_sale_status = Sale.SALE_STATUS_CHOICES[1][0] # 'COMPLETED'
                if payment_type_input == 'CREDIT': # If credit and no vehicle, maybe still 'Pending Payment' or similar
                    pass # You might want a 'PENDING_PAYMENT' status if no vehicle but on credit. For now, 'COMPLETED'.


            try:
                with transaction.atomic():
                    pd_to_sell = ProductDetail.objects.select_for_update().get(pk=product_detail_batch.pk)
                    stock_before_this_sale = pd_to_sell.stock

                    # Decrease stock using the method in ProductDetail
                    # This method now takes the decimal quantity (e.g., 1.1)
                    if not pd_to_sell.decrease_stock(quantity_sold_decimal_input):
                        form.add_error('quantity_to_sell', f"Stock update failed. Available: {pd_to_sell.stock} (represents {pd_to_sell.total_items_in_stock} items).")
                        raise Exception("Stock update failed during transaction.")
                    
                    # Create the Sale record
                    new_sale = Sale.objects.create(
                        user=request.user,
                        product_detail_snapshot=pd_to_sell,
                        customer_shop=customer_shop_instance,
                        customer_name_manual=customer_name_manual_input,
                        # Snapshot fields are filled by Sale model's save() method
                        stock_before_sale=stock_before_this_sale, # Explicitly pass for accuracy
                        # Other snapshot fields (expiry, items_per_master, cost) will be set by Sale.save()
                        quantity_sold_decimal=quantity_sold_decimal_input,
                        selling_price_per_item=selling_price_item,
                        payment_type=payment_type_input,
                        needs_vehicle=needs_vehicle_input,
                        assigned_vehicle=assigned_vehicle_instance if needs_vehicle_input else None,
                        status=initial_sale_status
                        # total_revenue_dispatch, total_cost_dispatch are calculated in Sale.save()
                    )
                    messages.success(request, f"Sale #{new_sale.id} recorded: {quantity_sold_decimal_input} of {pd_to_sell.product_base.name}. Status: {new_sale.get_status_display()}")
                    return redirect('stock:sales')
            except Exception as e:
                messages.error(request, f"An error occurred while processing the sale: {str(e)}")
                form_had_errors = True # To reopen modal with existing data and errors
        else:
            messages.error(request, "Please correct the errors in the sale form.")
            form_had_errors = True
    
    recent_sales = Sale.objects.filter(user=request.user).select_related(
        'product_detail_snapshot__product_base', 'customer_shop', 'assigned_vehicle'
    ).order_by('-sale_time')[:20]

    context = {
        'sale_form': form,
        'recent_sales': recent_sales,
        'form_had_errors_for_sale_modal': form_had_errors,
    }
    return render(request, 'stock/sales.html', context)

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
def pending_deliveries_view(request):
    # Fetch sales that are pending delivery and assigned to a vehicle,
    # potentially further filterable by vehicles the current user manages if that's a feature.
    # For now, let's assume user sees all their sales pending delivery.
    pending_sales = Sale.objects.filter(
        user=request.user, # Sales made by this user
        status=Sale.SALE_STATUS_CHOICES[0][0] # 'PENDING_DELIVERY'
    ).select_related(
        'product_detail_snapshot__product_base', 
        'customer_shop', 
        'assigned_vehicle'
    ).order_by('sale_time')

    context = {
        'pending_sales': pending_sales,
    }
    return render(request, 'stock/pending_deliveries.html', context)


@login_required
def process_delivery_return_view(request, sale_pk):
    sale_instance = get_object_or_404(
        Sale, 
        pk=sale_pk, 
        user=request.user, 
        status=Sale.SALE_STATUS_CHOICES[0][0] # 'PENDING_DELIVERY'
    )
    # Ensure the ProductDetail still exists, though it's protected on Sale model
    product_detail_batch = sale_instance.product_detail_snapshot 

    if request.method == 'POST':
        form = ProcessReturnForm(request.POST, sale_instance=sale_instance)
        if form.is_valid():
            returned_quantity_decimal = form.cleaned_data.get('returned_stock_decimal', Decimal('0.0'))

            try:
                with transaction.atomic():
                    # 1. Update Sale record
                    sale_instance.returned_stock_decimal = returned_quantity_decimal
                    
                    # Determine new status
                    if returned_quantity_decimal is None or returned_quantity_decimal == Decimal('0.0'):
                        sale_instance.status = Sale.SALE_STATUS_CHOICES[1][0] # 'COMPLETED'
                    elif returned_quantity_decimal >= sale_instance.quantity_sold_decimal:
                        # This case should be caught by form validation, but as a safeguard
                        # If all items are returned
                        sale_instance.status = Sale.SALE_STATUS_CHOICES[3][0] # 'FULLY_RETURNED'
                        # Ensure returned_quantity_decimal doesn't exceed quantity_sold_decimal
                        sale_instance.returned_stock_decimal = sale_instance.quantity_sold_decimal
                    else:
                        sale_instance.status = Sale.SALE_STATUS_CHOICES[2][0] # 'PARTIALLY_RETURNED'
                    
                    sale_instance.save() # This will also recalculate final_profit via properties if you display it

                    # 2. Add returned stock back to ProductDetail inventory
                    if returned_quantity_decimal and returned_quantity_decimal > Decimal('0.0'):
                        # Re-fetch with select_for_update if high concurrency is expected
                        # For simplicity here, we use the instance we have.
                        product_detail_to_update = ProductDetail.objects.get(pk=product_detail_batch.pk)
                        if not product_detail_to_update.increase_stock(returned_quantity_decimal):
                            raise Exception("Failed to add returned stock back to inventory.")
                    
                    messages.success(request, f"Delivery for Sale #{sale_instance.pk} processed. Status: {sale_instance.get_status_display()}.")
                    return redirect('stock:pending_deliveries')
            except Exception as e:
                messages.error(request, f"Error processing delivery/return: {str(e)}")
                # Form will be re-rendered with original data due to no redirect yet
        else:
            messages.error(request, "Please correct the errors in the return form.")
            # Form with errors will be passed to template
    else:
        form = ProcessReturnForm(sale_instance=sale_instance, initial={'returned_stock_decimal': Decimal('0.0')})

    context = {
        'form': form,
        'sale': sale_instance,
        'product_detail': product_detail_batch,
    }
    return render(request, 'stock/process_delivery_return.html', context)

@login_required
def sales_report_view(request):
    # --- Date Range Setup ---
    today = timezone.localdate() # Use localdate for date comparisons
    
    # Today's Sales
    start_of_today = timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.min.time()))
    end_of_today = timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.max.time()))

    # This Week's Sales (assuming week starts on Monday)
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    start_of_week_dt = timezone.make_aware(timezone.datetime.combine(start_of_week, timezone.datetime.min.time()))
    end_of_week_dt = timezone.make_aware(timezone.datetime.combine(end_of_week, timezone.datetime.max.time()))

    # This Month's Sales
    start_of_month = today.replace(day=1)
    # To get end of month, go to first day of next month and subtract one day
    if today.month == 12:
        end_of_month = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        end_of_month = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
    start_of_month_dt = timezone.make_aware(timezone.datetime.combine(start_of_month, timezone.datetime.min.time()))
    end_of_month_dt = timezone.make_aware(timezone.datetime.combine(end_of_month, timezone.datetime.max.time()))
    
    # This Year's Sales
    start_of_year = today.replace(month=1, day=1)
    end_of_year = today.replace(month=12, day=31)
    start_of_year_dt = timezone.make_aware(timezone.datetime.combine(start_of_year, timezone.datetime.min.time()))
    end_of_year_dt = timezone.make_aware(timezone.datetime.combine(end_of_year, timezone.datetime.max.time()))

    # --- Queries (scoped to the logged-in user) ---
    # We need to calculate profit per sale item if not stored directly or use the final_profit logic.
    # The Sale model's `final_profit` property calculates `final_total_revenue - final_total_cost`.
    # `final_total_revenue` = `actual_sold_individual_items_count * selling_price_per_item`
    # `final_total_cost` = `actual_sold_individual_items_count * cost_price_per_item_at_sale`
    # So, profit = `actual_sold_individual_items_count * (selling_price_per_item - cost_price_per_item_at_sale)`

    # To aggregate profit, we need to calculate it at the database level if possible or iterate.
    # For database-level aggregation, we need an expression for individual items sold * profit_margin_per_item.

    # Let's define an expression for the profit margin per item
    profit_margin_per_item_expr = F('selling_price_per_item') - F('cost_price_per_item_at_sale')
    
    # We need an expression for actual items sold (dispatched - returned)
    # This is complex with your decimal stock. Let's rely on calculated properties for individual sales
    # and iterate for aggregate profit if direct DB aggregation is too complex for now.

    # For revenue and cost, we can use the stored `total_revenue_dispatch` and `total_cost_dispatch`
    # but for *final* figures considering returns, we need to use logic similar to the properties.

    def get_sales_stats(queryset):
        # Calculate final revenue and profit by iterating if direct aggregation of properties is hard
        total_final_revenue = Decimal('0.00')
        total_final_profit = Decimal('0.00')
        for sale in queryset:
            total_final_revenue += sale.final_total_revenue # Uses the property
            total_final_profit += sale.final_profit       # Uses the property
        
        stats = queryset.aggregate(
            sales_count=Count('id'),
            # total_revenue_dispatch=Sum('total_revenue_dispatch'), # Revenue from initial dispatch
            # total_cost_dispatch=Sum('total_cost_dispatch')      # Cost from initial dispatch
        )
        stats['total_final_revenue'] = total_final_revenue or Decimal('0.00')
        stats['total_final_profit'] = total_final_profit or Decimal('0.00')
        stats['sales_count'] = stats['sales_count'] or 0
        return stats

    sales_today_qs = Sale.objects.filter(user=request.user, sale_time__gte=start_of_today, sale_time__lte=end_of_today)
    stats_today = get_sales_stats(sales_today_qs)

    sales_this_week_qs = Sale.objects.filter(user=request.user, sale_time__gte=start_of_week_dt, sale_time__lte=end_of_week_dt)
    stats_this_week = get_sales_stats(sales_this_week_qs)

    sales_this_month_qs = Sale.objects.filter(user=request.user, sale_time__gte=start_of_month_dt, sale_time__lte=end_of_month_dt)
    stats_this_month = get_sales_stats(sales_this_month_qs)

    sales_this_year_qs = Sale.objects.filter(user=request.user, sale_time__gte=start_of_year_dt, sale_time__lte=end_of_year_dt)
    stats_this_year = get_sales_stats(sales_this_year_qs)
    
    # You could also add a custom date range filter here using GET parameters

    last_7_days_sales_data = []
    daily_labels = []
    daily_revenue_data = []
    for i in range(6, -1, -1): # From 6 days ago to today
        day = today - timedelta(days=i)
        start_of_day = timezone.make_aware(timezone.datetime.combine(day, timezone.datetime.min.time()))
        end_of_day = timezone.make_aware(timezone.datetime.combine(day, timezone.datetime.max.time()))
        
        sales_on_day = Sale.objects.filter(user=request.user, sale_time__gte=start_of_day, sale_time__lte=end_of_day)
        daily_revenue = sum(s.final_total_revenue for s in sales_on_day) or Decimal('0.00')
        
        daily_labels.append(day.strftime("%b %d")) # e.g., "Jun 07"
        daily_revenue_data.append(float(daily_revenue)) # Chart.js usually prefers floats

    # 2. Monthly Sales Revenue for the Last 6 Months
    monthly_labels = []
    monthly_revenue_data = []
    for i in range(5, -1, -1): # From 5 months ago to this month
        # Calculate the first day of the target month
        target_month_date = today - timedelta(days=i * 30) # Approximate
        first_day_of_target_month = target_month_date.replace(day=1)
        
        # Calculate the last day of the target month
        if first_day_of_target_month.month == 12:
            last_day_of_target_month = first_day_of_target_month.replace(year=first_day_of_target_month.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            last_day_of_target_month = first_day_of_target_month.replace(month=first_day_of_target_month.month + 1, day=1) - timedelta(days=1)

        start_of_target_month_dt = timezone.make_aware(timezone.datetime.combine(first_day_of_target_month, timezone.datetime.min.time()))
        end_of_target_month_dt = timezone.make_aware(timezone.datetime.combine(last_day_of_target_month, timezone.datetime.max.time()))

        sales_in_month = Sale.objects.filter(user=request.user, sale_time__gte=start_of_target_month_dt, sale_time__lte=end_of_target_month_dt)
        monthly_revenue = sum(s.final_total_revenue for s in sales_in_month) or Decimal('0.00')

        monthly_labels.append(first_day_of_target_month.strftime("%b %Y")) # e.g., "Jun 2025"
        monthly_revenue_data.append(float(monthly_revenue))

    context = {
        'stats_today': stats_today,
        'stats_this_week': stats_this_week,
        'stats_this_month': stats_this_month,
        'stats_this_year': stats_this_year,
        'report_generation_time': timezone.now(),
        
        # Chart data (ensure it's JSON serializable)
        'daily_chart_labels': json.dumps(daily_labels),
        'daily_chart_revenue': json.dumps(daily_revenue_data),
        'monthly_chart_labels': json.dumps(monthly_labels),
        'monthly_chart_revenue': json.dumps(monthly_revenue_data),
    }
    return render(request, 'stock/sales_report.html', context)


# Recepit View ...................................

@login_required
def sale_receipt_view(request, sale_pk):
    # Fetch the sale, ensuring it belongs to the current user who processed it
    # Or, if admins can print any receipt, adjust permission checks.
    sale_instance = get_object_or_404(
        Sale.objects.select_related(
            'user', # User who processed the sale
            'product_detail_snapshot__product_base', # Product name
            'customer_shop', # Shop details
            'assigned_vehicle' # Vehicle details
        ),
        pk=sale_pk,
        user=request.user # Or remove this if access is broader
    )

    # We need to calculate the number of individual items sold based on quantity_sold_decimal
    # This logic should be consistent with how it's done in the Sale model or its properties
    items_per_mu = sale_instance.items_per_master_unit_at_sale
    dispatched_items_count = sale_instance.dispatched_individual_items_count
    returned_items_count = sale_instance.returned_individual_items_count
    actual_sold_items_count = sale_instance.actual_sold_individual_items_count


    context = {
        'sale': sale_instance,
        'dispatched_items_count': dispatched_items_count,
        'returned_items_count': returned_items_count,
        'actual_sold_items_count': actual_sold_items_count,
        # You can add more company details here from settings or another model
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
    # Assuming shops are user-specific. If global, remove user filter.
    # Or if only admins see all shops, add permission checks.
    shops = Shop.objects.filter(user=request.user, is_active=True).order_by('name')
    # If you want to show all shops regardless of current user:
    # shops = Shop.objects.filter(is_active=True).order_by('name')
    
    context = {
        'shops': shops,
    }
    return render(request, 'stock/list_shops_for_sales.html', context)

@login_required
def shop_purchase_history_view(request, shop_pk):
    # Ensure the shop exists and (optionally) belongs to the user or is accessible
    shop = get_object_or_404(Shop, pk=shop_pk) 
    # Add user=request.user if shops are strictly user-scoped for viewing history too:
    # shop = get_object_or_404(Shop, pk=shop_pk, user=request.user)


    # Fetch sales associated with this shop, also made by the current user (if sales are user-scoped)
    shop_sales = Sale.objects.filter(
        customer_shop=shop,
        user=request.user # Ensures user only sees sales they processed for this shop
    ).select_related(
        'product_detail_snapshot__product_base', 
        'assigned_vehicle'
    ).order_by('-sale_time')

    # Calculate total sales value for this shop by this user
    shop_total_sales_value = shop_sales.aggregate(total_value=Sum('total_revenue_dispatch'))['total_value'] or Decimal('0.00')
    shop_total_profit = sum(sale.final_profit for sale in shop_sales if sale.final_profit is not None)


    context = {
        'shop': shop,
        'shop_sales': shop_sales,
        'shop_total_sales_value': shop_total_sales_value,
        'shop_total_profit': shop_total_profit,
    }
    return render(request, 'stock/shop_purchase_history.html', context)