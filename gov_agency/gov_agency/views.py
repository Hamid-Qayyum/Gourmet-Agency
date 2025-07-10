from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import AdminProfile
from .forms import SetAdminPasswordForm, EnterAdminPasswordForm, ResetAdminPasswordForm,SecurityAnswerForm

@login_required
def set_admin_password_view(request):
    admin_profile, created = AdminProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = SetAdminPasswordForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            admin_profile.set_password(data['password'])
            admin_profile.security_question = data['security_question']
            admin_profile.set_security_answer(data['security_answer'])
            admin_profile.save()
            messages.success(request, "Admin Mode password has been set. You can now activate it.")
            return redirect('dashboard:main_dashboard')
    else:
        form = SetAdminPasswordForm()

    context = {'form': form}
    return render(request, 'gov_agency/set_admin_password.html', context)


@login_required
def toggle_admin_mode_view(request):
    admin_profile, created = AdminProfile.objects.get_or_create(user=request.user)

    # If the admin password has never been set, force the user to set it first.
    if not admin_profile.admin_password_hash:
        messages.warning(request, "You must set an Admin Mode password before you can use this feature.")
        return redirect('set_admin_password')

    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'activate':
            form = EnterAdminPasswordForm(request.POST)
            if form.is_valid():
                password = form.cleaned_data['password']
                if admin_profile.check_password(password):
                    request.session['admin_mode_active'] = True
                    messages.success(request, "Admin Mode Activated.")
                else:
                    messages.error(request, "Incorrect Admin Password.")
        
        elif action == 'deactivate':
            # Clear the session key to deactivate the mode
            if 'admin_mode_active' in request.session:
                del request.session['admin_mode_active']
            messages.info(request, "Admin Mode Deactivated.")
            
    # Redirect back to the page the user was on
    return redirect(request.META.get('HTTP_REFERER', 'dashboard:main_dashboard'))



@login_required
def forgot_admin_password_view(request):
    admin_profile = AdminProfile.objects.filter(user=request.user).first()
    session_key = 'admin_password_reset_authorized'

    # Security check: Does the user have a profile and a security question set?
    if not admin_profile or not admin_profile.security_question:
        messages.error(request, "No security question is set up for your account. Cannot recover password.")
        return redirect('dashboard:main_dashboard')

    if request.method == 'POST':
        action = request.POST.get('action')
        
        # --- Stage 1: User submits the security answer ---
        if action == 'check_answer':
            answer_form = SecurityAnswerForm(request.POST)
            if answer_form.is_valid():
                answer = answer_form.cleaned_data['security_answer']
                if admin_profile.check_security_answer(answer):
                    # Answer is correct. Authorize the reset in the session.
                    request.session[session_key] = True
                    messages.success(request, "Security question answered correctly. You can now set a new password.")
                    # The page will now show the reset form (see context below)
                else:
                    messages.error(request, "Incorrect answer. Please try again.")
                    request.session[session_key] = False # Explicitly deny
        
        # --- Stage 2: User submits the new password ---
        elif action == 'reset_password':
            # Security check: Ensure they were authorized by the previous step.
            if not request.session.get(session_key):
                messages.error(request, "Authorization expired or not granted. Please answer the security question again.")
                return redirect('gov_agency:forgot_admin_password')
            
            reset_form = ResetAdminPasswordForm(request.POST)
            if reset_form.is_valid():
                new_password = reset_form.cleaned_data['password']
                admin_profile.set_password(new_password)
                admin_profile.save()
                
                # Clean up the session
                del request.session[session_key]
                
                messages.success(request, "Your Admin Mode password has been reset successfully.")
                return redirect('dashboard:main_dashboard')
            else:
                # If form is invalid, repopulate the context to show the reset form again
                context = {
                    'security_question': admin_profile.security_question,
                    'answer_form': SecurityAnswerForm(),
                    'reset_form': reset_form, # Pass the form with errors
                    'show_reset_form': True, # Keep showing the reset form
                }
                return render(request, 'gov_agency/forgot_admin_password.html', context)

    # --- For a GET request, or after Stage 1 POST ---
    show_reset_form = request.session.get(session_key, False)
    context = {
        'security_question': admin_profile.security_question,
        'answer_form': SecurityAnswerForm(),
        'reset_form': ResetAdminPasswordForm(),
        'show_reset_form': show_reset_form
    }
    return render(request, 'gov_agency/forgot_admin_password.html', context)