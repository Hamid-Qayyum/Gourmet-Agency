

from django.urls import path
from . import views

app_name = 'expense'

urlpatterns = [
    path('manage/', views.manage_expenses_view, name='manage_expenses'),
    path('update/<int:expense_pk>/', views.update_expense_view, name='update_expense'),
    path('delete/<int:expense_pk>/', views.delete_expense_view, name='delete_expense'),
    path('ajax/get_data/<int:expense_pk>/', views.ajax_get_expense_data, name='ajax_get_expense_data'),
]