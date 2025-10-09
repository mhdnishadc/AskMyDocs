// src/App.js - Complete RAG App with Authentication & Threads

import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  MessageCircle, Send, Paperclip, Trash2, LogOut,
  Plus, User, Loader, X, Check, Menu, Bot
} from 'lucide-react';

const API_URL = 'http://localhost:8000/api';

function App() {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem('token'));
  const [showAuth, setShowAuth] = useState('login');

  // Auth states
  const [authForm, setAuthForm] = useState({ username: '', password: '', email: '' });
  const [authError, setAuthError] = useState('');
  const [authLoading, setAuthLoading] = useState(false);

  // Thread states
  const [threads, setThreads] = useState([]);
  const [currentThread, setCurrentThread] = useState(null);
  const [messages, setMessages] = useState([]);

  // Message states
  const [messageInput, setMessageInput] = useState('');
  const [sendLoading, setSendLoading] = useState(false);
  const [uploadLoading, setUploadLoading] = useState(false);

  // UI states
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  
  // ADDED: Document upload state
  const [hasUploadedDoc, setHasUploadedDoc] = useState(false);

  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);

  // Scroll to bottom
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // API Helper - FIXED to handle 204 No Content
  const apiCall = async (endpoint, options = {}) => {
    const headers = {
      'Content-Type': 'application/json',
      ...(token && { 'Authorization': `Token ${token}` }),
      ...options.headers,
    };

    if (options.body instanceof FormData) {
      delete headers['Content-Type'];
    }

    const response = await fetch(`${API_URL}${endpoint}`, {
      ...options,
      headers,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.error || error.detail || 'An error occurred');
    }

    // Handle 204 No Content - don't try to parse JSON
    if (response.status === 204) {
      return null;
    }

    // Only parse JSON if there's content
    const contentType = response.headers.get('content-type');
    if (contentType && contentType.includes('application/json')) {
      return response.json();
    }

    return null;
  };

  // Auth Functions - wrapped with useCallback
  const fetchCurrentUser = useCallback(async () => {
    try {
      const data = await apiCall('/auth/user/');
      setUser(data);
    } catch (err) {
      console.error('Error fetching user:', err);
      handleLogout();
    }
  }, [token]);

  const fetchThreads = useCallback(async () => {
    try {
      const data = await apiCall('/threads/');
      setThreads(data);
    } catch (err) {
      console.error('Error fetching threads:', err);
    }
  }, [token]);

  // Initialize - FIXED useEffect dependencies
  useEffect(() => {
    if (token) {
      fetchCurrentUser();
      fetchThreads();
    }
  }, [token, fetchCurrentUser, fetchThreads]);

  const handleLogin = async (e) => {
    e.preventDefault();
    setAuthLoading(true);
    setAuthError('');

    try {
      const data = await apiCall('/auth/login/', {
        method: 'POST',
        body: JSON.stringify({
          username: authForm.username,
          password: authForm.password,
        }),
      });

      setToken(data.token);
      setUser(data.user);
      localStorage.setItem('token', data.token);
      setAuthForm({ username: '', password: '', email: '' });
    } catch (err) {
      setAuthError(err.message);
    } finally {
      setAuthLoading(false);
    }
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    setAuthLoading(true);
    setAuthError('');

    try {
      const data = await apiCall('/auth/register/', {
        method: 'POST',
        body: JSON.stringify(authForm),
      });

      setToken(data.token);
      setUser(data.user);
      localStorage.setItem('token', data.token);
      setAuthForm({ username: '', password: '', email: '' });
    } catch (err) {
      setAuthError(err.message);
    } finally {
      setAuthLoading(false);
    }
  };

  const handleLogout = async () => {
    try {
      await apiCall('/auth/logout/', { method: 'POST' });
    } catch (err) {
      console.error('Logout error:', err);
    } finally {
      setToken(null);
      setUser(null);
      setThreads([]);
      setCurrentThread(null);
      setMessages([]);
      localStorage.removeItem('token');
    }
  };

  // Thread Functions
  const createNewThread = async () => {
    try {
      const data = await apiCall('/threads/', { method: 'POST' });
      setThreads([data, ...threads]);
      setCurrentThread(data);
      setMessages(data.messages || []);
      setHasUploadedDoc(false); // ADDED: Reset document flag
      setSuccess('New chat created!');
      setTimeout(() => setSuccess(''), 2000);
    } catch (err) {
      setError('Failed to create new thread');
      setTimeout(() => setError(''), 3000);
    }
  };

  const selectThread = async (thread) => {
    try {
      const data = await apiCall(`/threads/${thread.id}/`);
      setCurrentThread(data);
      setMessages(data.messages || []);
      
      // ADDED: Check if thread has documents
      const hasDoc = data.documents && data.documents.length > 0;
      setHasUploadedDoc(hasDoc);
    } catch (err) {
      setError('Failed to load thread');
      setTimeout(() => setError(''), 3000);
    }
  };

  // FIXED deleteThread to handle 204 response
  const deleteThread = async (threadId, e) => {
    e.stopPropagation();

    if (!window.confirm('Delete this chat?')) return;

    try {
      await apiCall(`/threads/${threadId}/`, { method: 'DELETE' });

      setThreads(threads.filter(t => t.id !== threadId));

      if (currentThread?.id === threadId) {
        setCurrentThread(null);
        setMessages([]);
        setHasUploadedDoc(false); // ADDED: Reset document flag
      }

      setSuccess('Chat deleted!');
      setTimeout(() => setSuccess(''), 2000);
    } catch (err) {
      console.error('Delete error:', err);
      setError('Failed to delete thread');
      setTimeout(() => setError(''), 3000);
    }
  };

  // Message Functions
  const sendMessage = async (e) => {
    e.preventDefault();

    if (!messageInput.trim() || !currentThread) return;

    setSendLoading(true);
    setError('');

    try {
      const data = await apiCall(`/threads/${currentThread.id}/send_message/`, {
        method: 'POST',
        body: JSON.stringify({ message: messageInput }),
      });

      setMessages([...messages, data.user_message, data.assistant_message]);
      setMessageInput('');

      fetchThreads();
    } catch (err) {
      setError('Failed to send message');
      setTimeout(() => setError(''), 3000);
    } finally {
      setSendLoading(false);
    }
  };

  // UPDATED: File Upload
  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file || !currentThread) return;

    setUploadLoading(true);
    setError('');

    const formData = new FormData();
    formData.append('file', file);

    try {
      const data = await apiCall(`/threads/${currentThread.id}/upload_document/`, {
        method: 'POST',
        body: formData,
        headers: {},
      });

      // UPDATE THE WELCOME MESSAGE instead of adding system message
      if (data.updated_message_id) {
        // Re-fetch the thread to get updated messages
        const threadData = await apiCall(`/threads/${currentThread.id}/`);
        setMessages(threadData.messages || []);
        
        // ADDED: Set document uploaded flag
        setHasUploadedDoc(true);
      }

      // Update thread title if provided
      if (data.thread_title) {
        setCurrentThread({
          ...currentThread,
          title: data.thread_title
        });

        setThreads(threads.map(t =>
          t.id === currentThread.id
            ? { ...t, title: data.thread_title }
            : t
        ));
      }

      setSuccess('Document uploaded!');
      setTimeout(() => setSuccess(''), 3000);

      e.target.value = '';
    } catch (err) {
      setError(err.message || 'Failed to upload document');
      setTimeout(() => setError(''), 3000);
    } finally {
      setUploadLoading(false);
    }
  };

  // ADDED: Helper functions for message display
  const getMessageLabel = (role) => {
    switch (role) {
      case 'user':
        return 'You';
      case 'assistant':
        return 'Chatbot';
      case 'system':
        return 'System';
      default:
        return role;
    }
  };

  const getMessageIcon = (role) => {
    switch (role) {
      case 'user':
        return <User size={18} />;
      case 'assistant':
        return <Bot size={18} />;
      case 'system':
        return <MessageCircle size={18} />;
      default:
        return null;
    }
  };

  // Render Auth Screen
  if (!token) {
    return (
      <div className="auth-container">
        <div className="auth-box">
          <div className="auth-header">
            <MessageCircle size={48} className="auth-icon" />
            <h1>RAG Chat System</h1>
            <p>Intelligent document-based conversations</p>
          </div>

          {authError && (
            <div className="alert alert-error">
              <X size={16} />
              <span>{authError}</span>
            </div>
          )}

          <div className="auth-tabs">
            <button
              className={showAuth === 'login' ? 'active' : ''}
              onClick={() => setShowAuth('login')}
            >
              Login
            </button>
            <button
              className={showAuth === 'register' ? 'active' : ''}
              onClick={() => setShowAuth('register')}
            >
              Register
            </button>
          </div>

          {showAuth === 'login' ? (
            <form onSubmit={handleLogin} className="auth-form">
              <input
                type="text"
                placeholder="Username"
                value={authForm.username}
                onChange={(e) => setAuthForm({ ...authForm, username: e.target.value })}
                required
              />
              <input
                type="password"
                placeholder="Password"
                value={authForm.password}
                onChange={(e) => setAuthForm({ ...authForm, password: e.target.value })}
                required
              />
              <button type="submit" disabled={authLoading}>
                {authLoading ? <Loader className="spinning" size={20} /> : 'Login'}
              </button>
            </form>
          ) : (
            <form onSubmit={handleRegister} className="auth-form">
              <input
                type="text"
                placeholder="Username"
                value={authForm.username}
                onChange={(e) => setAuthForm({ ...authForm, username: e.target.value })}
                required
              />
              <input
                type="email"
                placeholder="Email"
                value={authForm.email}
                onChange={(e) => setAuthForm({ ...authForm, email: e.target.value })}
                required
              />
              <input
                type="password"
                placeholder="Password"
                value={authForm.password}
                onChange={(e) => setAuthForm({ ...authForm, password: e.target.value })}
                required
              />
              <button type="submit" disabled={authLoading}>
                {authLoading ? <Loader className="spinning" size={20} /> : 'Register'}
              </button>
            </form>
          )}
        </div>
      </div>
    );
  }

  // Main Chat Interface
  return (
    <div className="app-container">
      {/* Sidebar */}
      <div className={`sidebar ${sidebarOpen ? 'open' : 'closed'}`}>
        <div className="sidebar-header">
          <h3 style={{ margin: 0, fontSize: '18px', fontWeight: '600' }}>My Chats</h3>
          <button onClick={createNewThread} className="new-chat-btn" title="New Chat">
            <Plus size={20} />
          </button>
        </div>

        <div className="threads-list">
          {threads.length === 0 ? (
            <div style={{
              padding: '40px 20px',
              textAlign: 'center',
              color: '#888',
              fontSize: '14px'
            }}>
              <MessageCircle size={48} style={{ margin: '0 auto 16px', opacity: 0.3 }} />
              <p>No chats yet</p>
              <p style={{ fontSize: '12px', marginTop: '8px' }}>
                Click the + button to start
              </p>
            </div>
          ) : (
            threads.map((thread) => (
              <div
                key={thread.id}
                className={`thread-item ${currentThread?.id === thread.id ? 'active' : ''}`}
                onClick={() => selectThread(thread)}
              >
                <MessageCircle size={16} />
                <div className="thread-info">
                  <span className="thread-title">{thread.title}</span>
                  <span className="thread-meta">{thread.message_count} messages</span>
                </div>
                <button
                  onClick={(e) => deleteThread(thread.id, e)}
                  className="delete-thread-btn"
                  title="Delete"
                >
                  <Trash2 size={16} />
                </button>
              </div>
            ))
          )}
        </div>

        <button onClick={handleLogout} className="logout-btn">
          <LogOut size={20} />
          <span>Logout</span>
        </button>
      </div>

      {/* Main Chat Area */}
      <div className="main-content">
        {/* Chat header - UPDATED with document indicator */}
        <div className="chat-header">
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="toggle-sidebar-btn"
          >
            <Menu size={24} />
          </button>
          <div style={{ flex: 1 }}>
            <h2 style={{ margin: 0 }}>Welcome, {user?.username}!</h2>

            {/* Show document loaded indicator after successful upload */}
            {hasUploadedDoc && currentThread && (
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                marginTop: '8px',
                fontSize: '14px',
                color: '#059669',
                fontWeight: '500'
              }}>
                <span>📄 Document loaded</span>
              </div>
            )}
          </div>
        </div>

        {/* Notifications */}
        {error && (
          <div className="alert alert-error">
            <X size={16} />
            <span>{error}</span>
            <button onClick={() => setError('')}>
              <X size={16} />
            </button>
          </div>
        )}

        {success && (
          <div className="alert alert-success">
            <Check size={16} />
            <span>{success}</span>
          </div>
        )}

        {/* Messages - UPDATED with labels */}
        <div className="messages-container">
          {!currentThread ? (
            <div className="empty-state">
              <MessageCircle size={64} />
              <h3>Welcome {user?.username}!</h3>
              <p>Hi, I am your AI Chatbot. Create a new chat to get started</p>
              <button onClick={createNewThread} className="create-first-chat">
                <Plus size={20} />
                Start New Chat
              </button>
            </div>
          ) : messages.length === 0 ? (
            <div className="empty-state">
              <Loader className="spinning" size={48} />
              <p>Loading messages...</p>
            </div>
          ) : (
            messages.map((message) => (
              <div key={message.id} className={`message message-${message.role}`}>
                <div className="message-content">
                  {/* Message label header */}
                  <div className="message-label">
                    {getMessageIcon(message.role)}
                    <span>{getMessageLabel(message.role)}</span>
                  </div>

                  {/* Message text */}
                  <p className="message-text" style={{ whiteSpace: 'pre-line' }}>
                    {message.content}
                  </p>

                  {/* Sources */}
                  {message.sources && message.sources.length > 0 && (
                    <div className="message-sources">
                      <strong>Sources:</strong>
                      {message.sources.map((source, idx) => (
                        <div key={idx} className="source-item">
                          • {source.content}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        {currentThread && (
          <div className="input-container">
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileUpload}
              accept=".pdf,.docx,.txt"
              style={{ display: 'none' }}
            />

            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={uploadLoading}
              className="attach-btn"
              title="Upload Document"
            >
              {uploadLoading ? (
                <Loader className="spinning" size={20} />
              ) : (
                <Paperclip size={20} />
              )}
            </button>

            <input
              type="text"
              value={messageInput}
              onChange={(e) => setMessageInput(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && !e.shiftKey && sendMessage(e)}
              placeholder="Type a message..."
              disabled={sendLoading}
              className="message-input"
            />

            <button
              onClick={sendMessage}
              disabled={sendLoading || !messageInput.trim()}
              className="send-btn"
              title="Send"
            >
              {sendLoading ? (
                <Loader className="spinning" size={20} />
              ) : (
                <Send size={20} />
              )}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
