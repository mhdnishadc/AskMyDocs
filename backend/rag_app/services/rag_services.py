# rag_app/services/rag_service.py - HYBRID MODE

import os
from pinecone import Pinecone
from langchain_pinecone import PineconeVectorStore
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader, TextLoader
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_groq import ChatGroq
from langchain.prompts import ChatPromptTemplate
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class RAGService:
    def __init__(self):
        logger.info("Initializing RAG Service (Hybrid Mode)...")
        
        self.embeddings = HuggingFaceEmbeddings(
            model_name='sentence-transformers/all-MiniLM-L6-v2',
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True}
        )
        
        self.pinecone_api_key = os.getenv('PINECONE_API_KEY')
        self.groq_api_key = os.getenv('GROQ_API_KEY')
        
        if not self.pinecone_api_key:
            logger.warning("PINECONE_API_KEY not found")
        
        if not self.groq_api_key:
            logger.warning("GROQ_API_KEY not found")
        
        self.vectorstore = None
        self.load_vectorstore()
    
    def load_vectorstore(self):
        """Initialize Pinecone vectorstore"""
        try:
            if not self.pinecone_api_key:
                logger.error("Cannot initialize Pinecone without API key")
                return
            
            pc = Pinecone(api_key=self.pinecone_api_key)
            index_name = "medical-rag"
            
            existing_indexes = [idx['name'] for idx in pc.list_indexes()]
            
            if index_name not in existing_indexes:
                logger.info(f"Creating Pinecone index: {index_name}")
                pc.create_index(
                    name=index_name,
                    dimension=384,
                    metric='cosine',
                    spec={'serverless': {'cloud': 'aws', 'region': 'us-east-1'}}
                )
            
            index = pc.Index(index_name)
            self.vectorstore = PineconeVectorStore(
                index=index,
                embedding=self.embeddings,
                text_key="text"
            )
            
            logger.info("Pinecone vectorstore initialized")
            
        except Exception as e:
            logger.error(f"Error initializing Pinecone: {str(e)}")
    
    def clean_text(self, text):
        """Clean and validate text content"""
        if not text:
            return None
        
        text = ' '.join(text.split())
        text = ''.join(char for char in text if char.isprintable() or char in ['\n', '\t'])
        
        if len(text.strip()) < 10:
            return None
        
        return text.strip()
    
    def process_document(self, file_path, file_type, thread_id=None):
        """Process and add document to Pinecone with thread metadata"""
        try:
            logger.info(f"Processing {file_type} file: {file_path}")
            
            if file_type == 'pdf':
                loader = PyPDFLoader(file_path)
            elif file_type == 'docx':
                loader = Docx2txtLoader(file_path)
            elif file_type == 'txt':
                loader = TextLoader(file_path, encoding='utf-8')
            else:
                raise ValueError(f"Unsupported file type: {file_type}")
            
            documents = loader.load()
            
            if not documents:
                raise ValueError("No content found in document")
            
            logger.info(f"Loaded {len(documents)} pages")
            
            valid_documents = []
            for doc in documents:
                cleaned_content = self.clean_text(doc.page_content)
                if cleaned_content:
                    doc.page_content = cleaned_content
                    # Add thread metadata
                    if thread_id:
                        doc.metadata['thread_id'] = thread_id
                    valid_documents.append(doc)
            
            if not valid_documents:
                raise ValueError("No valid text content found")
            
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200,
                separators=["\n\n", "\n", ". ", " ", ""]
            )
            
            splits = text_splitter.split_documents(valid_documents)
            
            valid_splits = []
            for split in splits:
                cleaned_content = self.clean_text(split.page_content)
                if cleaned_content:
                    split.page_content = cleaned_content
                    if thread_id:
                        split.metadata['thread_id'] = thread_id
                    valid_splits.append(split)
            
            if not valid_splits:
                raise ValueError("No valid text chunks created")
            
            # Add to Pinecone
            batch_size = 50
            added_count = 0
            
            for i in range(0, len(valid_splits), batch_size):
                batch = valid_splits[i:i + batch_size]
                try:
                    self.vectorstore.add_documents(batch)
                    added_count += len(batch)
                except Exception as e:
                    logger.error(f"Error adding batch: {str(e)}")
                    continue
            
            return True, f"Successfully processed {added_count} chunks"
            
        except Exception as e:
            logger.error(f"Error processing document: {str(e)}")
            return False, str(e)
    
    def ask_question(self, question, thread=None):
        """
        Answer question - HYBRID MODE
        - If thread has documents: use RAG
        - If no documents: use general LLM knowledge
        """
        try:
            if not self.groq_api_key:
                return {
                    'answer': 'Error: GROQ_API_KEY not configured.',
                    'sources': []
                }
            
            llm = ChatGroq(
                api_key=self.groq_api_key,
                model_name="llama-3.1-8b-instant",
                temperature=0.3,
            )
            
            # Check if thread has documents
            has_documents = False
            if thread and thread.documents.filter(processed=True).exists():
                has_documents = True
            
            if has_documents and self.vectorstore:
                # RAG MODE: Search in documents
                try:
                    # Filter by thread_id
                    retriever = self.vectorstore.as_retriever(
                        search_kwargs={
                            "k": 3,
                            "filter": {"thread_id": thread.id} if thread else {}
                        }
                    )
                    
                    relevant_docs = retriever.get_relevant_documents(question)
                    
                    if relevant_docs:
                        # Use documents for context
                        context = "\n\n".join([doc.page_content for doc in relevant_docs])
                        
                        prompt = ChatPromptTemplate.from_messages([
                            ("system", """You are a helpful assistant. Use the following context from the uploaded documents to answer the question.
                            If the context doesn't contain the answer, you can use your general knowledge but mention that it's not from the document.
                            
                            Context from documents:
                            {context}"""),
                            ("human", "{question}")
                        ])
                        
                        chain = prompt | llm
                        response = chain.invoke({
                            "context": context,
                            "question": question
                        })
                        
                        # Format sources
                        sources = []
                        for doc in relevant_docs:
                            sources.append({
                                'content': doc.page_content[:200] + '...',
                                'metadata': doc.metadata
                            })
                        
                        return {
                            'answer': response.content,
                            'sources': sources
                        }
                except Exception as e:
                    logger.error(f"Error in RAG search: {str(e)}")
            
            # GENERAL MODE: No documents or RAG failed, use general knowledge
            prompt = ChatPromptTemplate.from_messages([
                ("system", "You are a helpful AI assistant. Answer the question using your knowledge."),
                ("human", "{question}")
            ])
            
            chain = prompt | llm
            response = chain.invoke({"question": question})
            
            return {
                'answer': response.content,
                'sources': []
            }
            
        except Exception as e:
            logger.error(f"Error in ask_question: {str(e)}")
            return {
                'answer': f'Error: {str(e)}',
                'sources': []
            }
    
    def clear_vectorstore(self):
        """Clear all documents from Pinecone"""
        try:
            if not self.vectorstore:
                return False, "Vectorstore not initialized"
            
            self.vectorstore._index.delete(delete_all=True)
            return True, "Vectorstore cleared successfully"
        except Exception as e:
            logger.error(f"Error clearing vectorstore: {str(e)}")
            return False, str(e)