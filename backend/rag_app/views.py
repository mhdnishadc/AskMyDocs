from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from .models import Document, ChatHistory
from .serializers import DocumentSerializer, ChatHistorySerializer, QuestionSerializer
from .services.rag_services import RAGService
import os
import tempfile

rag_service = RAGService()

class DocumentViewSet(viewsets.ModelViewSet):
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer
    parser_classes = (MultiPartParser, FormParser)
    
    def create(self, request, *args, **kwargs):
        file = request.FILES.get('file')
        title = request.data.get('title', file.name if file else 'Untitled')
        
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
            title=title,
            file=file,
            file_type=file_ext
        )
        
        
        temp_file_path = None
        try:
            # Create temporary file to download S3 content
            with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{file_ext}') as tmp_file:
                # Open the file from S3
                document.file.open('rb')
                
                # Read and write chunks to temp file
                for chunk in document.file.chunks():
                    tmp_file.write(chunk)
                
                # Close S3 file
                document.file.close()
                
                # Store temp file path
                temp_file_path = tmp_file.name
            
            # Process document with RAG using temporary file path
            success, message = rag_service.process_document(
                temp_file_path,  # ✅ Use temp file path instead of document.file.path
                document.file_type
            )
            
            if success:
                document.processed = True
                document.save()
                serializer = self.get_serializer(document)
                return Response(
                    {
                        'document': serializer.data,
                        'message': message
                    },
                    status=status.HTTP_201_CREATED
                )
            else:
                document.delete()
                return Response(
                    {'error': f'Failed to process document: {message}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        except Exception as e:
            # Clean up document on error
            if document.id:
                document.delete()
            return Response(
                {'error': f'Error processing document: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        finally:
            # Always clean up temporary file
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                except Exception as e:
                    print(f"Warning: Could not delete temp file {temp_file_path}: {e}")
    
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(
            {'message': 'Document deleted successfully'},
            status=status.HTTP_204_NO_CONTENT
        )
    
    @action(detail=False, methods=['delete'])
    def clear_all(self, request):
        """Delete all documents and clear vectorstore"""
        Document.objects.all().delete()
        success, message = rag_service.clear_vectorstore()
        
        if success:
            return Response({'message': message}, status=status.HTTP_200_OK)
        else:
            return Response({'error': message}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ChatViewSet(viewsets.ModelViewSet):
    queryset = ChatHistory.objects.all()
    serializer_class = ChatHistorySerializer
    
    @action(detail=False, methods=['post'])
    def ask(self, request):
        """Ask a question based on uploaded documents"""
        serializer = QuestionSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        question = serializer.validated_data['question']
        
        # Get answer from RAG
        result = rag_service.ask_question(question)
        
        # Save to history
        chat = ChatHistory.objects.create(
            question=question,
            answer=result['answer'],
            sources=result['sources']
        )
        
        return Response({
            'id': chat.id,
            'question': chat.question,
            'answer': chat.answer,
            'sources': chat.sources,
            'created_at': chat.created_at
        }, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['delete'])
    def clear_history(self, request):
        """Clear all chat history"""
        ChatHistory.objects.all().delete()
        return Response(
            {'message': 'Chat history cleared'},
            status=status.HTTP_200_OK
        )