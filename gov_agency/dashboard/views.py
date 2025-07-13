
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from decimal import Decimal
import json 
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from django.utils.timezone import make_aware, datetime
from datetime import date  # import date directly

# Import models from your other apps
from .models import Note,MonthlySalesTarget
from .forms import NoteForm,SalesTargetForm
from stock.models import SalesTransaction,Shop,ProductDetail,SalesTransactionItem
from accounts.models import CustomAccount
from claim.models import Claim

@login_required
def dashboard_view(request):
    user = request.user
    today = timezone.localdate()
    start_of_current_month = make_aware(datetime.combine(today.replace(day=1), datetime.min.time()))

    if request.method == 'POST':
        target_form = SalesTargetForm(request.POST)
        if target_form.is_valid():
            data = target_form.cleaned_data
            target_date = date(int(data['year']), int(data['month']), 1)
            MonthlySalesTarget.objects.update_or_create(
                user=user,
                month=target_date,
                defaults={'target_quantity': data['target_quantity']}
            )
            messages.success(request, f"Sales target for {target_date.strftime('%B %Y')} has been set.")
            return redirect('dashboard:main_dashboard')
    else:
        target_form = SalesTargetForm(initial={'month': today.month, 'year': today.year})

    # --- KPIs and Summaries ---
    pending_deliveries_count = SalesTransaction.objects.filter(user=user, status='PENDING_DELIVERY').count()
    incomplete_notes_count = Note.objects.filter(user=request.user, is_completed=False).count()

    stock_summary = ProductDetail.objects.filter(
        user=user, stock__gt=Decimal('0.00')
    ).values('quantity_in_packing', 'unit_of_measure').annotate(total_stock=Sum('stock')).order_by('unit_of_measure', '-total_stock')

    stock_chart_labels = []
    stock_chart_data = []
    for item in stock_summary:
        # Correct Python formatting
        label = f"{format(item['quantity_in_packing'], 'g')} {item['unit_of_measure']}"
        stock_chart_labels.append(label)
        stock_chart_data.append(float(item['total_stock']))
    
    all_shops = Shop.objects.filter(user=user)
    all_custom_accounts = CustomAccount.objects.filter(user=user)
    total_shop_balance = sum(shop.current_balance for shop in all_shops)
    total_custom_balance = sum(account.current_balance for account in all_custom_accounts)
    total_receivables = total_shop_balance + total_custom_balance
    
    pending_claims_count = Claim.objects.filter(user=user, status='AWAITING_PROCESSING').count()

    # --- Sales Target Logic ---
    current_target_obj = MonthlySalesTarget.objects.filter(user=user, month=start_of_current_month).first()
    sales_target = current_target_obj.target_quantity if current_target_obj else Decimal('1000.00')

    net_sales_aggregation = SalesTransactionItem.objects.filter(
        transaction__user=user, 
        transaction__transaction_time__gte=start_of_current_month
    ).aggregate(
        total_dispatched=Sum('quantity_sold_decimal'),
        total_returned=Sum('returned_quantity_decimal')
    )
    
    total_dispatched = net_sales_aggregation['total_dispatched'] or Decimal('0.00')
    total_returned = net_sales_aggregation['total_returned'] or Decimal('0.00')
    quantity_sold_this_month = total_dispatched - total_returned

    remaining_to_target = max(Decimal('0.00'), sales_target - quantity_sold_this_month)
    sales_target_data = [float(quantity_sold_this_month), float(remaining_to_target)]
    sales_target_labels = ['Achieved', 'Remaining']
    
    achieved_percentage = 0
    if sales_target > 0:
        achieved_percentage = round((quantity_sold_this_month / sales_target) * 100)
    
    context = {
        'pending_deliveries_count': pending_deliveries_count,
        'total_receivables': total_receivables,
        'pending_claims_count': pending_claims_count,
        'incomplete_notes_count': incomplete_notes_count,
        'stock_summary' : stock_summary,
        'stock_chart_labels': json.dumps(stock_chart_labels),
        'stock_chart_data': json.dumps(stock_chart_data),
        'sales_target': sales_target,
        'target_form': target_form,
        'quantity_sold_this_month': quantity_sold_this_month,
        'sales_target_labels': json.dumps(sales_target_labels),
        'sales_target_data': json.dumps(sales_target_data),
        'achieved_percentage': achieved_percentage,
    }
    return render(request, 'dashboard/dashboard.html', context)



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
