from django.db import models
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password, check_password
from decimal import Decimal


class AdminProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='admin_profile')
    admin_password_hash = models.CharField(max_length=128, blank=True, null=True)
    security_question = models.CharField(max_length=255, blank=True, null=True)
    security_answer_hash = models.CharField(max_length=128, blank=True, null=True)


    def set_password(self, raw_password):
        self.admin_password_hash = make_password(raw_password)

    def check_password(self, raw_password):
        if not self.admin_password_hash:
            return False
        return check_password(raw_password, self.admin_password_hash)
        
    def set_security_answer(self, raw_answer):
        # Standardize the answer to be case-insensitive and without extra spaces
        self.security_answer_hash = make_password(raw_answer.lower().strip())
        
    def check_security_answer(self, raw_answer):
        if not self.security_answer_hash:
            return False
        return check_password(raw_answer.lower().strip(), self.security_answer_hash)

    def __str__(self):
        return f"Admin Profile for {self.user.username}"