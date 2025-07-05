from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Expense
from .forms import ExpenseForm
from django.utils import timezone
from datetime import date
from django.db.models import Sum
from django.http import JsonResponse








@login_required
def manage_expenses_view(request):
    """
    A single, robust view to list, add, and handle errors for expenses.
    """
    # This view now handles both GET and POST for adding expenses.
    if request.method == 'POST':
        # This POST request is for CREATING a new expense.
        # The update/delete actions will have their own views.
        form = ExpenseForm(request.POST)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.user = request.user
            expense.save()
            messages.success(request, f"Expense '{expense.title}' recorded successfully!")
            return redirect('expense:manage_expenses')
        else:
            # If the form is invalid, we fall through to the GET response below,
            # passing the form with its errors to the template.
            messages.error(request, "Please correct the errors in the form.")
            add_form_with_errors = form
    else:
        # For a GET request, create a fresh, unbound form.
        add_form_with_errors = ExpenseForm(initial={'expense_date': timezone.now()})

    # --- Daily Total Expense Calculation (for the new feature) ---
    today = timezone.localdate()
    daily_total = Expense.objects.filter(
        user=request.user, 
        expense_date__date=today
    ).aggregate(total=Sum('amount'))['total'] or 0.00
    
    # --- Data for the main list ---
    expenses_list = Expense.objects.filter(user=request.user)

    context = {
        'add_form': add_form_with_errors,
        'expenses': expenses_list,
        'daily_total_expense': daily_total,
        'today_date': today,
        # This flag tells the template whether to auto-open the modal.
        'form_had_errors': 'add_form' in locals() and add_form_with_errors.errors,
    }
    return render(request, 'expense/manage_expenses.html', context)



@login_required
def update_expense_view(request, expense_pk):
    """
    Handles the update of an existing expense.
    """
    expense_instance = get_object_or_404(Expense, pk=expense_pk, user=request.user)
    if request.method == 'POST':
        form = ExpenseForm(request.POST, instance=expense_instance)
        if form.is_valid():
            form.save()
            messages.success(request, f"Expense '{expense_instance.title}' updated successfully!")
        else:
            error_string = ". ".join([f"{field}: {', '.join(errors)}" for field, errors in form.errors.items()])
            messages.error(request, f"Failed to update expense. {error_string}")
    return redirect('expense:manage_expenses')


@login_required
def delete_expense_view(request, expense_pk):
    """
    Handles the deletion of an expense.
    """
    expense_instance = get_object_or_404(Expense, pk=expense_pk, user=request.user)
    if request.method == 'POST':
        expense_title = expense_instance.title
        expense_instance.delete()
        messages.error(request, f"Expense '{expense_title}' deleted successfully.")
    return redirect('expense:manage_expenses')


@login_required
def ajax_get_expense_data(request, expense_pk):
    """
    Serves data for a specific expense to populate the update modal via JS.
    """
    try:
        expense = get_object_or_404(Expense, pk=expense_pk, user=request.user)
        data = {
            'pk': expense.pk,
            'title': expense.title,
            'amount': str(expense.amount),
            # Format date for datetime-local input
            'expense_date': expense.expense_date.strftime('%Y-%m-%dT%H:%M'),
            'description': expense.description or "",
        }
        return JsonResponse({'success': True, 'data': data})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)