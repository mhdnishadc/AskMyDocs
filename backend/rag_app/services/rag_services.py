# services/rag_service.py 
import os
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader, TextLoader
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_groq import ChatGroq
from langchain.chains import ConversationalRetrievalChain
from langchain.prompts import PromptTemplate
from pinecone import Pinecone
from langchain_pinecone import PineconeVectorStore
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class RAGService:
    def __init__(self):
        logger.info("Initializing RAG Service...")
        
        # Initialize embeddings
        self.embeddings = HuggingFaceEmbeddings(
            model_name='sentence-transformers/all-MiniLM-L6-v2',
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True}
        )
        
        # Initialize Pinecone
        self.pinecone_api_key = os.getenv('PINECONE_API_KEY')
        self.groq_api_key = os.getenv('GROQ_API_KEY')
        
        if not self.pinecone_api_key:
            logger.warning("PINECONE_API_KEY not found in environment variables")
        
        if not self.groq_api_key:
            logger.warning("GROQ_API_KEY not found in environment variables")
        
        # Setup Pinecone
        self.vectorstore = None
        self.load_vectorstore()
    
    def load_vectorstore(self):
        """Initialize Pinecone vectorstore"""
        try:
            if not self.pinecone_api_key:
                logger.error("Cannot initialize Pinecone without API key")
                return
            
            # Initialize Pinecone
            pc = Pinecone(api_key=self.pinecone_api_key)
            
            index_name = "medical-rag"
            
            # Check if index exists, create if not
            existing_indexes = [idx['name'] for idx in pc.list_indexes()]
            
            if index_name not in existing_indexes:
                logger.info(f"Creating Pinecone index: {index_name}")
                pc.create_index(
                    name=index_name,
                    dimension=384,  # Dimension for all-MiniLM-L6-v2
                    metric='cosine',
                    spec={
                        'serverless': {
                            'cloud': 'aws',
                            'region': 'us-east-1'
                        }
                    }
                )
                logger.info(f"Index {index_name} created successfully")
            else:
                logger.info(f"Using existing Pinecone index: {index_name}")
            
            # Get index
            index = pc.Index(index_name)
            
            # Create vectorstore
            self.vectorstore = PineconeVectorStore(
                index=index,
                embedding=self.embeddings,
                text_key="text"
            )
            
            logger.info("Pinecone vectorstore initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing Pinecone: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
    
    def clean_text(self, text):
        """Clean and validate text content"""
        if not text:
            return None
        
        # Remove excessive whitespace
        text = ' '.join(text.split())
        
        # Remove non-printable characters except newlines and tabs
        text = ''.join(char for char in text if char.isprintable() or char in ['\n', '\t'])
        
        # Check if text has meaningful content (at least 10 characters)
        if len(text.strip()) < 10:
            return None
        
        return text.strip()
    
    def process_document(self, file_path, file_type):
        """Process and add document to Pinecone"""
        try:
            logger.info(f"Processing {file_type} file: {file_path}")
            
            # Load document based on type
            if file_type == 'pdf':
                loader = PyPDFLoader(file_path)
            elif file_type == 'docx':
                loader = Docx2txtLoader(file_path)
            elif file_type == 'txt':
                loader = TextLoader(file_path, encoding='utf-8')
            else:
                raise ValueError(f"Unsupported file type: {file_type}")
            
            # Load documents
            logger.info("Loading document pages...")
            documents = loader.load()
            
            if not documents:
                raise ValueError("No content found in document")
            
            logger.info(f"Loaded {len(documents)} pages")
            
            # Filter and clean documents
            valid_documents = []
            for doc in documents:
                cleaned_content = self.clean_text(doc.page_content)
                if cleaned_content:
                    doc.page_content = cleaned_content
                    valid_documents.append(doc)
            
            if not valid_documents:
                raise ValueError("No valid text content found. Document may be empty or contain only images.")
            
            logger.info(f"Found {len(valid_documents)} valid pages")
            
            # Split documents into chunks
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200,
                length_function=len,
                separators=["\n\n", "\n", ". ", " ", ""]
            )
            
            logger.info("Splitting documents into chunks...")
            splits = text_splitter.split_documents(valid_documents)
            
            # Filter out empty chunks
            valid_splits = []
            for split in splits:
                cleaned_content = self.clean_text(split.page_content)
                if cleaned_content:
                    split.page_content = cleaned_content
                    valid_splits.append(split)
            
            if not valid_splits:
                raise ValueError("No valid text chunks created")
            
            logger.info(f"Created {len(valid_splits)} valid chunks")
            
            # Test embeddings with first chunk
            try:
                test_embedding = self.embeddings.embed_query(valid_splits[0].page_content)
                if not test_embedding or len(test_embedding) == 0:
                    raise ValueError("Embedding model returned empty embeddings")
                logger.info(f"Embeddings validated. Dimension: {len(test_embedding)}")
            except Exception as e:
                logger.error(f"Embedding validation failed: {str(e)}")
                raise ValueError(f"Failed to generate embeddings: {str(e)}")
            
            # Add to Pinecone in batches
            batch_size = 50
            total_batches = (len(valid_splits) + batch_size - 1) // batch_size
            added_count = 0
            
            logger.info(f"Adding documents to Pinecone in {total_batches} batches...")
            
            for i in range(0, len(valid_splits), batch_size):
                batch = valid_splits[i:i + batch_size]
                batch_num = (i // batch_size) + 1
                logger.info(f"Processing batch {batch_num}/{total_batches}...")
                
                try:
                    self.vectorstore.add_documents(batch)
                    added_count += len(batch)
                    logger.info(f"Batch {batch_num} added. Total: {added_count} chunks")
                except Exception as e:
                    logger.error(f"Error adding batch {batch_num}: {str(e)}")
                    continue
            
            if added_count == 0:
                raise ValueError("Failed to add any chunks to vectorstore")
            
            logger.info(f"Processing complete. Added {added_count} chunks to Pinecone")
            return True, f"Successfully processed {added_count} chunks from {len(valid_documents)} pages"
            
        except Exception as e:
            logger.error(f"Error processing document: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return False, str(e)
    
    def ask_question(self, question):
        """Answer question based on Pinecone vectorstore"""
        try:
            if not self.vectorstore:
                return {
                    'answer': 'Vector store not initialized. Please check Pinecone configuration.',
                    'sources': []
                }
            
            # Check if vectorstore has documents
            stats = self.vectorstore._index.describe_index_stats()
            total_vectors = stats.total_vector_count
            
            if total_vectors == 0:
                return {
                    'answer': 'No documents have been uploaded yet. Please upload documents first.',
                    'sources': []
                }
            
            logger.info(f"Searching for: {question}")
            logger.info(f"Pinecone has {total_vectors} vectors")
            
            if not self.groq_api_key:
                return {
                    'answer': 'Error: GROQ_API_KEY not configured. Please set it in your .env file.',
                    'sources': []
                }
            
            llm = ChatGroq(
                api_key=self.groq_api_key,
                model_name="llama-3.1-8b-instant", 
                temperature=0.3,
            )
            
            template = """You are an assistant for question-answering tasks. Use the following pieces of context to answer the question at the end. 
If you don't know the answer, just say that you don't know, don't try to make up an answer.

Context:
{context}

Question: {question}

Answer:"""
            
            QA_PROMPT = PromptTemplate(
                template=template,
                input_variables=["context", "question"]
            )
            
            qa_chain = ConversationalRetrievalChain.from_llm(
                llm=llm,
                retriever=self.vectorstore.as_retriever(search_kwargs={"k": 3}),
                return_source_documents=True,
                combine_docs_chain_kwargs={"prompt": QA_PROMPT}
            )
            
            result = qa_chain({
                "question": question,
                "chat_history": []
            })
            
            logger.info(f"Got answer for question: {question[:50]}...")
            
            # SIMPLE RETURN - NO SOURCES DISPLAYED
            return {
                'answer': result['answer'],
                'sources': []  # Empty - no sources shown to user
            }
            
        except Exception as e:
            logger.error(f"Error in ask_question: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                'answer': f'Error: {str(e)}',
                'sources': []
            }
    
    def clear_vectorstore(self):
        """Clear all documents from Pinecone"""
        try:
            if not self.vectorstore:
                return False, "Vectorstore not initialized"
            
            # Delete all vectors in the index
            self.vectorstore._index.delete(delete_all=True)
            logger.info("Pinecone index cleared successfully")
            return True, "Vectorstore cleared successfully"
        except Exception as e:
            logger.error(f"Error clearing vectorstore: {str(e)}")
            return False, str(e)