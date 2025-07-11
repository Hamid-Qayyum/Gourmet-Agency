from django import forms

class SetAdminPasswordForm(forms.Form):
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'input input-bordered w-full'}), label="New Admin Password")
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'input input-bordered w-full'}), label="Confirm Admin Password")
    security_question = forms.CharField(max_length=255, widget=forms.TextInput(attrs={'class': 'input input-bordered w-full'}), label="Security Question (Remember this always. If you forget password it will be used to reset the password)")
    security_answer = forms.CharField(max_length=255, widget=forms.TextInput(attrs={'class': 'input input-bordered w-full'}), label="Security Answer")

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('password') != cleaned_data.get('confirm_password'):
            raise forms.ValidationError("Passwords do not match.")
        return cleaned_data

class EnterAdminPasswordForm(forms.Form):
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'input input-bordered w-full'}), label="Enter Admin Password")



class SecurityAnswerForm(forms.Form):
    security_answer = forms.CharField(
        label="Your Answer",
        widget=forms.TextInput(attrs={'class': 'input input-bordered w-full',
                                       'autofocus': True,
                                        'autocomplete': 'off',
                                })
    )

class ResetAdminPasswordForm(forms.Form):
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'input input-bordered w-full'}), label="New Admin Password")
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'input input-bordered w-full'}), label="Confirm New Password")

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('password') != cleaned_data.get('confirm_password'):
            raise forms.ValidationError("Passwords do not match.")
        return cleaned_data