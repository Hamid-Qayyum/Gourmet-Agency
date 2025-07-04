from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.http import JsonResponse
from decimal import Decimal

# Import models from other apps using their app name
from stock.models import Vehicle, ProductDetail
from .models import Claim
from .forms import ClaimForm

# 1. The Hub View (lists vehicles and store)
@login_required
def claims_hub_view(request):
    vehicles = Vehicle.objects.filter(is_active=True, user=request.user) # Or filter by user if needed
    context = {
        'vehicles': vehicles,
    }
    return render(request, 'claim/claims_hub.html', context)



# 2. The Group Details View (for a specific vehicle or the store)
@login_required
def claim_group_details_view(request, vehicle_pk=None):
    add_claim_form = ClaimForm(user=request.user)
    
    if vehicle_pk:
        grouping_object = get_object_or_404(Vehicle, pk=vehicle_pk)
        grouping_name = f"Vehicle: {grouping_object.vehicle_number}"
        claims_list = Claim.objects.filter(retrieval_vehicle=grouping_object)
    else: # This is for "Store" claims
        grouping_object = None
        grouping_name = "Store Claims (No Vehicle)"
        claims_list = Claim.objects.filter(retrieval_vehicle__isnull=True)

    # Further filter by the user who filed the claim
    claims_list = claims_list.filter(user=request.user).select_related(
        'product_detail__product_base', 'claimed_from_shop'
    ).order_by('-claim_date')

    context = {
        'add_form': add_claim_form,
        'claims': claims_list,
        'grouping_name': grouping_name,
        'grouping_object': grouping_object,
        # This flag tells the add form's action where to redirect
        'vehicle_pk_for_form': vehicle_pk if vehicle_pk else 0,
    }
    return render(request, 'claim/claim_group_details.html', context)


# 3. View to handle the POST from the "Add Claim" modal
@login_required
def create_claim_view(request):
    if request.method == 'POST':
        form = ClaimForm(request.POST, user=request.user)
        if form.is_valid():
            product_detail = form.cleaned_data['product_detail']
            quantity_claimed = form.cleaned_data['quantity_claimed_decimal']
            
            try:
                with transaction.atomic():
                    # Re-fetch with lock to prevent race conditions
                    pd_to_claim = ProductDetail.objects.select_for_update().get(pk=product_detail.pk)
                    
                    # Decrease stock first
                    if not pd_to_claim.decrease_stock(quantity_claimed):
                        raise Exception("Not enough stock for this claim (should be caught by form validation).")
                    
                    # If stock decrease is successful, save the claim
                    claim = form.save(commit=False)
                    claim.user = request.user
                    claim.save()
                    messages.success(request, f"Claim for {quantity_claimed} of {product_detail.product_base.name} recorded successfully.")
            except Exception as e:
                messages.error(request, f"Error creating claim: {str(e)}")
        else:
            # Create a string of errors to pass back in a message
            error_string = ". ".join([f"{field}: {', '.join(errors)}" for field, errors in form.errors.items()])
            messages.error(request, f"Failed to create claim. {error_string}")
        
        # Redirect back to the group details page it came from
        vehicle_pk = request.POST.get('vehicle_pk_for_redirect')
        if vehicle_pk and vehicle_pk != '0':
            return redirect('claim:claims_by_vehicle', vehicle_pk=vehicle_pk)
        else:
            return redirect('claim:claims_by_store')
            
    # GET requests to this URL are not expected
    return redirect('claim:claims_hub')



@login_required
def update_claim_view(request, claim_pk):
    """Handles the POST submission from the 'Update Claim' modal."""
    claim_instance = get_object_or_404(Claim, pk=claim_pk, user=request.user)
    # Store original values before any changes
    original_product_detail = claim_instance.product_detail
    original_quantity = claim_instance.quantity_claimed_decimal

    if request.method == 'POST':
        form = ClaimForm(request.POST, instance=claim_instance, user=request.user)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Get the new data from the form
                    new_product_detail = form.cleaned_data['product_detail']
                    new_quantity = form.cleaned_data['quantity_claimed_decimal']
                    
                    # --- Stock Adjustment Logic ---
                    # Case 1: The product batch itself was changed.
                    if original_product_detail.pk != new_product_detail.pk:
                        # Add stock back to the OLD product batch
                        original_product_detail.increase_stock(original_quantity)
                        # Decrease stock from the NEW product batch
                        if not new_product_detail.decrease_stock(new_quantity):
                            raise Exception(f"Not enough stock for the newly selected product batch '{new_product_detail}'.")
                    # Case 2: Product is the same, but quantity changed.
                    elif original_quantity != new_quantity:
                        quantity_difference = new_quantity - original_quantity
                        if quantity_difference > 0: # Claim amount increased
                            if not original_product_detail.decrease_stock(quantity_difference):
                                raise Exception("Not enough stock for the increased claim amount.")
                        elif quantity_difference < 0: # Claim amount decreased
                            original_product_detail.increase_stock(abs(quantity_difference))
                    
                    # If we reach here, all stock adjustments were successful. Save the form.
                    form.save()
                    messages.success(request, f"Claim #{claim_instance.pk} updated successfully.")
            except Exception as e:
                messages.error(request, f"Error updating claim: {str(e)}")
        else:
            error_string = ". ".join([f"{field}: {', '.join(errors)}" for field, errors in form.errors.items()])
            messages.error(request, f"Failed to update claim. {error_string}")

        # Redirect back to the group details page it came from
        vehicle_pk = request.POST.get('vehicle_pk_for_redirect')
        if vehicle_pk and vehicle_pk != '0':
            return redirect('claim:claims_by_vehicle', vehicle_pk=vehicle_pk)
        else:
            return redirect('claim:claims_by_store')

    # GET requests to this URL are not expected
    return redirect('claim:claims_hub')


@login_required
def delete_claim_view(request, claim_pk):
    """Handles the POST submission from the 'Delete Claim' confirmation modal."""
    claim_instance = get_object_or_404(Claim, pk=claim_pk, user=request.user)
    
    if request.method == 'POST':
        quantity_to_return = claim_instance.quantity_claimed_decimal
        product_detail = claim_instance.product_detail
        
        try:
            with transaction.atomic():
                # Add the stock back to inventory first
                if not product_detail.increase_stock(quantity_to_return):
                    raise Exception("Failed to return stock to inventory.")
                
                # Then delete the claim record
                claim_instance.delete()
                messages.success(request, f"Claim #{claim_pk} deleted and stock has been returned to inventory.")
        except Exception as e:
            messages.error(request, f"Error deleting claim: {str(e)}")
        
        # Redirect back to the group details page it came from
        vehicle_pk = request.POST.get('vehicle_pk_for_redirect')
        if vehicle_pk and vehicle_pk != '0':
            return redirect('claim:claims_by_vehicle', vehicle_pk=vehicle_pk)
        else:
            return redirect('claim:claims_by_store')

    return redirect('claim:claims_hub')


@login_required
def ajax_get_claim_data(request, claim_pk):
    """Serves data for a specific claim to populate the update modal via JS."""
    try:
        claim = get_object_or_404(Claim, pk=claim_pk, user=request.user)
        data = {
            'pk': claim.pk,
            'product_detail': claim.product_detail.pk,
            'quantity_claimed_decimal': str(claim.quantity_claimed_decimal),
            'claimed_from_shop': claim.claimed_from_shop.pk if claim.claimed_from_shop else "",
            'retrieval_vehicle': claim.retrieval_vehicle.pk if claim.retrieval_vehicle else "",
            'reason': claim.reason or "",
        }
        return JsonResponse({'success': True, 'data': data})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)