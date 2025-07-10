from django.shortcuts import redirect
from django.contrib import messages

def admin_mode_required(view_func):
    def _wrapped_view(request, *args, **kwargs):
        # Check if 'admin_mode_active' is in the session and is True
        if not request.session.get('admin_mode_active', False):
            messages.error(request, "You need to be in Admin Mode to access this page.")
            # Redirect to a safe, non-protected page like the main dashboard
            return redirect('dashboard:main_dashboard') 
        return view_func(request, *args, **kwargs)
    return _wrapped_view