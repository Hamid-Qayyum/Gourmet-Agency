from django.urls import path,re_path
from . import views

app_name = 'accounts'

urlpatterns = [
    # The main hub page
    path('transactions-hub/', views.transactions_hub_view, name='transactions_hub'),
    path('vehicle-ledger/<int:vehicle_pk>/', views.vehicle_ledger_summary_view, name='vehicle_ledger_summary'),
    path('store-ledger/', views.store_ledger_summary_view, name='store_ledger_summary'),
    re_path(r'^manual-customer-ledger/(?P<customer_name>.+)/$', views.manual_customer_ledger_view, name='manual_customer_ledger'),

    path('shop-ledger/<int:shop_pk>/', views.shop_ledger_view, name='shop_ledger'),
    path('financial-transaction/edit/<int:transaction_pk>/', views.edit_financial_transaction_view, name='edit_financial_transaction'),
    path('financial-transaction/delete/<int:transaction_pk>/', views.delete_financial_transaction_view, name='delete_financial_transaction'),
    path('financial-transaction/ajax/get-data/<int:transaction_pk>/', views.ajax_get_financial_transaction_data, name='ajax_get_financial_transaction_data'),
    

    path('custom/', views.custom_account_hub_view, name='custom_account_hub'),
    path('custom/update/<int:account_pk>/', views.update_custom_account_card_view, name='update_custom_account'),
    path('custom/delete/<int:account_pk>/', views.delete_custom_account_card_view, name='delete_custom_account'),
    
    path('custom/ledger/<int:account_pk>/', views.custom_account_ledger_view, name='custom_account_ledger'),
    path('custom-accounts/update/<int:pk>/', views.update_custom_transaction_view, name='update_custom_transaction'),
    path('custom-accounts/delete/<int:pk>/', views.delete_custom_transaction_view, name='delete_custom_transaction'),
    path('custom-accounts/ajax/get-data/<int:pk>/', views.ajax_get_custom_transaction_data, name='ajax_get_custom_transaction_data'),

    # --- NEW URLS FOR DAILY SUMMARY ---
    path('summary/', views.daily_summary_list_view, name='daily_summary_list'),
    path('summary/generate/', views.generate_today_summary_view, name='generate_today_summary'),
    path('summary/delete/<int:summary_pk>/', views.delete_daily_summary_view, name='delete_daily_summary'),
]