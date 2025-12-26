'use client';

import { useState, useRef, useEffect } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  ArrowLeft,
  Send,
  Loader2,
  User,
  Bot,
  Phone,
  CheckCircle,
  AlertCircle,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Textarea } from '@/components/ui/textarea';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { api } from '@/lib/api';
import { formatDateTime } from '@/lib/utils';
import { useToast } from '@/hooks/use-toast';

interface Message {
  id: number;
  role: 'user' | 'assistant';
  content: string;
  createdAt: string;
}

interface Interview {
  id: number;
  applicationId: number;
  candidateName: string;
  requisitionName: string;
  interviewType: string;
  status: string;
  startedAt: string | null;
  completedAt: string | null;
  messageCount: number;
}

interface ProxyMessageResponse {
  userMessage: Message;
  aiResponse: Message;
  isComplete: boolean;
}

interface EndProxyResponse {
  interviewId: number;
  status: string;
  messageCount: number;
  completedAt: string;
}

export default function ProxyInterviewConductPage() {
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const [input, setInput] = useState('');
  const [showEndDialog, setShowEndDialog] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Fetch interview details
  const { data: interview, isLoading: interviewLoading } = useQuery<Interview>({
    queryKey: ['interview', params.id],
    queryFn: async () => {
      const response = await api.get(`/interviews/${params.id}`);
      return response.data;
    },
  });

  // Fetch messages - this is the source of truth
  const { data: messages = [] } = useQuery<Message[]>({
    queryKey: ['interview-messages', params.id],
    queryFn: async () => {
      const response = await api.get(`/interviews/${params.id}/messages`);
      return response.data;
    },
    enabled: !!interview,
  });

  const isComplete = interview?.status === 'completed';

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Send message mutation with optimistic update
  const sendMessageMutation = useMutation<ProxyMessageResponse, Error, string>({
    mutationFn: async (content: string) => {
      const response = await api.post(`/interviews/${params.id}/proxy-message`, {
        content,
      });
      return response.data;
    },
    onSuccess: (data) => {
      // Update the messages cache with new messages
      queryClient.setQueryData<Message[]>(
        ['interview-messages', params.id],
        (old = []) => [...old, data.userMessage, data.aiResponse]
      );
      setInput('');

      if (data.isComplete) {
        queryClient.invalidateQueries({ queryKey: ['interview', params.id] });
      }
    },
    onError: (error) => {
      toast({
        title: 'Failed to send message',
        description: error.message || 'Please try again',
        variant: 'destructive',
      });
    },
  });

  // End interview mutation
  const endInterviewMutation = useMutation<EndProxyResponse, Error>({
    mutationFn: async () => {
      const response = await api.post(`/interviews/${params.id}/end-proxy`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['interview', params.id] });
      queryClient.invalidateQueries({ queryKey: ['applications'] });
      setShowEndDialog(false);
      toast({
        title: 'Interview ended',
        description: 'The evaluation will be processed shortly.',
      });
    },
    onError: (error) => {
      toast({
        title: 'Failed to end interview',
        description: error.message || 'Please try again',
        variant: 'destructive',
      });
      setShowEndDialog(false);
    },
  });

  const handleSend = () => {
    if (input.trim() && !sendMessageMutation.isPending) {
      sendMessageMutation.mutate(input.trim());
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  if (interviewLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin h-8 w-8 border-4 border-primary border-t-transparent rounded-full" />
      </div>
    );
  }

  if (!interview) {
    return (
      <div className="text-center py-12">
        <p className="text-muted-foreground">Interview not found</p>
        <Button variant="outline" onClick={() => router.back()} className="mt-4">
          Go Back
        </Button>
      </div>
    );
  }

  if (interview.interviewType !== 'proxy') {
    return (
      <div className="text-center py-12">
        <AlertCircle className="h-12 w-12 text-destructive mx-auto mb-4" />
        <p className="text-muted-foreground">This page is only for proxy interviews</p>
        <Link href={`/interviews/${interview.id}`}>
          <Button variant="outline" className="mt-4">
            View Interview Details
          </Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="h-[calc(100vh-6rem)] flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between pb-4 border-b">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => router.back()}>
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div>
            <h1 className="text-xl font-bold flex items-center gap-2">
              <Phone className="h-5 w-5" />
              Proxy Interview
            </h1>
            <p className="text-sm text-muted-foreground">
              {interview.candidateName} - {interview.requisitionName}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {isComplete ? (
            <span className="px-3 py-1 rounded-full text-sm bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200 flex items-center gap-1">
              <CheckCircle className="h-4 w-4" />
              Completed
            </span>
          ) : (
            <Button
              variant="outline"
              onClick={() => setShowEndDialog(true)}
              disabled={endInterviewMutation.isPending}
            >
              End Interview
            </Button>
          )}
        </div>
      </div>

      {/* Instructions Card */}
      <Card className="my-4 bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800">
        <CardContent className="py-3">
          <p className="text-sm text-blue-800 dark:text-blue-200">
            <strong>Proxy Mode:</strong> You are conducting this interview on behalf of the candidate during a phone call.
            Type what the candidate says in their own words. The AI will respond with the next question.
          </p>
        </CardContent>
      </Card>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto space-y-4 py-4">
        {messages.length === 0 && !sendMessageMutation.isPending && (
          <div className="text-center text-muted-foreground py-12">
            <p>No messages yet. Type the candidate&apos;s first response to begin.</p>
          </div>
        )}

        {messages.map((message) => (
          <div
            key={message.id}
            className={`flex gap-3 ${
              message.role === 'user' ? 'justify-end' : 'justify-start'
            }`}
          >
            {message.role !== 'user' && (
              <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0">
                <Bot className="h-4 w-4 text-primary" />
              </div>
            )}
            <div
              className={`max-w-[70%] rounded-lg px-4 py-3 ${
                message.role === 'user'
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-muted'
              }`}
            >
              <p className="text-sm whitespace-pre-wrap">{message.content}</p>
              <p
                className={`text-xs mt-1 ${
                  message.role === 'user'
                    ? 'text-primary-foreground/70'
                    : 'text-muted-foreground'
                }`}
              >
                {formatDateTime(message.createdAt)}
              </p>
            </div>
            {message.role === 'user' && (
              <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center flex-shrink-0">
                <User className="h-4 w-4 text-primary-foreground" />
              </div>
            )}
          </div>
        ))}

        {sendMessageMutation.isPending && (
          <div className="flex gap-3 justify-start">
            <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0">
              <Bot className="h-4 w-4 text-primary" />
            </div>
            <div className="bg-muted rounded-lg px-4 py-3">
              <Loader2 className="h-4 w-4 animate-spin" />
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      {!isComplete && (
        <div className="border-t pt-4">
          <div className="flex gap-2">
            <Textarea
              placeholder="Type what the candidate says..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              rows={2}
              className="resize-none"
              disabled={sendMessageMutation.isPending}
            />
            <Button
              onClick={handleSend}
              disabled={!input.trim() || sendMessageMutation.isPending}
              className="self-end"
            >
              {sendMessageMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
            </Button>
          </div>
          <p className="text-xs text-muted-foreground mt-2">
            Press Enter to send, Shift+Enter for new line
          </p>
        </div>
      )}

      {/* Completion Message */}
      {isComplete && (
        <div className="border-t pt-4">
          <Card className="bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800">
            <CardContent className="py-4 text-center">
              <CheckCircle className="h-8 w-8 text-green-600 mx-auto mb-2" />
              <p className="font-medium text-green-800 dark:text-green-200">
                Interview Complete
              </p>
              <p className="text-sm text-green-700 dark:text-green-300 mt-1">
                The evaluation will be processed shortly.
              </p>
              <div className="flex justify-center gap-2 mt-4">
                <Link href={`/interviews/${interview.id}`}>
                  <Button variant="outline" size="sm">
                    View Transcript
                  </Button>
                </Link>
                <Link href="/applications">
                  <Button size="sm">
                    Back to Applications
                  </Button>
                </Link>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* End Interview Confirmation Dialog */}
      <AlertDialog open={showEndDialog} onOpenChange={setShowEndDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>End Interview?</AlertDialogTitle>
            <AlertDialogDescription>
              This will end the interview and trigger the evaluation process.
              {messages.length === 0 && (
                <span className="block mt-2 text-amber-600 dark:text-amber-400">
                  Note: No messages have been recorded yet. The interview will be marked as incomplete.
                </span>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => endInterviewMutation.mutate()}
              disabled={endInterviewMutation.isPending}
            >
              {endInterviewMutation.isPending ? 'Ending...' : 'End Interview'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
