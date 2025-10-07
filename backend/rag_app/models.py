

# Create your models here.
# models.py
from django.db import models
import os

class Document(models.Model):
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
    # Deletes file from storage (works for S3 and local)
        if self.file:
            self.file.delete(save=False)
        super().delete(*args, **kwargs)


class ChatHistory(models.Model):
    question = models.TextField()
    answer = models.TextField()
    sources = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Q: {self.question[:50]}..."