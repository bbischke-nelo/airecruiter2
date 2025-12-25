'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  ArrowLeft,
  Mail,
  FileText,
  MessageSquare,
  AlertTriangle,
  CheckCircle,
  Clock,
  RefreshCw,
  ExternalLink,
  ThumbsUp,
  ThumbsDown,
  AlertCircle,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { api } from '@/lib/api';
import { formatDateTime, formatRelativeTime } from '@/lib/utils';
import { Application, Analysis, Interview, Evaluation } from '@/types';

interface ApplicationDetail extends Application {
  requisition?: {
    id: number;
    name: string;
    externalId: string;
  };
}

export default function ApplicationDetailPage() {
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();

  const { data: application, isLoading } = useQuery<ApplicationDetail>({
    queryKey: ['application', params.id],
    queryFn: async () => {
      const response = await api.get(`/applications/${params.id}`);
      return response.data;
    },
  });

  const { data: analysis } = useQuery<Analysis>({
    queryKey: ['application-analysis', params.id],
    queryFn: async () => {
      const response = await api.get(`/applications/${params.id}/analysis`);
      return response.data;
    },
    enabled: !!application,
  });

  const reprocessMutation = useMutation({
    mutationFn: async () => {
      await api.post(`/applications/${params.id}/reprocess`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['application', params.id] });
    },
  });

  const sendInterviewMutation = useMutation({
    mutationFn: async () => {
      await api.post(`/interviews`, { applicationId: params.id });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['application', params.id] });
    },
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin h-8 w-8 border-4 border-primary border-t-transparent rounded-full" />
      </div>
    );
  }

  if (!application) {
    return (
      <div className="text-center py-12">
        <p className="text-muted-foreground">Application not found</p>
        <Button variant="outline" onClick={() => router.back()} className="mt-4">
          Go Back
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-4">
          <Button variant="ghost" size="icon" onClick={() => router.back()}>
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div>
            <h1 className="text-2xl font-bold">{application.candidateName}</h1>
            <p className="text-muted-foreground">{application.candidateEmail}</p>
            {application.requisition && (
              <Link
                href={`/requisitions/${application.requisition.id}`}
                className="text-sm text-primary hover:underline flex items-center gap-1 mt-1"
              >
                {application.requisition.name}
                <ExternalLink className="h-3 w-3" />
              </Link>
            )}
          </div>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => reprocessMutation.mutate()}
            disabled={reprocessMutation.isPending}
          >
            <RefreshCw className={`h-4 w-4 mr-2 ${reprocessMutation.isPending ? 'animate-spin' : ''}`} />
            Reprocess
          </Button>
          {!application.interviewSent && (
            <Button
              onClick={() => sendInterviewMutation.mutate()}
              disabled={sendInterviewMutation.isPending}
            >
              <Mail className="h-4 w-4 mr-2" />
              Send Interview
            </Button>
          )}
        </div>
      </div>

      {/* Status Banner */}
      <Card className={`border-l-4 ${getStatusBorderColor(application.status)}`}>
        <CardContent className="flex items-center justify-between py-4">
          <div className="flex items-center gap-3">
            {getStatusIcon(application.status)}
            <div>
              <p className="font-medium">Status: {application.status.replace(/_/g, ' ')}</p>
              <p className="text-sm text-muted-foreground">
                {application.workdayStatus && `Workday: ${application.workdayStatus}`}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-4 text-sm text-muted-foreground">
            <span>Created {formatRelativeTime(application.createdAt)}</span>
            {application.interviewSent && (
              <span className="flex items-center gap-1 text-green-600">
                <Mail className="h-4 w-4" />
                Interview sent
              </span>
            )}
            {application.humanRequested && (
              <span className="flex items-center gap-1 text-yellow-600">
                <AlertCircle className="h-4 w-4" />
                Human requested
              </span>
            )}
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Analysis Section */}
        <div className="lg:col-span-2 space-y-6">
          {analysis ? (
            <>
              {/* Risk Score */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <FileText className="h-5 w-5" />
                    Resume Analysis
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center gap-6 mb-6">
                    <div className="text-center">
                      <div
                        className={`text-4xl font-bold ${getRiskColor(analysis.riskScore)}`}
                      >
                        {analysis.riskScore}
                      </div>
                      <p className="text-sm text-muted-foreground">Risk Score</p>
                    </div>
                    <div className="flex-1">
                      <p>{analysis.relevanceSummary}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Pros, Cons, Red Flags */}
              <div className="grid gap-4 md:grid-cols-3">
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm flex items-center gap-2 text-green-600">
                      <ThumbsUp className="h-4 w-4" />
                      Strengths
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ul className="space-y-1 text-sm">
                      {analysis.pros.map((pro, i) => (
                        <li key={i} className="flex items-start gap-2">
                          <CheckCircle className="h-4 w-4 text-green-500 mt-0.5 flex-shrink-0" />
                          {pro}
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
                      {analysis.cons.map((con, i) => (
                        <li key={i} className="flex items-start gap-2">
                          <AlertCircle className="h-4 w-4 text-orange-500 mt-0.5 flex-shrink-0" />
                          {con}
                        </li>
                      ))}
                    </ul>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm flex items-center gap-2 text-red-600">
                      <AlertTriangle className="h-4 w-4" />
                      Red Flags
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ul className="space-y-1 text-sm">
                      {analysis.redFlags.length > 0 ? (
                        analysis.redFlags.map((flag, i) => (
                          <li key={i} className="flex items-start gap-2">
                            <AlertTriangle className="h-4 w-4 text-red-500 mt-0.5 flex-shrink-0" />
                            {flag}
                          </li>
                        ))
                      ) : (
                        <li className="text-muted-foreground">No red flags identified</li>
                      )}
                    </ul>
                  </CardContent>
                </Card>
              </div>

              {/* Suggested Questions */}
              {analysis.suggestedQuestions.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm flex items-center gap-2">
                      <MessageSquare className="h-4 w-4" />
                      Suggested Interview Questions
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ol className="list-decimal list-inside space-y-2 text-sm">
                      {analysis.suggestedQuestions.map((q, i) => (
                        <li key={i}>{q}</li>
                      ))}
                    </ol>
                  </CardContent>
                </Card>
              )}
            </>
          ) : (
            <Card>
              <CardContent className="py-12 text-center">
                <FileText className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                <p className="text-muted-foreground">No analysis available yet</p>
                <Button
                  variant="outline"
                  className="mt-4"
                  onClick={() => reprocessMutation.mutate()}
                >
                  <RefreshCw className="h-4 w-4 mr-2" />
                  Run Analysis
                </Button>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Timeline & Actions Sidebar */}
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Timeline</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <TimelineItem
                  icon={<Clock className="h-4 w-4" />}
                  title="Application received"
                  time={application.createdAt}
                  done
                />
                {analysis && (
                  <TimelineItem
                    icon={<FileText className="h-4 w-4" />}
                    title="Resume analyzed"
                    time={analysis.createdAt}
                    done
                  />
                )}
                {application.interviewSentAt && (
                  <TimelineItem
                    icon={<Mail className="h-4 w-4" />}
                    title="Interview sent"
                    time={application.interviewSentAt}
                    done
                  />
                )}
                {application.status === 'interview_complete' && (
                  <TimelineItem
                    icon={<MessageSquare className="h-4 w-4" />}
                    title="Interview completed"
                    time={application.updatedAt}
                    done
                  />
                )}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Application IDs</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Internal</span>
                <span className="font-mono">{application.id}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Workday App</span>
                <span className="font-mono text-xs">{application.externalApplicationId}</span>
              </div>
              {application.externalCandidateId && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Workday Candidate</span>
                  <span className="font-mono text-xs">{application.externalCandidateId}</span>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

function TimelineItem({
  icon,
  title,
  time,
  done,
}: {
  icon: React.ReactNode;
  title: string;
  time: string;
  done?: boolean;
}) {
  return (
    <div className="flex gap-3">
      <div
        className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
          done ? 'bg-green-100 text-green-600' : 'bg-muted text-muted-foreground'
        }`}
      >
        {icon}
      </div>
      <div>
        <p className="text-sm font-medium">{title}</p>
        <p className="text-xs text-muted-foreground">{formatDateTime(time)}</p>
      </div>
    </div>
  );
}

function getStatusIcon(status: string) {
  switch (status) {
    case 'new':
      return <Clock className="h-5 w-5 text-blue-500" />;
    case 'analyzed':
      return <FileText className="h-5 w-5 text-purple-500" />;
    case 'interview_pending':
      return <Mail className="h-5 w-5 text-yellow-500" />;
    case 'interview_complete':
      return <MessageSquare className="h-5 w-5 text-green-500" />;
    case 'complete':
      return <CheckCircle className="h-5 w-5 text-gray-500" />;
    default:
      return <Clock className="h-5 w-5 text-muted-foreground" />;
  }
}

function getStatusBorderColor(status: string): string {
  const colors: Record<string, string> = {
    new: 'border-l-blue-500',
    analyzed: 'border-l-purple-500',
    interview_pending: 'border-l-yellow-500',
    interview_complete: 'border-l-green-500',
    complete: 'border-l-gray-500',
  };
  return colors[status] || 'border-l-gray-300';
}

function getRiskColor(score: number | null): string {
  if (score === null) return 'text-muted-foreground';
  if (score <= 3) return 'text-green-600';
  if (score <= 6) return 'text-yellow-600';
  return 'text-red-600';
}
