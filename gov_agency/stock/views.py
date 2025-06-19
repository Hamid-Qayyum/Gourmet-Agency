from django.shortcuts import render,redirect, get_object_or_404
from .forms import RegisterForm, AddProductForm, ProductDetailForm, SaleForm, VehicleForm, ShopForm
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





# Create your views here.

# login view.........
def user_login(request):
    print("inside login")
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
        print(form)
        if form.is_valid():
            form.save()
            messages.success(request, f"Details for '{instance .product_base.name}' updated successfully!")
            query = request.GET.get('q_after_update', '')
            redirect_url = redirect('stock:add_product_details').url
            if query: redirect_url += f'?q={query}'
            return redirect(redirect_url)
        else:
            print("Errors:", form.errors.as_data())
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
                    return redirect('stock:sales_page')
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



def sales(request):
    form = SaleForm(user=request.user)
    form_had_errors = False
    if request.method == 'POST':
        form = SaleForm(request.POST, user=request.user)
        if form.is_valid():
            product_detail_batch = form.cleaned_data['product_detail_batch']
            quantity_sold = form.cleaned_data['quantity_items_to_sell']
            selling_price = form.cleaned_data['selling_price_per_item']
            customer_name = form.cleaned_data.get('name_of_customer') # get() in case it's not submitted

            # --- Critical Stock and Sale Processing ---
            try:
                with transaction.atomic(): # Ensures all database operations succeed or none do
                    # 1. Re-fetch the ProductDetail instance within the transaction to ensure atomicity
                    #    and to get the most current stock before attempting to decrease it.
                    #    Lock the row for update if your database supports it (e.g., select_for_update())
                    #    to prevent race conditions if multiple sales happen concurrently for the same item.
                    #    For SQLite, select_for_update() might not have full effect but good practice.
                    pd_to_sell = ProductDetail.objects.select_for_update().get(pk=product_detail_batch.pk)
                    # Snapshot current stock before attempting to decrease
                    stock_before_this_sale = pd_to_sell.stock 
                    # 2. Decrease stock using the method in ProductDetail

                    if not pd_to_sell.decrease_stock(quantity_sold):
                        form.add_error('quantity_items_to_sell', f"Stock update failed. Available items: {pd_to_sell.total_items_in_stock}.")
                        raise Exception("Stock update failed during transaction.")

                    # 3. Create the Sale record
                    Sale.objects.create(
                        user=request.user,
                        product_detail_snapshot=pd_to_sell, # The instance whose stock was just updated
                        name_of_customer=customer_name,
                        stock_before_sale=stock_before_this_sale, # Pass the stock value before deduction
                        expiry_date_at_sale=pd_to_sell.expirey_date, # Copied from current state
                        items_per_master_unit_at_sale=pd_to_sell.items_per_master_unit, # Copied
                        cost_price_per_item_at_sale=pd_to_sell.price_per_item, # Copied (your cost)
                        quantity_items_sold=quantity_sold,
                        selling_price_per_item=selling_price
                        # total_revenue, total_cost are calculated in Sale.save()
                    )
                    messages.success(request, f"Sale recorded for {quantity_sold} x {pd_to_sell.product_base.name}.")
                    return redirect('stock:sales')

            except ProductDetail.DoesNotExist:
                messages.error(request, "Selected product batch could not be found. Please try again.")
                form_had_errors = True
            except Exception as e:
                print("Errors:", e)
                messages.error(request, f"An error occurred while processing the sale: {str(e)}")
                form_had_errors = True
        else:
            messages.error(request, "Please correct the errors in the sale form.")
            form_had_errors = True

    # List recent sales made by this user for display
    recent_sales = Sale.objects.filter(user=request.user).select_related(
        'product_detail_snapshot__product_base'
    ).order_by('-sale_time')[:500] # Show last 20 sales for example

    context = {
        'sale_form': form,
        'recent_sales': recent_sales,
        'form_had_errors_for_sale_modal': form_had_errors,
    }
    return render(request, 'stock/sales.html', context)


# AJAX endpoint to get details for a selected product_detail_batch
# This is used by JavaScript to auto-fill parts of the SaleForm
@login_required
def ajax_get_batch_details_for_sale(request, pk):
    try:
        detail = get_object_or_404(ProductDetail, pk=pk, user=request.user)
        # You MUST ensure total_items_in_stock and display_stock are accurate properties in your ProductDetail model.
        data = {
            'pk': detail.pk,
            'product_name_display': str(detail.product_base.name),
            'expiry_date_display': detail.expirey_date.strftime('%Y-%m-%d'),
            'current_stock_master_units_display': detail.stock, # e.g., "2.5" (representing cartons)
            'current_stock_master_units_unit': detail.product_base.name + "s", # e.g., "Cartons" - better to have a unit field on ProductDetail itself
            'total_individual_items_available': detail.total_items_in_stock, # e.g., 25 (individual bottles)
            'cost_price_per_item': str(detail.price_per_item), # Your cost
            # Suggest a selling price, e.g., 20% markup on your cost price.
            # User can override this in the form.
            'suggested_selling_price_per_item': str(round(detail.price_per_item * Decimal('1.20'), 2)),
        }
        return JsonResponse({'success': True, 'data': data})
    except ProductDetail.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Product batch not found or not authorized.'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'An error occurred: {str(e)}'}, status=500)
    


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