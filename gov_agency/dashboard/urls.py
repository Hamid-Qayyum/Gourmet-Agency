# dashboard/urls.py

from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('dashboard', views.dashboard_view, name='main_dashboard'),

    # notes..............
    path('notes/', views.note_list_view, name='note_list'),
    path('notes/create/', views.create_note_view, name='create_note'),
    path('notes/update-status/<int:note_pk>/', views.update_note_status_view, name='update_note_status'),
    path('notes/delete/<int:note_pk>/', views.delete_note_view, name='delete_note'),
    path('notes/update-order/', views.update_note_order_view, name='update_note_order'),
]