'use client';

import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { useState } from 'react';
import {
  MessageSquare,
  Clock,
  CheckCircle,
  XCircle,
  AlertCircle,
  Filter,
  ExternalLink,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { api } from '@/lib/api';
import { formatDateTime, formatRelativeTime } from '@/lib/utils';
import { Interview } from '@/types';

interface InterviewWithDetails extends Interview {
  application?: {
    id: number;
    candidateName: string;
    candidateEmail: string;
  };
  evaluation?: {
    overallScore: number;
    recommendation: string;
  };
}

interface PaginatedResponse {
  data: InterviewWithDetails[];
  meta: {
    page: number;
    perPage: number;
    total: number;
    totalPages: number;
  };
}

type StatusFilter = 'all' | 'scheduled' | 'in_progress' | 'completed' | 'abandoned';

export default function InterviewsPage() {
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');

  const { data, isLoading, error, refetch } = useQuery<PaginatedResponse>({
    queryKey: ['interviews', statusFilter],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (statusFilter !== 'all') {
        params.set('status', statusFilter);
      }
      const response = await api.get(`/interviews?${params.toString()}`);
      return response.data;
    },
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin h-8 w-8 border-4 border-primary border-t-transparent rounded-full" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-12">
        <p className="text-destructive">Failed to load interviews</p>
        <Button variant="outline" onClick={() => refetch()} className="mt-4">
          Retry
        </Button>
      </div>
    );
  }

  const interviews = data?.data || [];

  const statusFilters: { value: StatusFilter; label: string; icon: React.ReactNode }[] = [
    { value: 'all', label: 'All', icon: <MessageSquare className="h-4 w-4" /> },
    { value: 'scheduled', label: 'Scheduled', icon: <Clock className="h-4 w-4" /> },
    { value: 'in_progress', label: 'In Progress', icon: <AlertCircle className="h-4 w-4" /> },
    { value: 'completed', label: 'Completed', icon: <CheckCircle className="h-4 w-4" /> },
    { value: 'abandoned', label: 'Abandoned', icon: <XCircle className="h-4 w-4" /> },
  ];

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Interviews</h1>
          <p className="text-muted-foreground">
            {data?.meta.total || 0} total interviews
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-2 mb-6 overflow-x-auto pb-2">
        {statusFilters.map((filter) => (
          <Button
            key={filter.value}
            variant={statusFilter === filter.value ? 'default' : 'outline'}
            size="sm"
            onClick={() => setStatusFilter(filter.value)}
            className="flex items-center gap-2"
          >
            {filter.icon}
            {filter.label}
          </Button>
        ))}
      </div>

      {interviews.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <MessageSquare className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <p className="text-muted-foreground">No interviews found</p>
            {statusFilter !== 'all' && (
              <Button
                variant="outline"
                className="mt-4"
                onClick={() => setStatusFilter('all')}
              >
                Clear Filter
              </Button>
            )}
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {interviews.map((interview) => (
            <Link key={interview.id} href={`/interviews/${interview.id}`}>
              <Card className="hover:shadow-md transition-shadow cursor-pointer">
                <CardContent className="flex items-center justify-between py-4">
                  <div className="flex items-center gap-4">
                    <div
                      className={`w-10 h-10 rounded-full flex items-center justify-center ${getStatusBgColor(
                        interview.status
                      )}`}
                    >
                      {getStatusIcon(interview.status)}
                    </div>
                    <div>
                      <p className="font-medium">
                        {interview.application?.candidateName || `Interview #${interview.id}`}
                      </p>
                      <p className="text-sm text-muted-foreground">
                        {interview.application?.candidateEmail}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-6">
                    {interview.evaluation && (
                      <div className="text-right">
                        <p className="text-lg font-bold">
                          {interview.evaluation.overallScore}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {formatRecommendation(interview.evaluation.recommendation)}
                        </p>
                      </div>
                    )}

                    <div className="text-right text-sm">
                      <p
                        className={`px-2 py-1 rounded-full text-xs ${getStatusColor(
                          interview.status
                        )}`}
                      >
                        {interview.status.replace(/_/g, ' ')}
                      </p>
                      <p className="text-muted-foreground mt-1">
                        {interview.completedAt
                          ? `Completed ${formatRelativeTime(interview.completedAt)}`
                          : interview.startedAt
                          ? `Started ${formatRelativeTime(interview.startedAt)}`
                          : `Created ${formatRelativeTime(interview.createdAt)}`}
                      </p>
                    </div>

                    <ExternalLink className="h-4 w-4 text-muted-foreground" />
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}

      {/* Pagination */}
      {data && data.meta.totalPages > 1 && (
        <div className="flex justify-center gap-2 mt-6">
          {Array.from({ length: data.meta.totalPages }, (_, i) => (
            <Button
              key={i + 1}
              variant={data.meta.page === i + 1 ? 'default' : 'outline'}
              size="sm"
            >
              {i + 1}
            </Button>
          ))}
        </div>
      )}
    </div>
  );
}

function getStatusIcon(status: string) {
  switch (status) {
    case 'scheduled':
      return <Clock className="h-5 w-5 text-blue-600" />;
    case 'in_progress':
      return <AlertCircle className="h-5 w-5 text-yellow-600" />;
    case 'completed':
      return <CheckCircle className="h-5 w-5 text-green-600" />;
    case 'abandoned':
      return <XCircle className="h-5 w-5 text-red-600" />;
    default:
      return <Clock className="h-5 w-5 text-muted-foreground" />;
  }
}

function getStatusBgColor(status: string): string {
  const colors: Record<string, string> = {
    scheduled: 'bg-blue-100 dark:bg-blue-900',
    in_progress: 'bg-yellow-100 dark:bg-yellow-900',
    completed: 'bg-green-100 dark:bg-green-900',
    abandoned: 'bg-red-100 dark:bg-red-900',
  };
  return colors[status] || 'bg-muted';
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
