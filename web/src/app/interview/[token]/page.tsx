'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams } from 'next/navigation';
import { Send, Loader2, User, Bot, AlertCircle, CheckCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';

interface Message {
  id: number;
  role: 'user' | 'assistant';
  content: string;
  createdAt: string;
}

interface InterviewInfo {
  id: number;
  candidateName: string;
  positionTitle: string;
  status: string;
}

type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'error' | 'completed';

export default function InterviewPage() {
  const { token } = useParams<{ token: string }>();

  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('connecting');
  const [interviewInfo, setInterviewInfo] = useState<InterviewInfo | null>(null);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const reconnectAttempts = useRef(0);
  const maxReconnectAttempts = 3;

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  const connectWebSocket = useCallback(() => {
    if (!token) return;

    // Determine WebSocket URL based on API URL
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    const wsProtocol = apiUrl.startsWith('https') ? 'wss:' : 'ws:';
    const apiHost = apiUrl.replace(/^https?:\/\//, '');
    const wsUrl = `${wsProtocol}//${apiHost}/api/v1/ws/interviews/${token}`;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('WebSocket connected');
      reconnectAttempts.current = 0;
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        switch (data.type) {
          case 'connected':
            setConnectionStatus('connected');
            setInterviewInfo(data.interview);
            break;

          case 'history':
            setMessages(data.messages);
            break;

          case 'message':
            if (data.role === 'assistant') {
              setMessages((prev) => [
                ...prev,
                {
                  id: data.id,
                  role: data.role,
                  content: data.content,
                  createdAt: data.createdAt,
                },
              ]);
            }
            break;

          case 'message_received':
            // Update temporary message with real ID
            setMessages((prev) =>
              prev.map((m) =>
                m.id === -1 ? { ...m, id: data.id, createdAt: data.createdAt } : m
              )
            );
            break;

          case 'typing':
            setIsTyping(data.status);
            break;

          case 'completed':
            setConnectionStatus('completed');
            break;

          case 'human_requested':
            setMessages((prev) => [
              ...prev,
              {
                id: Date.now(),
                role: 'assistant',
                content: data.message,
                createdAt: new Date().toISOString(),
              },
            ]);
            break;

          case 'error':
            setError(data.message);
            setConnectionStatus('error');
            break;
        }
      } catch (err) {
        console.error('Failed to parse WebSocket message', err);
      }
    };

    ws.onerror = () => {
      console.error('WebSocket error');
    };

    ws.onclose = (event) => {
      console.log('WebSocket closed', event.code);

      // Don't reconnect if interview is completed or there was an auth error
      if (connectionStatus === 'completed' || event.code === 4000) {
        return;
      }

      // Try to reconnect
      if (reconnectAttempts.current < maxReconnectAttempts) {
        reconnectAttempts.current += 1;
        setConnectionStatus('connecting');
        setTimeout(connectWebSocket, 2000 * reconnectAttempts.current);
      } else {
        setConnectionStatus('disconnected');
        setError('Connection lost. Please refresh the page to continue.');
      }
    };

    return () => {
      ws.close();
    };
  }, [token, connectionStatus]);

  useEffect(() => {
    const cleanup = connectWebSocket();
    return cleanup;
  }, [connectWebSocket]);

  const sendMessage = () => {
    if (!inputValue.trim() || connectionStatus !== 'connected' || !wsRef.current) {
      return;
    }

    const content = inputValue.trim();
    setInputValue('');

    // Add message optimistically
    setMessages((prev) => [
      ...prev,
      {
        id: -1, // Temporary ID
        role: 'user',
        content,
        createdAt: new Date().toISOString(),
      },
    ]);

    // Send to WebSocket
    wsRef.current.send(JSON.stringify({ type: 'message', content }));

    // Focus back on input
    inputRef.current?.focus();
  };

  const requestHuman = () => {
    if (wsRef.current && connectionStatus === 'connected') {
      wsRef.current.send(JSON.stringify({ type: 'request_human' }));
    }
  };

  const endInterview = () => {
    if (wsRef.current && connectionStatus === 'connected') {
      if (confirm('Are you sure you want to end the interview?')) {
        wsRef.current.send(JSON.stringify({ type: 'end' }));
      }
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  if (connectionStatus === 'connecting') {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <Card className="w-full max-w-md">
          <CardContent className="p-8 text-center">
            <Loader2 className="h-12 w-12 animate-spin text-primary mx-auto mb-4" />
            <p className="text-lg">Connecting to interview...</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (connectionStatus === 'error' || connectionStatus === 'disconnected') {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <Card className="w-full max-w-md">
          <CardContent className="p-8 text-center">
            <AlertCircle className="h-12 w-12 text-destructive mx-auto mb-4" />
            <h2 className="text-xl font-semibold mb-2">
              {connectionStatus === 'error' ? 'Unable to Connect' : 'Connection Lost'}
            </h2>
            <p className="text-muted-foreground">{error || 'An error occurred.'}</p>
            <Button onClick={() => window.location.reload()} className="mt-4">
              Try Again
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (connectionStatus === 'completed') {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <Card className="w-full max-w-md">
          <CardContent className="p-8 text-center">
            <CheckCircle className="h-12 w-12 text-green-500 mx-auto mb-4" />
            <h2 className="text-xl font-semibold mb-2">Interview Complete</h2>
            <p className="text-muted-foreground">
              Thank you for taking the time to interview with us,{' '}
              {interviewInfo?.candidateName}! We will review your responses and be in
              touch soon.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Header */}
      <header className="bg-ccfs-blue text-white px-4 py-3 sticky top-0 z-10">
        <div className="max-w-3xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="font-semibold">{interviewInfo?.positionTitle} Interview</h1>
            <p className="text-sm text-white/80">Welcome, {interviewInfo?.candidateName}</p>
          </div>
          <div className="flex gap-2">
            <Button
              variant="ghost"
              size="sm"
              className="text-white hover:bg-white/10"
              onClick={requestHuman}
            >
              Request Human
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="text-white hover:bg-white/10"
              onClick={endInterview}
            >
              End Interview
            </Button>
          </div>
        </div>
      </header>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4">
        <div className="max-w-3xl mx-auto space-y-4">
          {messages.map((message) => (
            <div
              key={message.id}
              className={`flex gap-3 ${
                message.role === 'user' ? 'justify-end' : 'justify-start'
              }`}
            >
              {message.role === 'assistant' && (
                <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0">
                  <Bot className="h-5 w-5 text-primary" />
                </div>
              )}
              <div
                className={`max-w-[80%] rounded-2xl px-4 py-3 ${
                  message.role === 'user'
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-white border shadow-sm'
                }`}
              >
                <p className="whitespace-pre-wrap">{message.content}</p>
              </div>
              {message.role === 'user' && (
                <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center flex-shrink-0">
                  <User className="h-5 w-5 text-primary-foreground" />
                </div>
              )}
            </div>
          ))}

          {isTyping && (
            <div className="flex gap-3">
              <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0">
                <Bot className="h-5 w-5 text-primary" />
              </div>
              <div className="bg-white border shadow-sm rounded-2xl px-4 py-3">
                <div className="flex gap-1">
                  <span
                    className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                    style={{ animationDelay: '0ms' }}
                  />
                  <span
                    className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                    style={{ animationDelay: '150ms' }}
                  />
                  <span
                    className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                    style={{ animationDelay: '300ms' }}
                  />
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input */}
      <div className="bg-white border-t p-4 sticky bottom-0">
        <div className="max-w-3xl mx-auto flex gap-2">
          <textarea
            ref={inputRef}
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type your response..."
            rows={1}
            className="flex-1 resize-none rounded-lg border border-input bg-background px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
            disabled={connectionStatus !== 'connected'}
          />
          <Button
            onClick={sendMessage}
            disabled={!inputValue.trim() || connectionStatus !== 'connected'}
            size="icon"
            className="h-12 w-12"
          >
            <Send className="h-5 w-5" />
          </Button>
        </div>
        <p className="text-xs text-center text-muted-foreground mt-2">
          Press Enter to send, Shift+Enter for new line
        </p>
      </div>
    </div>
  );
}
