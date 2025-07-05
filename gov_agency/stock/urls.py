from django.contrib import admin
from django.urls import path,include
from . import views
from django.conf import settings
from django.conf.urls.static import static


app_name = 'stock'

urlpatterns = [
   path('',views.dashboard, name='dashboard'),
   path('dashboard',views.dashboard, name='dashboard'),

   # views about creating products.......
   path('create_product/',views.create_product, name='create_product'),
   path('product/<int:product_id>/confirm_delete/', views.confirm_delete_product_view, name='confirm_delete_product'),
   path('delete_product/<int:product_id>/', views.delete_product_view, name='delete_product'),

   # views about adding product details ............
   path('add_product_details/',views.add_product_details, name='add_product_details'),
   path('product-details/delete/', views.product_detail_delete_selected_view, name='product_detail_delete_selected'),
   path('sales/bulk_delete/', views.bulk_delete_sales_view, name='bulk_delete_sales'),
   path('product-details/update/<int:pk>/', views.product_detail_update_view, name='product_detail_update'),
   path('product-details/add-stock/<int:pk>/', views.add_stock_to_product_detail_view, name='add_stock_to_product_detail'),


   #views about sales.................
   path('sales/', views.sales_processing_view, name="sales"),
   path('sales/ajax/get-batch-info/<int:pk>/', views.ajax_get_batch_details_for_sale, name='ajax_get_batch_info_for_sale'),
   path('transactions/all/', views.all_transactions_list_view, name='all_transactions_list'),
   path('transactions/export/', views.export_sales_to_excel, name='export_sales_to_excel'),
   path('update-note/', views.update_note, name='update_note'),
   path('sales/pending-deliveries/', views.pending_deliveries_view, name='pending_deliveries'),
   path('sales/process-delivery/<int:sale_pk>/', views.process_delivery_return_view, name='process_delivery_return'),
   path('reports/sales/', views.sales_report_view, name='sales_report'),


   # Recpiy view ...........
   path('sales/receipt/<int:sale_pk>/', views.sale_receipt_view, name='sale_receipt'),




   # URL for managing vehicles............
   path('vehicles/', views.manage_vehicles_view, name='manage_vehicles'),
   path('vehicles/delete/<int:vehicle_pk>/', views.delete_vehicle_action_view, name='delete_vehicle_action'),
   path('vehicles/ajax/get-data/<int:vehicle_pk>/', views.ajax_get_vehicle_data, name='ajax_get_vehicle_data'),
   path('vehicles/update/<int:vehicle_pk>/', views.vehicle_update_action_view, name='vehicle_update_action'),


   # URLs for managing shops...............
   path('shops/', views.manage_shops_view, name='manage_shops'),
   path('shops/delete/<int:shop_pk>/', views.delete_shop_action_view, name='delete_shop_action'),
   path('shops/ajax/get-data/<int:shop_pk>/', views.ajax_get_shop_data, name='ajax_get_shop_data'),
   path('shops/update/<int:shop_pk>/', views.shop_update_action_view, name='shop_update_action'),
   path('sales/by-shop/', views.list_shops_for_sales_view, name='list_shops_for_sales'),
   path('sales/shop-history/<int:shop_pk>/', views.shop_purchase_history_view, name='shop_purchase_history'),



   # auth views............
   path('sign_up/', views.register_user, name='sign_up'),
   path('login/',views.user_login, name='login'),
]+ static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
