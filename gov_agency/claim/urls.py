from django.urls import path
from . import views

app_name = 'claim'

urlpatterns = [
    # The main hub page that lists vehicles/store
    path('', views.claims_hub_view, name='claims_hub'),
    
    path('by-vehicle/<int:vehicle_pk>/', views.claim_group_details_view, name='vehicle_claim_details'),
    path('group/', views.claim_group_details_view, name='store_claim_details'),
    
    path('create/', views.create_claim_view, name='create_claim'),
    path('delete/<int:claim_pk>/', views.delete_claim_view, name='delete_claim'),
    path('process_pending/', views.process_pending_claims_view, name='process_pending_claims'),
]