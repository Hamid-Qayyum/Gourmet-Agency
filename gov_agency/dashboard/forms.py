# dashboard/forms.py

from django import forms
from .models import Note

class NoteForm(forms.ModelForm):
    class Meta:
        model = Note
        fields = ['content']
        widgets = {
            'content': forms.TextInput(attrs={
                'class': 'input input-bordered w-full',
                'placeholder': 'Enter your new to-do item...'
            })
        }
        labels = {
            'content': '' # Hide the label for a cleaner look
        }