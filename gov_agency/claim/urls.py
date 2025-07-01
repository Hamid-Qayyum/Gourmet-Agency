from django.urls import path
from . import views

app_name = 'claim'

urlpatterns = [
    # The main hub page that lists vehicles/store
    path('', views.claims_hub_view, name='claims_hub'),
    
    # The page showing claims for a specific vehicle
    path('by-vehicle/<int:vehicle_pk>/', views.claim_group_details_view, name='claims_by_vehicle'),
    
    # The page showing claims for the "Store" (no vehicle)
    path('by-store/', views.claim_group_details_view, name='claims_by_store'),
    
    # Action URLs (will be called from modals)
    path('create/', views.create_claim_view, name='create_claim'),
    path('update/<int:claim_pk>/', views.update_claim_view, name='update_claim'),
    path('delete/<int:claim_pk>/', views.delete_claim_view, name='delete_claim'),
    
    # AJAX endpoint to get data for the update modal
    path('ajax/get-data/<int:claim_pk>/', views.ajax_get_claim_data, name='ajax_get_claim_data'),
]