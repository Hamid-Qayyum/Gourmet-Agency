from django.db import models
from django.contrib.auth.models import User

class Note(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notes")
    content = models.CharField(max_length=255)
    is_completed = models.BooleanField(default=False)
    position = models.PositiveIntegerField(default=0) # For ordering/sorting
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['position'] # Order by the position field

    def __str__(self):
        return self.content[:50]