# rag_app/serializers.py

from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Thread, Document, Message

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email']

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    
    class Meta:
        model = User
        fields = ['username', 'email', 'password']
    
    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password'],
        )
        return user

class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ['id', 'role', 'content', 'sources', 'created_at']

class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ['id', 'title', 'file', 'uploaded_at', 'processed', 'file_type']
        read_only_fields = ['uploaded_at', 'processed', 'file_type']

class ThreadSerializer(serializers.ModelSerializer):
    messages = MessageSerializer(many=True, read_only=True)
    documents = DocumentSerializer(many=True, read_only=True)
    message_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Thread
        fields = ['id', 'title', 'created_at', 'updated_at', 'messages', 'documents', 'message_count']
    
    def get_message_count(self, obj):
        return obj.messages.count()

class ThreadListSerializer(serializers.ModelSerializer):
    """Lighter serializer for thread list (no messages)"""
    message_count = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    
    class Meta:
        model = Thread
        fields = ['id', 'title', 'created_at', 'updated_at', 'message_count', 'last_message']
    
    def get_message_count(self, obj):
        return obj.messages.count()
    
    def get_last_message(self, obj):
        last_msg = obj.messages.filter(role='user').last()
        if last_msg:
            return last_msg.content[:50] + '...' if len(last_msg.content) > 50 else last_msg.content
        return None