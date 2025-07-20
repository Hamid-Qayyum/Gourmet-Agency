"""
URL configuration for gov_agency project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from . import views

urlpatterns = [
    path('gov_agencykaadmin/', admin.site.urls),
    path('',include('dashboard.urls')),

    # tooogle admin views.............
    path('set-admin-password/', views.set_admin_password_view, name='set_admin_password'),
    path('toggle-admin-mode/', views.toggle_admin_mode_view, name='toggle_admin_mode'),
    path('forgot-admin-password/', views.forgot_admin_password_view, name='forgot_admin_password'),


    path('stock/', include('stock.urls',namespace='stock')),
    path('accounts/', include('accounts.urls', namespace='accounts')),
    path('claims/', include('claim.urls')),
    path('expenses/', include('expense.urls', namespace='expense')),
    path('', include('django.contrib.auth.urls')),

]
