# rag_app/models.py

from django.db import models
from django.contrib.auth.models import User
import os

class Thread(models.Model):
    """Conversation thread for each chat"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='threads', null=True, blank=True)
    title = models.CharField(max_length=255, default='New Chat')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.title}"

class Document(models.Model):
    """Documents uploaded by users"""
    thread = models.ForeignKey(Thread, on_delete=models.CASCADE, related_name='documents', null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='documents')
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='documents/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)
    file_type = models.CharField(max_length=50, blank=True)
    
    class Meta:
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return self.title
    
    def delete(self, *args, **kwargs):
        # Delete the file when the model is deleted
        if self.file:
            if os.path.isfile(self.file.path):
                os.remove(self.file.path)
        super().delete(*args, **kwargs)

class Message(models.Model):
    """Individual messages in a thread"""
    ROLE_CHOICES = (
        ('user', 'User'),
        ('assistant', 'Assistant'),
        ('system', 'System'),
    )
    
    thread = models.ForeignKey(Thread, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    sources = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.thread.title} - {self.role}: {self.content[:50]}"