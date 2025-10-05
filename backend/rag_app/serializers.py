# serializers.py
from rest_framework import serializers
from .models import Document, ChatHistory

class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ['id', 'title', 'file', 'uploaded_at', 'processed', 'file_type']
        read_only_fields = ['uploaded_at', 'processed', 'file_type']

class ChatHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatHistory
        fields = ['id', 'question', 'answer', 'sources', 'created_at']
        read_only_fields = ['created_at']

class QuestionSerializer(serializers.Serializer):
    question = serializers.CharField(required=True, max_length=1000)