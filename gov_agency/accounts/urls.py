from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    # The main hub page
    path('transactions-hub/', views.transactions_hub_view, name='transactions_hub'),
    path('vehicle-ledger/<int:vehicle_pk>/', views.vehicle_ledger_summary_view, name='vehicle_ledger_summary'),
    path('store-ledger/', views.store_ledger_summary_view, name='store_ledger_summary'),


    path('shop-ledger/<int:shop_pk>/', views.shop_ledger_view, name='shop_ledger'),
    path('financial-transaction/edit/<int:transaction_pk>/', views.edit_financial_transaction_view, name='edit_financial_transaction'),
    path('financial-transaction/delete/<int:transaction_pk>/', views.delete_financial_transaction_view, name='delete_financial_transaction'),
    path('financial-transaction/ajax/get-data/<int:transaction_pk>/', views.ajax_get_financial_transaction_data, name='ajax_get_financial_transaction_data'),
    
]