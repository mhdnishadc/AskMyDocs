// src/App.js
import React, { useState, useEffect } from 'react';
import { Upload, MessageCircle, File, Trash2, Send, X, FileText, Loader } from 'lucide-react';
import './App.css';

const API_URL = "http://localhost:8000/api";


function App() {
  const [documents, setDocuments] = useState([]);
  const [chatHistory, setChatHistory] = useState([]);
  const [question, setQuestion] = useState('');
  const [loading, setLoading] = useState(false);
  const [uploadLoading, setUploadLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  useEffect(() => {
    fetchDocuments();
    fetchChatHistory();
  }, []);

  const fetchDocuments = async () => {
    try {
      const response = await fetch(`${API_URL}/documents/`);
      const data = await response.json();
      setDocuments(data);
    } catch (err) {
      console.error('Error fetching documents:', err);
      setError('Failed to fetch documents');
    }
  };

  const fetchChatHistory = async () => {
    try {
      const response = await fetch(`${API_URL}/chat/`);
      const data = await response.json();
      setChatHistory(data);
    } catch (err) {
      console.error('Error fetching chat history:', err);
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);
    formData.append('title', file.name);

    setUploadLoading(true);
    setError('');
    setSuccess('');

    try {
      const response = await fetch(`${API_URL}/documents/`, {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();

      if (response.ok) {
        setSuccess(`Document "${file.name}" uploaded successfully!`);
        await fetchDocuments();
        e.target.value = '';
        setTimeout(() => setSuccess(''), 3000);
      } else {
        setError(data.error || 'Failed to upload document');
      }
    } catch (err) {
      setError('Error uploading document. Please try again.');
    } finally {
      setUploadLoading(false);
    }
  };

  const handleDeleteDocument = async (id, title) => {
    if (!window.confirm(`Are you sure you want to delete "${title}"?`)) {
      return;
    }

    try {
      const response = await fetch(`${API_URL}/documents/${id}/`, {
        method: 'DELETE',
      });

      if (response.ok) {
        setSuccess('Document deleted successfully');
        await fetchDocuments();
        setTimeout(() => setSuccess(''), 3000);
      }
    } catch (err) {
      console.error('Error deleting document:', err);
      setError('Failed to delete document');
    }
  };

  const handleAskQuestion = async (e) => {
    e.preventDefault();
    if (!question.trim() || loading) return;

    if (documents.length === 0) {
      setError('Please upload at least one document first');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const response = await fetch(`${API_URL}/chat/ask/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ question: question.trim() }),
      });

      const data = await response.json();

      if (response.ok) {
        setChatHistory([data, ...chatHistory]);
        setQuestion('');
      } else {
        setError(data.error || 'Failed to get answer');
      }
    } catch (err) {
      setError('Error asking question. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const clearAllDocuments = async () => {
    if (!window.confirm('Are you sure you want to delete ALL documents? This will also clear the vector database.')) {
      return;
    }

    try {
      const response = await fetch(`${API_URL}/documents/clear_all/`, {
        method: 'DELETE',
      });

      if (response.ok) {
        setSuccess('All documents cleared');
        await fetchDocuments();
        setChatHistory([]);
        setTimeout(() => setSuccess(''), 3000);
      }
    } catch (err) {
      console.error('Error clearing documents:', err);
      setError('Failed to clear documents');
    }
  };

  const clearChatHistory = async () => {
    if (!window.confirm('Are you sure you want to clear chat history?')) {
      return;
    }

    try {
      const response = await fetch(`${API_URL}/chat/clear_history/`, {
        method: 'DELETE',
      });

      if (response.ok) {
        setChatHistory([]);
        setSuccess('Chat history cleared');
        setTimeout(() => setSuccess(''), 3000);
      }
    } catch (err) {
      console.error('Error clearing chat history:', err);
      setError('Failed to clear chat history');
    }
  };

  return (
    <div className="app">
      <div className="container">
        {/* Header */}
        <div className="header">
          <h1 className="title">RAG System</h1>
          <p className="subtitle">Upload documents and ask questions powered by AI</p>
        </div>

        {/* Notifications */}
        {error && (
          <div className="notification error">
            <span>{error}</span>
            <button onClick={() => setError('')} className="close-btn">
              <X size={20} />
            </button>
          </div>
        )}

        {success && (
          <div className="notification success">
            <span>{success}</span>
            <button onClick={() => setSuccess('')} className="close-btn">
              <X size={20} />
            </button>
          </div>
        )}

        {/* Main Content */}
        <div className="main-grid">
          {/* Documents Panel */}
          <div className="panel documents-panel">
            <div className="panel-header">
              <h2 className="panel-title">
                <FileText size={24} />
                Documents ({documents.length})
              </h2>
              {documents.length > 0 && (
                <button onClick={clearAllDocuments} className="clear-btn">
                  Clear All
                </button>
              )}
            </div>

            {/* Upload Area */}
            <label className="upload-area">
              <input
                type="file"
                className="file-input"
                accept=".pdf,.docx,.txt"
                onChange={handleFileUpload}
                disabled={uploadLoading}
              />
              <div className="upload-content">
                {uploadLoading ? (
                  <>
                    <Loader className="upload-icon spinning" size={32} />
                    <p className="upload-text">Processing...</p>
                  </>
                ) : (
                  <>
                    <Upload className="upload-icon" size={32} />
                    <p className="upload-text">Click to upload</p>
                    <p className="upload-subtext">PDF, DOCX, TXT (Max 10MB)</p>
                  </>
                )}
              </div>
            </label>

            {/* Documents List */}
            <div className="documents-list">
              {documents.map((doc) => (
                <div key={doc.id} className="document-item">
                  <div className="document-info">
                    <File size={20} className="document-icon" />
                    <div className="document-details">
                      <p className="document-title">{doc.title}</p>
                      <p className="document-meta">
                        {doc.file_type.toUpperCase()}
                        {doc.processed && ' • Processed'}
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={() => handleDeleteDocument(doc.id, doc.title)}
                    className="delete-btn"
                    title="Delete document"
                  >
                    <Trash2 size={18} />
                  </button>
                </div>
              ))}
              {documents.length === 0 && (
                <div className="empty-state">
                  <p>No documents uploaded yet</p>
                  <p className="empty-subtext">Upload a document to get started</p>
                </div>
              )}
            </div>
          </div>

          {/* Chat Panel */}
          <div className="panel chat-panel">
            <div className="panel-header">
              <h2 className="panel-title">
                <MessageCircle size={24} />
                Ask Questions
              </h2>
              {chatHistory.length > 0 && (
                <button onClick={clearChatHistory} className="clear-btn">
                  Clear History
                </button>
              )}
            </div>

            {/* Chat Messages */}
            <div className="chat-messages">
              {chatHistory.map((chat) => (
                <div key={chat.id} className="chat-item">
                  <div className="message question">
                    <p className="message-text">{chat.question}</p>
                  </div>
                  <div className="message answer">
                    <p className="message-text">{chat.answer}</p>
                    {chat.sources && chat.sources.length > 0 && (
                      <div className="sources">
                        <p className="sources-title">Sources:</p>
                        {chat.sources.map((source, idx) => (
                          <div key={idx} className="source-item">
                            <span className="source-bullet">•</span>
                            <span className="source-text">{source.content}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))}
              {chatHistory.length === 0 && (
                <div className="empty-state chat-empty">
                  <MessageCircle size={48} className="empty-icon" />
                  <p>No messages yet</p>
                  <p className="empty-subtext">
                    {documents.length === 0
                      ? 'Upload documents first, then ask questions'
                      : 'Ask a question about your documents'}
                  </p>
                </div>
              )}
            </div>

            {/* Input Form */}
            <div className="chat-input-wrapper">
              <input
                type="text"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyPress={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleAskQuestion(e);
                  }
                }}
                placeholder={
                  documents.length === 0
                    ? 'Upload documents first...'
                    : 'Ask a question about your documents...'
                }
                className="chat-input"
                disabled={loading || documents.length === 0}
              />
              <button
                onClick={handleAskQuestion}
                disabled={loading || !question.trim() || documents.length === 0}
                className="send-btn"
                title="Send message"
              >
                {loading ? (
                  <Loader className="spinning" size={20} />
                ) : (
                  <Send size={20} />
                )}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;