# rag_app/views.py

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from .models import Thread, Document, Message
from .serializers import (
    ThreadSerializer, ThreadListSerializer, DocumentSerializer, 
    MessageSerializer, UserSerializer, RegisterSerializer
)
from .services.rag_services import RAGService
import os

rag_service = RAGService()

# Authentication Views
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def register(request):
    """Register new user"""
    serializer = RegisterSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        token, _ = Token.objects.get_or_create(user=user)
        return Response({
            'token': token.key,
            'user': UserSerializer(user).data
        }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def login(request):
    """Login user"""
    username = request.data.get('username')
    password = request.data.get('password')
    
    user = authenticate(username=username, password=password)
    if user:
        token, _ = Token.objects.get_or_create(user=user)
        return Response({
            'token': token.key,
            'user': UserSerializer(user).data
        })
    return Response(
        {'error': 'Invalid credentials'},
        status=status.HTTP_401_UNAUTHORIZED
    )

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def logout(request):
    """Logout user"""
    request.user.auth_token.delete()
    return Response({'message': 'Logged out successfully'})

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def current_user(request):
    """Get current user info"""
    return Response(UserSerializer(request.user).data)

# Thread ViewSet
class ThreadViewSet(viewsets.ModelViewSet):
    serializer_class = ThreadSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return Thread.objects.filter(user=self.request.user)
    
    def get_serializer_class(self):
        if self.action == 'list':
            return ThreadListSerializer
        return ThreadSerializer
    
    def create(self, request):
        """Create new thread with welcome message"""
        thread = Thread.objects.create(
            user=request.user,
            title='New Chat'
        )
        
        # UPDATED: Create welcome message WITHOUT username
        welcome_message = "👋 I'm your chat bot. You can ask me anything or upload a document to get started!"
        Message.objects.create(
            thread=thread,
            role='assistant',
            content=welcome_message
        )
        
        serializer = self.get_serializer(thread)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    def destroy(self, request, pk=None):
        """Delete thread and all associated messages and documents"""
        thread = self.get_object()
        
        # Delete associated documents
        for doc in thread.documents.all():
            doc.delete()
        
        thread.delete()
        return Response(
            {'message': 'Thread deleted successfully'},
            status=status.HTTP_204_NO_CONTENT
        )
    
    @action(detail=True, methods=['post'])
    def send_message(self, request, pk=None):
        """Send message in a thread"""
        thread = self.get_object()
        message_content = request.data.get('message')
        
        if not message_content:
            return Response(
                {'error': 'Message content is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Save user message
        user_message = Message.objects.create(
            thread=thread,
            role='user',
            content=message_content
        )
        
        # Get answer from RAG
        result = rag_service.ask_question(
            question=message_content,
            thread=thread
        )
        
        # UPDATED: Save assistant message WITHOUT sources
        assistant_message = Message.objects.create(
            thread=thread,
            role='assistant',
            content=result['answer']
            # Removed: sources=result.get('sources', [])
        )
        
        # Update thread title if it's the first user message
        if thread.messages.filter(role='user').count() == 1:
            thread.title = message_content[:50] + '...' if len(message_content) > 50 else message_content
            thread.save()
        
        return Response({
            'user_message': MessageSerializer(user_message).data,
            'assistant_message': MessageSerializer(assistant_message).data
        })
    
    @action(detail=True, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    def upload_document(self, request, pk=None):
        """Upload document to a thread"""
        thread = self.get_object()
        file = request.FILES.get('file')
        
        if not file:
            return Response(
                {'error': 'No file provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get file extension
        file_ext = os.path.splitext(file.name)[1].lower().replace('.', '')
        
        if file_ext not in ['pdf', 'docx', 'txt']:
            return Response(
                {'error': 'Unsupported file type. Please upload PDF, DOCX, or TXT files.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create document
        document = Document.objects.create(
            thread=thread,
            user=request.user,
            title=file.name,
            file=file,
            file_type=file_ext
        )
        
        # Process document with RAG
        try:
            # Try to get local path (works with FileSystemStorage)
            file_path = document.file.path
        except NotImplementedError:
            # If cloud storage, download file temporarily
            import tempfile
            from django.core.files.storage import default_storage
            
            # Create temporary file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f'.{file_ext}')
            
            # Read from storage and write to temp file
            with default_storage.open(document.file.name, 'rb') as source_file:
                temp_file.write(source_file.read())
            
            temp_file.close()
            file_path = temp_file.name
        
        success, message = rag_service.process_document(
            file_path,
            document.file_type,
            thread_id=thread.id
        )
        
        # Clean up temporary file if created
        if 'temp_file' in locals():
            os.unlink(file_path)
        
        if success:
            document.processed = True
            document.save()
            
            # Update thread title if still "New Chat"
            if thread.title == 'New Chat':
                thread.title = f"📄 {file.name}"
                thread.save()
            
            # UPDATED: Find and update the welcome message with proper line breaks
            welcome_msg = thread.messages.filter(role='assistant').first()
            if welcome_msg and 'upload a document to get started' in welcome_msg.content:
                # Use actual line breaks instead of \n
                welcome_msg.content = (
                    "👋 I'm your chat bot. You can ask me anything or upload a document to get started!"
                    "📄 I have access to your uploaded document. You can now ask me anything about this document."
                )
                welcome_msg.save()
            
            serializer = DocumentSerializer(document)
            return Response({
                'document': serializer.data,
                'updated_message_id': welcome_msg.id if welcome_msg else None,
                'thread_title': thread.title
            }, status=status.HTTP_201_CREATED)
        else:
            document.delete()
            return Response(
                {'error': f'Failed to process document: {message}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
