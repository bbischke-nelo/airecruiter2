'use client';

import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import Link from 'next/link';
import {
  Activity,
  Filter,
  RefreshCw,
  CheckCircle,
  MessageSquare,
  FileText,
  AlertCircle,
  TrendingUp,
  Mail,
  Upload,
  ExternalLink,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { api } from '@/lib/api';
import { formatDateTime, formatRelativeTime } from '@/lib/utils';

interface ActivityItem {
  id: number;
  action: string;
  applicationId: number | null;
  requisitionId: number | null;
  recruiterId: number | null;
  details: Record<string, unknown> | null;
  createdAt: string;
  // Joined data
  candidateName?: string;
  requisitionName?: string;
}

interface PaginatedResponse {
  data: ActivityItem[];
  meta: {
    page: number;
    perPage: number;
    total: number;
    totalPages: number;
  };
}

type ActionFilter = 'all' | 'analysis' | 'interview' | 'evaluation' | 'report' | 'status';

export default function LogsPage() {
  const [page, setPage] = useState(1);
  const [actionFilter, setActionFilter] = useState<ActionFilter>('all');
  const [searchQuery, setSearchQuery] = useState('');

  const { data, isLoading, error, refetch } = useQuery<PaginatedResponse>({
    queryKey: ['logs', page, actionFilter, searchQuery],
    queryFn: async () => {
      const params = new URLSearchParams();
      params.set('page', page.toString());
      params.set('per_page', '25');
      if (actionFilter !== 'all') {
        params.set('action', actionFilter);
      }
      if (searchQuery) {
        params.set('search', searchQuery);
      }
      const response = await api.get(`/logs?${params.toString()}`);
      return response.data;
    },
  });

  const actionFilters: { value: ActionFilter; label: string; icon: React.ReactNode }[] = [
    { value: 'all', label: 'All', icon: <Activity className="h-4 w-4" /> },
    { value: 'analysis', label: 'Analysis', icon: <FileText className="h-4 w-4" /> },
    { value: 'interview', label: 'Interview', icon: <MessageSquare className="h-4 w-4" /> },
    { value: 'evaluation', label: 'Evaluation', icon: <TrendingUp className="h-4 w-4" /> },
    { value: 'report', label: 'Report', icon: <Upload className="h-4 w-4" /> },
    { value: 'status', label: 'Status', icon: <CheckCircle className="h-4 w-4" /> },
  ];

  if (error) {
    return (
      <div className="text-center py-12">
        <p className="text-destructive">Failed to load activity logs</p>
        <Button variant="outline" onClick={() => refetch()} className="mt-4">
          Retry
        </Button>
      </div>
    );
  }

  const activities = data?.data || [];

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Activity Log</h1>
          <p className="text-muted-foreground">
            {data?.meta.total || 0} total events
          </p>
        </div>
        <Button variant="outline" onClick={() => refetch()}>
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Filters */}
      <div className="flex flex-col md:flex-row gap-4 mb-6">
        <div className="flex gap-2 overflow-x-auto pb-2">
          {actionFilters.map((filter) => (
            <Button
              key={filter.value}
              variant={actionFilter === filter.value ? 'default' : 'outline'}
              size="sm"
              onClick={() => {
                setActionFilter(filter.value);
                setPage(1);
              }}
              className="flex items-center gap-2 whitespace-nowrap"
            >
              {filter.icon}
              {filter.label}
            </Button>
          ))}
        </div>
        <div className="flex-1 max-w-sm">
          <Input
            placeholder="Search by candidate or requisition..."
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setPage(1);
            }}
          />
        </div>
      </div>

      {/* Activity List */}
      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="p-8">
              <div className="space-y-4">
                {[1, 2, 3, 4, 5].map((i) => (
                  <div key={i} className="animate-pulse flex gap-4">
                    <div className="h-10 w-10 bg-muted rounded-full" />
                    <div className="flex-1 space-y-2">
                      <div className="h-4 bg-muted rounded w-3/4" />
                      <div className="h-3 bg-muted rounded w-1/2" />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : activities.length === 0 ? (
            <div className="py-12 text-center">
              <Activity className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
              <p className="text-muted-foreground">No activity found</p>
              {(actionFilter !== 'all' || searchQuery) && (
                <Button
                  variant="outline"
                  className="mt-4"
                  onClick={() => {
                    setActionFilter('all');
                    setSearchQuery('');
                  }}
                >
                  Clear Filters
                </Button>
              )}
            </div>
          ) : (
            <div className="divide-y">
              {activities.map((activity) => (
                <div
                  key={activity.id}
                  className="flex items-start gap-4 p-4 hover:bg-muted/50 transition-colors"
                >
                  <div
                    className={`flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center ${getActionBgColor(
                      activity.action
                    )}`}
                  >
                    {getActionIcon(activity.action)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <p className="font-medium">{formatAction(activity.action)}</p>
                        <p className="text-sm text-muted-foreground">
                          {activity.candidateName && (
                            <>
                              <span>{activity.candidateName}</span>
                              {activity.requisitionName && <span> - </span>}
                            </>
                          )}
                          {activity.requisitionName && (
                            <span>{activity.requisitionName}</span>
                          )}
                        </p>
                        {activity.details && (
                          <p className="text-xs text-muted-foreground mt-1">
                            {formatDetails(activity.details)}
                          </p>
                        )}
                      </div>
                      <div className="flex items-center gap-2 flex-shrink-0">
                        <span className="text-sm text-muted-foreground whitespace-nowrap">
                          {formatRelativeTime(activity.createdAt)}
                        </span>
                        {activity.applicationId && (
                          <Link href={`/applications/${activity.applicationId}`}>
                            <Button variant="ghost" size="icon" className="h-8 w-8">
                              <ExternalLink className="h-4 w-4" />
                            </Button>
                          </Link>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Pagination */}
      {data && data.meta.totalPages > 1 && (
        <div className="flex items-center justify-between mt-6">
          <p className="text-sm text-muted-foreground">
            Showing {(page - 1) * 25 + 1} to {Math.min(page * 25, data.meta.total)} of{' '}
            {data.meta.total}
          </p>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
            >
              <ChevronLeft className="h-4 w-4" />
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((p) => Math.min(data.meta.totalPages, p + 1))}
              disabled={page === data.meta.totalPages}
            >
              Next
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

function getActionIcon(action: string) {
  switch (action) {
    case 'analysis_completed':
      return <FileText className="h-5 w-5 text-purple-600" />;
    case 'interview_sent':
      return <Mail className="h-5 w-5 text-blue-600" />;
    case 'interview_started':
    case 'interview_completed':
      return <MessageSquare className="h-5 w-5 text-green-600" />;
    case 'evaluation_completed':
      return <TrendingUp className="h-5 w-5 text-indigo-600" />;
    case 'report_generated':
    case 'report_uploaded':
      return <Upload className="h-5 w-5 text-teal-600" />;
    case 'status_changed':
      return <CheckCircle className="h-5 w-5 text-orange-600" />;
    case 'human_requested':
      return <AlertCircle className="h-5 w-5 text-yellow-600" />;
    default:
      return <Activity className="h-5 w-5 text-muted-foreground" />;
  }
}

function getActionBgColor(action: string): string {
  switch (action) {
    case 'analysis_completed':
      return 'bg-purple-100 dark:bg-purple-900';
    case 'interview_sent':
      return 'bg-blue-100 dark:bg-blue-900';
    case 'interview_started':
    case 'interview_completed':
      return 'bg-green-100 dark:bg-green-900';
    case 'evaluation_completed':
      return 'bg-indigo-100 dark:bg-indigo-900';
    case 'report_generated':
    case 'report_uploaded':
      return 'bg-teal-100 dark:bg-teal-900';
    case 'status_changed':
      return 'bg-orange-100 dark:bg-orange-900';
    case 'human_requested':
      return 'bg-yellow-100 dark:bg-yellow-900';
    default:
      return 'bg-muted';
  }
}

function formatAction(action: string): string {
  const map: Record<string, string> = {
    // Sync actions
    sync_completed: 'Sync Completed',
    requisition_synced: 'Requisition Synced',
    application_created: 'Application Created',
    workday_status_changed: 'Workday Status Changed',
    // Analysis/extraction
    analysis_completed: 'Resume Analyzed',
    facts_extracted: 'Facts Extracted',
    extraction_failed: 'Extraction Failed',
    // Interview
    interview_sent: 'Interview Invite Sent',
    interview_started: 'Interview Started',
    interview_completed: 'Interview Completed',
    evaluation_completed: 'Interview Evaluated',
    human_requested: 'Human Review Requested',
    // Report
    report_generated: 'Report Generated',
    report_uploaded: 'Report Uploaded',
    // HITL decisions
    application_advanced: 'Application Advanced',
    application_rejected: 'Application Rejected',
    application_held: 'Application Held',
    application_unheld: 'Application Unheld',
    // Status
    status_changed: 'Status Changed',
  };
  // Fallback: convert snake_case to Title Case
  return map[action] || action
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

function formatDetails(details: Record<string, unknown>): string {
  const parts: string[] = [];

  if (details.risk_score !== undefined) {
    parts.push(`Risk: ${details.risk_score}`);
  }
  if (details.overall_score !== undefined) {
    parts.push(`Score: ${details.overall_score}`);
  }
  if (details.recommendation) {
    parts.push(`${details.recommendation}`);
  }
  if (details.from_status && details.to_status) {
    parts.push(`${details.from_status} → ${details.to_status}`);
  }

  return parts.join(' | ');
}
