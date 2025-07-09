from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.http import JsonResponse
from decimal import Decimal
from django.urls import reverse


# Import models from other apps using their app name
from stock.models import Vehicle, ProductDetail
from .models import Claim,ClaimItem
from .forms import FinalizeClaimForm,AddClaimItemForm


@login_required
def claims_hub_view(request):
    """
    This is the main navigation hub. It shows a list of vehicles and the 'Store'
    option, AND it also lists any claims that are awaiting stock processing.
    """
    user = request.user
    
    # 1. Fetch vehicles for the navigation cards
    vehicles = Vehicle.objects.filter(user=user, is_active=True).order_by('vehicle_number')
    
    # 2. Fetch claims that need action
    pending_claims = Claim.objects.filter(user=user, status='AWAITING_PROCESSING')
    
    context = {
        'vehicles': vehicles,
        'pending_claims': pending_claims,
        'can_process': pending_claims.exists(), # Flag for the "Process" button
    }
    return render(request, 'claim/claims_hub.html', context)


# 2. The Group Details View (for a specific vehicle or the store)
@login_required
def claim_group_details_view(request, vehicle_pk=None):
    """
    UPDATED: This view now lists the multi-item claims, filtered
    by the retrieval vehicle or by claims with no vehicle ("Store").
    It also provides context to its "Create" button.
    """
    user = request.user
    
    if vehicle_pk:
        grouping_object = get_object_or_404(Vehicle, pk=vehicle_pk, user=user)
        grouping_name = f"Claims for Vehicle: {grouping_object.vehicle_number}"
        base_query = Claim.objects.filter(retrieval_vehicle=grouping_object)
    else:
        grouping_object = None
        grouping_name = "Store Claims (No Vehicle)"
        base_query = Claim.objects.filter(retrieval_vehicle__isnull=True)

    claims_list = base_query.filter(user=user).select_related(
        'claimed_from_shop', 'retrieval_vehicle'
    ).prefetch_related('items__product_detail__product_base').order_by('-claim_date')

    # Pre-process items for cleaner template logic
    for claim in claims_list:
        claim.claimed_items = [item for item in claim.items.all() if item.item_type == 'CLAIMED']
        claim.exchanged_items = [item for item in claim.items.all() if item.item_type == 'EXCHANGED']

    context = {
        'claims': claims_list,
        'grouping_name': grouping_name,
        'grouping_object': grouping_object,
        'vehicle_pk': vehicle_pk, # Pass this to the template for the create link
    }
    return render(request, 'claim/claim_group_details.html', context)



# 3. View to handle the POST from the "Add Claim" modal
@login_required
def create_claim_view(request):
    session_key = f'claim_items_{request.user.id}'
    vehicle_pk = request.GET.get('vehicle_pk')
    initial_form_data = {}
    if vehicle_pk:
        initial_form_data['retrieval_vehicle'] = vehicle_pk

    finalize_form = FinalizeClaimForm(user=request.user, initial=initial_form_data)
    # Forms for the page
    claimed_form = AddClaimItemForm(user=request.user, prefix='claimed')
    exchanged_form = AddClaimItemForm(user=request.user, prefix='exchanged', for_exchange=True)

    if request.method == 'POST':
        action = request.POST.get('action')
        current_items = request.session.get(session_key, [])

        if action == 'add_claimed' or action == 'add_exchanged':
            form_prefix = 'claimed' if action == 'add_claimed' else 'exchanged'
            form_is_for_exchange = True if action == 'add_exchanged' else False
            
            form = AddClaimItemForm(request.POST, user=request.user, prefix=form_prefix, for_exchange=form_is_for_exchange)
            if form.is_valid():
                product_detail = form.cleaned_data['product_detail']
                quantity = form.cleaned_data['quantity']
                
                current_items.append({
                    'product_detail_id': product_detail.id,
                    'product_display': str(product_detail),
                    'quantity': str(quantity),
                    'cost_price': str(product_detail.price_per_item),
                    'item_type': 'CLAIMED' if action == 'add_claimed' else 'EXCHANGED',
                })
                request.session[session_key] = current_items
                messages.success(request, "Item added to claim.")
            else:
                messages.error(request, "Error adding item. Please check the form.")
            return redirect('claim:create_claim')

        elif action == 'remove_item':
            item_index = int(request.POST.get('item_index'))
            if 0 <= item_index < len(current_items):
                current_items.pop(item_index)
                request.session[session_key] = current_items
                messages.info(request, "Item removed.")
            return redirect('claim:create_claim')
            
        elif action == 'finalize_claim':
            finalize_form = FinalizeClaimForm(request.POST, user=request.user)
            if not current_items:
                messages.warning(request, "Cannot finalize an empty claim.")
                return redirect('claim:create_claim')

            if finalize_form.is_valid():
                with transaction.atomic():
                    claim_header = finalize_form.save(commit=False)
                    claim_header.user = request.user
                    claim_header.status = 'AWAITING_PROCESSING'
                    claim_header.save()
                    
                    for item_data in current_items:
                        ClaimItem.objects.create(
                            claim=claim_header,
                            product_detail_id=item_data['product_detail_id'],
                            item_type=item_data['item_type'],
                            quantity_decimal=Decimal(item_data['quantity']),
                            cost_price_at_claim=Decimal(item_data['cost_price'])
                        )
                    
                    del request.session[session_key]
                    messages.success(request, f"Claim #{claim_header.pk} created and is awaiting stock processing.")
                    return redirect('claim:claims_hub')

    context = {
        'claimed_form': claimed_form,
        'exchanged_form': exchanged_form,
        'finalize_form': finalize_form,
        'claim_items_session': request.session.get(session_key, []),
    }
    return render(request, 'claim/create_claim.html', context)



@login_required
def process_pending_claims_view(request):
    if request.method == 'POST':
        claims_to_process = Claim.objects.filter(user=request.user, status='AWAITING_PROCESSING')
        processed_count = 0
        try:
            with transaction.atomic():
                for claim in claims_to_process:
                    for item in claim.items.all():
                        product_detail = item.product_detail
                        if item.item_type == 'CLAIMED':
                            product_detail.increase_stock(item.quantity_decimal)
                        elif item.item_type == 'EXCHANGED':
                            product_detail.decrease_stock(item.quantity_decimal)
                    
                    claim.status = 'COMPLETED'
                    claim.save(update_fields=['status'])
                    processed_count += 1
            
            if processed_count > 0:
                messages.success(request, f"Successfully processed {processed_count} pending claim(s). Stock has been adjusted.")
            else:
                messages.info(request, "No pending claims were found to process.")

        except Exception as e:
            messages.error(request, f"An error occurred during processing: {e}")
            
    return redirect('claim:claims_hub')




@login_required
def delete_claim_view(request, claim_pk):
    """
    UPDATED: Deletes a Claim and its items. Now handles POST requests
    from a modal and always redirects to the main hub.
    """
    claim_to_delete = get_object_or_404(
        Claim, 
        pk=claim_pk, 
        user=request.user,
        status__in=['PENDING', 'AWAITING_PROCESSING']
    )
    
    # This view now only needs to handle POST requests from the modal's form.
    if request.method == 'POST':
        claim_pk_str = str(claim_to_delete.pk)
        claim_to_delete.delete() 
        messages.success(request, f"Claim #{claim_pk_str} has been successfully deleted.")
        # Always redirect to the main hub for simplicity and consistency.
        return redirect('claim:claims_hub')

    # If someone tries to access this URL with a GET request, just send them to the hub.
    return redirect('claim:claims_hub')