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
   path('product-details/update/<int:pk>/', views.product_detail_update_view, name='product_detail_update'),

   #views about sales.................
   path('sales/', views.sales, name="sales"),
   path('sales/ajax/get-batch-info/<int:pk>/', views.ajax_get_batch_details_for_sale, name='ajax_get_batch_info_for_sale'),


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


   # auth views............
   path('sign_up/', views.register_user, name='sign_up'),
   path('login/',views.user_login, name='login'),
]+ static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
