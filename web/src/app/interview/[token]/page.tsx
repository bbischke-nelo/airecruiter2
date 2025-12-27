'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams } from 'next/navigation';
import { Send, Loader2, User, AlertCircle, CheckCircle } from 'lucide-react';
import { Markdown } from '@/components/ui/markdown';
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
  const connectionStatusRef = useRef<ConnectionStatus>('connecting');

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  const connectWebSocket = useCallback(() => {
    if (!token) return;

    // Determine WebSocket URL
    // For relative API URLs (like /recruiter2/api), use the current host
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    let wsUrl: string;

    if (apiUrl.startsWith('/')) {
      // Relative URL - use current page's host
      const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      wsUrl = `${wsProtocol}//${window.location.host}${apiUrl}/v1/ws/interviews/${token}`;
    } else {
      // Absolute URL
      const wsProtocol = apiUrl.startsWith('https') ? 'wss:' : 'ws:';
      const apiHost = apiUrl.replace(/^https?:\/\//, '');
      wsUrl = `${wsProtocol}//${apiHost}/api/v1/ws/interviews/${token}`;
    }

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
            connectionStatusRef.current = 'connected';
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
            connectionStatusRef.current = 'completed';
            setConnectionStatus('completed');
            break;

          case 'error':
            setError(data.message);
            connectionStatusRef.current = 'error';
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
      if (connectionStatusRef.current === 'completed' || event.code === 4000) {
        return;
      }

      // Try to reconnect
      if (reconnectAttempts.current < maxReconnectAttempts) {
        reconnectAttempts.current += 1;
        connectionStatusRef.current = 'connecting';
        setConnectionStatus('connecting');
        setTimeout(connectWebSocket, 2000 * reconnectAttempts.current);
      } else {
        connectionStatusRef.current = 'disconnected';
        setConnectionStatus('disconnected');
        setError('Connection lost. Please refresh the page to continue.');
      }
    };

    return () => {
      ws.close();
    };
  }, [token]);

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
      <div className="min-h-screen bg-white flex items-center justify-center">
        <Card className="w-full max-w-md bg-white border shadow-lg">
          <CardContent className="p-8 text-center">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/recruiter2/logo-primary.png"
              alt="CrossCountry Freight Solutions"
              className="h-12 w-auto mx-auto mb-6"
            />
            <Loader2 className="h-8 w-8 animate-spin text-ccfs-red mx-auto mb-4" />
            <p className="text-lg text-gray-800">Connecting to interview...</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (connectionStatus === 'error' || connectionStatus === 'disconnected') {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center p-4">
        <Card className="w-full max-w-md bg-white border shadow-lg">
          <CardContent className="p-8 text-center">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/recruiter2/logo-primary.png"
              alt="CrossCountry Freight Solutions"
              className="h-12 w-auto mx-auto mb-6"
            />
            <AlertCircle className="h-10 w-10 text-red-600 mx-auto mb-4" />
            <h2 className="text-xl font-semibold mb-2 text-gray-900">
              {connectionStatus === 'error' ? 'Unable to Connect' : 'Connection Lost'}
            </h2>
            <p className="text-gray-600">{error || 'An error occurred.'}</p>
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
      <div className="min-h-screen bg-white flex items-center justify-center p-4">
        <Card className="w-full max-w-md bg-white border shadow-lg">
          <CardContent className="p-8 text-center">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/recruiter2/logo-primary.png"
              alt="CrossCountry Freight Solutions"
              className="h-12 w-auto mx-auto mb-6"
            />
            <CheckCircle className="h-10 w-10 text-green-500 mx-auto mb-4" />
            <h2 className="text-xl font-semibold mb-2 text-gray-900">Interview Complete</h2>
            <p className="text-gray-600">
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
    <div className="min-h-screen bg-gray-100 flex flex-col">
      {/* Header */}
      <header className="bg-ccfs-red text-white px-4 py-3 sticky top-0 z-10 safe-area-top">
        <div className="max-w-3xl mx-auto flex items-center justify-between gap-2 sm:gap-4">
          <div className="flex items-center gap-3 min-w-0 flex-1">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/recruiter2/logo-white.png"
              alt="CrossCountry Freight Solutions"
              className="h-10 w-auto hidden sm:block"
            />
            <div className="min-w-0">
              <h1 className="font-semibold truncate">{interviewInfo?.positionTitle} Interview</h1>
              <p className="text-sm text-white/80 truncate">Welcome, {interviewInfo?.candidateName}</p>
            </div>
          </div>
          <Button
            variant="ghost"
            size="sm"
            className="text-white hover:bg-white/10 px-2 sm:px-3"
            onClick={endInterview}
            title="End Interview"
          >
            <span className="hidden sm:inline">End Interview</span>
            <span className="sm:hidden">End</span>
          </Button>
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
                <div className="w-8 h-8 rounded-full bg-white border border-gray-200 flex items-center justify-center flex-shrink-0 overflow-hidden">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src="/recruiter2/tank.png"
                    alt="Tank"
                    className="w-7 h-7 object-contain"
                  />
                </div>
              )}
              <div
                className={`max-w-[80%] rounded-2xl px-4 py-3 ${
                  message.role === 'user'
                    ? 'bg-ccfs-red'
                    : 'bg-white border border-gray-200 shadow-sm text-gray-800'
                }`}
              >
                <Markdown variant={message.role === 'user' ? 'dark' : 'default'}>
                  {message.content}
                </Markdown>
              </div>
              {message.role === 'user' && (
                <div className="w-8 h-8 rounded-full bg-ccfs-red flex items-center justify-center flex-shrink-0">
                  <User className="h-5 w-5 text-white" />
                </div>
              )}
            </div>
          ))}

          {isTyping && (
            <div className="flex gap-3 items-center">
              <div className="w-8 h-8 rounded-full bg-white border border-gray-200 flex items-center justify-center flex-shrink-0 overflow-hidden">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src="/recruiter2/tank.png"
                  alt="Tank"
                  className="w-7 h-7 object-contain"
                />
              </div>
              <div className="bg-white border border-gray-200 shadow-sm rounded-2xl px-4 py-3">
                <div className="flex items-center gap-2">
                  <span className="text-sm text-gray-500">Tank is typing</span>
                  <div className="flex gap-1">
                    <span
                      className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce"
                      style={{ animationDelay: '0ms' }}
                    />
                    <span
                      className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce"
                      style={{ animationDelay: '150ms' }}
                    />
                    <span
                      className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce"
                      style={{ animationDelay: '300ms' }}
                    />
                  </div>
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input */}
      <div className="bg-white border-t border-gray-200 p-4 pb-safe sticky bottom-0">
        <div className="max-w-3xl mx-auto flex gap-2 sm:gap-3">
          <textarea
            ref={inputRef}
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type your response..."
            rows={1}
            className="flex-1 resize-none rounded-lg border border-gray-300 bg-white text-gray-800 px-3 sm:px-4 py-3 text-base focus:outline-none focus:ring-2 focus:ring-ccfs-red"
            disabled={connectionStatus !== 'connected'}
          />
          <Button
            onClick={sendMessage}
            disabled={!inputValue.trim() || connectionStatus !== 'connected'}
            size="icon"
            className="h-12 w-12 flex-shrink-0 bg-ccfs-red hover:bg-ccfs-red-dark text-white"
          >
            <Send className="h-5 w-5" />
          </Button>
        </div>
        <p className="text-xs text-center text-gray-500 mt-2 hidden sm:block">
          Press Enter to send, Shift+Enter for new line
        </p>
        {/* Compliance disclosures */}
        <div className="max-w-3xl mx-auto mt-3 pt-3 border-t border-gray-100">
          <p className="text-[10px] text-gray-500 text-center leading-relaxed">
            This interview uses artificial intelligence (AI) technology. Your responses are recorded and reviewed as part of our hiring process.
          </p>
        </div>
      </div>
    </div>
  );
}
