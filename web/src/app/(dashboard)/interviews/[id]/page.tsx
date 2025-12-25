'use client';

import { useQuery } from '@tanstack/react-query';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  ArrowLeft,
  MessageSquare,
  User,
  Bot,
  Clock,
  CheckCircle,
  AlertCircle,
  ExternalLink,
  Download,
  ThumbsUp,
  ThumbsDown,
  AlertTriangle,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { api } from '@/lib/api';
import { formatDateTime } from '@/lib/utils';
import { Interview, Message, Evaluation } from '@/types';

interface InterviewDetail extends Interview {
  application?: {
    id: number;
    candidateName: string;
    candidateEmail: string;
    requisitionId: number;
  };
}

export default function InterviewDetailPage() {
  const params = useParams();
  const router = useRouter();

  const { data: interview, isLoading } = useQuery<InterviewDetail>({
    queryKey: ['interview', params.id],
    queryFn: async () => {
      const response = await api.get(`/interviews/${params.id}`);
      return response.data;
    },
  });

  const { data: messages } = useQuery<{ data: Message[] }>({
    queryKey: ['interview-messages', params.id],
    queryFn: async () => {
      const response = await api.get(`/interviews/${params.id}/messages`);
      return response.data;
    },
    enabled: !!interview,
  });

  const { data: evaluation } = useQuery<Evaluation>({
    queryKey: ['interview-evaluation', params.id],
    queryFn: async () => {
      const response = await api.get(`/interviews/${params.id}/evaluation`);
      return response.data;
    },
    enabled: interview?.status === 'completed',
  });

  if (isLoading) {
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

  const scoreCategories = evaluation
    ? [
        { label: 'Reliability', score: evaluation.reliabilityScore },
        { label: 'Accountability', score: evaluation.accountabilityScore },
        { label: 'Professionalism', score: evaluation.professionalismScore },
        { label: 'Communication', score: evaluation.communicationScore },
        { label: 'Technical', score: evaluation.technicalScore },
        { label: 'Growth Potential', score: evaluation.growthPotentialScore },
      ]
    : [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-4">
          <Button variant="ghost" size="icon" onClick={() => router.back()}>
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div>
            <h1 className="text-2xl font-bold">
              Interview with {interview.application?.candidateName || 'Candidate'}
            </h1>
            <p className="text-muted-foreground">
              {interview.application?.candidateEmail}
            </p>
            {interview.application && (
              <Link
                href={`/applications/${interview.application.id}`}
                className="text-sm text-primary hover:underline flex items-center gap-1 mt-1"
              >
                View Application
                <ExternalLink className="h-3 w-3" />
              </Link>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`px-3 py-1 rounded-full text-sm ${getStatusColor(interview.status)}`}
          >
            {interview.status.replace(/_/g, ' ')}
          </span>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Transcript */}
        <div className="lg:col-span-2">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="flex items-center gap-2">
                <MessageSquare className="h-5 w-5" />
                Transcript
              </CardTitle>
              <Button variant="outline" size="sm">
                <Download className="h-4 w-4 mr-2" />
                Export
              </Button>
            </CardHeader>
            <CardContent>
              {messages?.data?.length ? (
                <div className="space-y-4 max-h-[600px] overflow-y-auto">
                  {messages.data.map((message) => (
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
                        className={`max-w-[80%] rounded-lg px-4 py-2 ${
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
                </div>
              ) : (
                <p className="text-center text-muted-foreground py-12">
                  No messages yet
                </p>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Evaluation Sidebar */}
        <div className="space-y-4">
          {/* Interview Info */}
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Interview Details</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Type</span>
                <span>{interview.interviewType}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Created</span>
                <span>{formatDateTime(interview.createdAt)}</span>
              </div>
              {interview.startedAt && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Started</span>
                  <span>{formatDateTime(interview.startedAt)}</span>
                </div>
              )}
              {interview.completedAt && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Completed</span>
                  <span>{formatDateTime(interview.completedAt)}</span>
                </div>
              )}
              {interview.humanRequested && (
                <div className="flex items-center gap-2 text-yellow-600">
                  <AlertCircle className="h-4 w-4" />
                  Human review requested
                </div>
              )}
            </CardContent>
          </Card>

          {/* Evaluation */}
          {evaluation && (
            <>
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">Overall Score</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-center">
                    <div className={`text-5xl font-bold ${getScoreColor(evaluation.overallScore)}`}>
                      {evaluation.overallScore}
                    </div>
                    <p className="text-sm text-muted-foreground mt-1">out of 100</p>
                    <span
                      className={`inline-block mt-3 px-3 py-1 rounded-full text-sm ${getRecommendationColor(
                        evaluation.recommendation
                      )}`}
                    >
                      {formatRecommendation(evaluation.recommendation)}
                    </span>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">Score Breakdown</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {scoreCategories.map((cat) => (
                    <div key={cat.label}>
                      <div className="flex justify-between text-sm mb-1">
                        <span>{cat.label}</span>
                        <span className="font-medium">{cat.score}/10</span>
                      </div>
                      <div className="h-2 bg-muted rounded-full overflow-hidden">
                        <div
                          className="h-full bg-primary rounded-full transition-all"
                          style={{ width: `${(cat.score / 10) * 100}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">Summary</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm">{evaluation.summary}</p>
                </CardContent>
              </Card>

              <div className="grid gap-4">
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm flex items-center gap-2 text-green-600">
                      <ThumbsUp className="h-4 w-4" />
                      Strengths
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ul className="space-y-1 text-sm">
                      {evaluation.strengths.map((s, i) => (
                        <li key={i} className="flex items-start gap-2">
                          <CheckCircle className="h-4 w-4 text-green-500 mt-0.5 flex-shrink-0" />
                          {s}
                        </li>
                      ))}
                    </ul>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm flex items-center gap-2 text-orange-600">
                      <ThumbsDown className="h-4 w-4" />
                      Weaknesses
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ul className="space-y-1 text-sm">
                      {evaluation.weaknesses.map((w, i) => (
                        <li key={i} className="flex items-start gap-2">
                          <AlertCircle className="h-4 w-4 text-orange-500 mt-0.5 flex-shrink-0" />
                          {w}
                        </li>
                      ))}
                    </ul>
                  </CardContent>
                </Card>

                {evaluation.redFlags.length > 0 && (
                  <Card>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm flex items-center gap-2 text-red-600">
                        <AlertTriangle className="h-4 w-4" />
                        Red Flags
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <ul className="space-y-1 text-sm">
                        {evaluation.redFlags.map((r, i) => (
                          <li key={i} className="flex items-start gap-2">
                            <AlertTriangle className="h-4 w-4 text-red-500 mt-0.5 flex-shrink-0" />
                            {r}
                          </li>
                        ))}
                      </ul>
                    </CardContent>
                  </Card>
                )}
              </div>
            </>
          )}

          {!evaluation && interview.status === 'completed' && (
            <Card>
              <CardContent className="py-8 text-center">
                <Clock className="h-8 w-8 text-muted-foreground mx-auto mb-2" />
                <p className="text-sm text-muted-foreground">
                  Evaluation pending...
                </p>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

function getStatusColor(status: string): string {
  const colors: Record<string, string> = {
    scheduled: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
    in_progress: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
    completed: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
    abandoned: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
  };
  return colors[status] || 'bg-gray-100 text-gray-800';
}

function getScoreColor(score: number): string {
  if (score >= 80) return 'text-green-600';
  if (score >= 60) return 'text-yellow-600';
  return 'text-red-600';
}

function getRecommendationColor(rec: string): string {
  const colors: Record<string, string> = {
    recommend: 'bg-green-100 text-green-800',
    strong_hire: 'bg-green-100 text-green-800',
    consider: 'bg-yellow-100 text-yellow-800',
    no_hire: 'bg-red-100 text-red-800',
    do_not_recommend: 'bg-red-100 text-red-800',
  };
  return colors[rec] || 'bg-gray-100 text-gray-800';
}

function formatRecommendation(rec: string): string {
  const map: Record<string, string> = {
    recommend: 'Recommend',
    strong_hire: 'Strong Hire',
    consider: 'Consider',
    no_hire: 'Do Not Hire',
    do_not_recommend: 'Do Not Recommend',
  };
  return map[rec] || rec;
}
