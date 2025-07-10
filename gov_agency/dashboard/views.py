
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from decimal import Decimal
import json 
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.contrib import messages

# Import models from your other apps
from .models import Note
from .forms import NoteForm
from stock.models import SalesTransaction,Shop
from accounts.models import CustomAccount
from claim.models import Claim

@login_required
def dashboard_view(request):
    user = request.user

    # Stock & Sales Metrics
    pending_deliveries_count = SalesTransaction.objects.filter(user=user, status='PENDING_DELIVERY').count()
    incomplete_notes_count = Note.objects.filter(user=request.user, is_completed=False).count()

    # Accounts & Financial Metrics
    # Fetch all shops and custom accounts for the user
    all_shops = Shop.objects.filter(user=user)
    all_custom_accounts = CustomAccount.objects.filter(user=user)

    # Calculate the total balance by looping in Python
    total_shop_balance = sum(shop.current_balance for shop in all_shops)
    total_custom_balance = sum(account.current_balance for account in all_custom_accounts)
    
    total_receivables = total_shop_balance + total_custom_balance
    
    # Claim Metrics
    pending_claims_count = Claim.objects.filter(user=user, status='AWAITING_PROCESSING').count()

    context = {
        'pending_deliveries_count': pending_deliveries_count,
        'total_receivables': total_receivables,
        'pending_claims_count': pending_claims_count,
        'incomplete_notes_count': incomplete_notes_count,

    }
    return render(request,'dashboard/dashboard.html', context)



@login_required
def note_list_view(request):
    """
    Displays the main page for managing all notes.
    """
    notes = Note.objects.filter(user=request.user)
    form = NoteForm()
    context = {
        'notes': notes,
        'form': form,
    }
    return render(request, 'dashboard/note_list.html', context)

@require_POST
@login_required
def create_note_view(request):
    """
    Handles the creation of a new note.
    """
    form = NoteForm(request.POST)
    if form.is_valid():
        note = form.save(commit=False)
        note.user = request.user
        note.save()
    else:
        # Handle potential errors, though less likely with a simple form
        messages.error(request, "Failed to add note.")
    return redirect('dashboard:note_list')

@require_POST
@login_required
def update_note_status_view(request, note_pk):
    """
    Handles AJAX requests to check/uncheck a note.
    """
    try:
        note = Note.objects.get(pk=note_pk, user=request.user)
        note.is_completed = not note.is_completed # Toggle the status
        note.save(update_fields=['is_completed'])
        return JsonResponse({'success': True, 'is_completed': note.is_completed})
    except Note.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Note not found.'}, status=404)

@require_POST
@login_required
def delete_note_view(request, note_pk):
    """
    Handles the deletion of a note.
    """
    try:
        note = Note.objects.get(pk=note_pk, user=request.user)
        note.delete()
        messages.success(request, "Note deleted successfully.")
    except Note.DoesNotExist:
        messages.error(request, "Note not found or you do not have permission to delete it.")
    return redirect('dashboard:note_list')

@require_POST
@login_required
def update_note_order_view(request):
    """
    Handles the new order of notes after a drag-and-drop event.
    """
    try:
        # The JS will send the new order as a JSON array of note IDs
        ordered_ids = json.loads(request.body)
        for index, note_id in enumerate(ordered_ids):
            Note.objects.filter(pk=note_id, user=request.user).update(position=index)
        return JsonResponse({'success': True, 'message': 'Order updated successfully.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
