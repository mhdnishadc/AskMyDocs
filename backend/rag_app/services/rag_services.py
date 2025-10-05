# services/rag_service.py - Clean version WITHOUT sources
import os
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader, TextLoader
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_groq import ChatGroq
from langchain.chains import ConversationalRetrievalChain
from langchain.prompts import PromptTemplate
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
        
        self.persist_directory = os.path.join(settings.BASE_DIR, 'chroma_db')
        self.vectorstore = None
        
        # Get Groq API key from environment
        self.groq_api_key = os.getenv('GROQ_API_KEY')
        if not self.groq_api_key:
            logger.warning("GROQ_API_KEY not found in environment variables")
        
        self.load_vectorstore()
    
    def load_vectorstore(self):
        """Load existing vectorstore or create new one"""
        try:
            os.makedirs(self.persist_directory, exist_ok=True)
            
            if os.path.exists(os.path.join(self.persist_directory, 'chroma.sqlite3')):
                logger.info("Loading existing vectorstore...")
                self.vectorstore = Chroma(
                    persist_directory=self.persist_directory,
                    embedding_function=self.embeddings
                )
            else:
                logger.info("Creating new vectorstore...")
                self.vectorstore = Chroma(
                    persist_directory=self.persist_directory,
                    embedding_function=self.embeddings
                )
        except Exception as e:
            logger.error(f"Error loading vectorstore: {str(e)}")
            self.vectorstore = Chroma(
                persist_directory=self.persist_directory,
                embedding_function=self.embeddings
            )
    
    def clean_text(self, text):
        """Clean and validate text content"""
        if not text:
            return None
        
        text = ' '.join(text.split())
        text = ''.join(char for char in text if char.isprintable() or char in ['\n', '\t'])
        
        if len(text.strip()) < 10:
            return None
        
        return text.strip()
    
    def process_document(self, file_path, file_type):
        """Process and add document to vectorstore"""
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
            
            logger.info("Loading document pages...")
            documents = loader.load()
            
            if not documents:
                raise ValueError("No content found in document")
            
            logger.info(f"Loaded {len(documents)} pages")
            
            valid_documents = []
            for doc in documents:
                cleaned_content = self.clean_text(doc.page_content)
                if cleaned_content:
                    doc.page_content = cleaned_content
                    valid_documents.append(doc)
            
            if not valid_documents:
                raise ValueError("No valid text content found. Document may be empty or contain only images.")
            
            logger.info(f"Found {len(valid_documents)} valid pages")
            
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200,
                length_function=len,
                separators=["\n\n", "\n", ". ", " ", ""]
            )
            
            logger.info("Splitting documents into chunks...")
            splits = text_splitter.split_documents(valid_documents)
            
            valid_splits = []
            for split in splits:
                cleaned_content = self.clean_text(split.page_content)
                if cleaned_content:
                    split.page_content = cleaned_content
                    valid_splits.append(split)
            
            if not valid_splits:
                raise ValueError("No valid text chunks created")
            
            logger.info(f"Created {len(valid_splits)} valid chunks")
            
            try:
                test_embedding = self.embeddings.embed_query(valid_splits[0].page_content)
                if not test_embedding or len(test_embedding) == 0:
                    raise ValueError("Embedding model returned empty embeddings")
                logger.info(f"Embeddings validated. Dimension: {len(test_embedding)}")
            except Exception as e:
                logger.error(f"Embedding validation failed: {str(e)}")
                raise ValueError(f"Failed to generate embeddings: {str(e)}")
            
            batch_size = 50
            total_batches = (len(valid_splits) + batch_size - 1) // batch_size
            added_count = 0
            
            logger.info(f"Adding documents in {total_batches} batches...")
            
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
            
            logger.info(f"Processing complete. Added {added_count} chunks")
            return True, f"Successfully processed {added_count} chunks from {len(valid_documents)} pages"
            
        except Exception as e:
            logger.error(f"Error processing document: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return False, str(e)
    
    def ask_question(self, question):
        """Answer question based on vectorstore - WITHOUT SOURCES"""
        try:
            collection = self.vectorstore._collection
            if collection.count() == 0:
                return {
                    'answer': 'No documents have been uploaded yet. Please upload documents first.',
                    'sources': []
                }
            
            logger.info(f"Searching for: {question}")
            logger.info(f"Vectorstore has {collection.count()} chunks")
            
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
        """Clear all documents from vectorstore"""
        try:
            if os.path.exists(self.persist_directory):
                import shutil
                shutil.rmtree(self.persist_directory)
                self.load_vectorstore()
            return True, "Vectorstore cleared successfully"
        except Exception as e:
            logger.error(f"Error clearing vectorstore: {str(e)}")
            return False, str(e)