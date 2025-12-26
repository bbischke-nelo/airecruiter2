'use client';

import { useQuery } from '@tanstack/react-query';
import { useState, useMemo } from 'react';
import {
  RefreshCw,
  Search,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  AlertCircle,
  Clock,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
import { Progress } from '@/components/ui/progress';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { api } from '@/lib/api';
import { formatRelativeTime, cn } from '@/lib/utils';
import { useDebounce } from '@/hooks/use-debounce';
import { ApplicationDrawer } from '@/components/applications/ApplicationDrawer';

interface Application {
  id: number;
  externalApplicationId: string;
  candidateName: string;
  candidateEmail: string | null;
  requisitionId: number;
  requisitionName: string;
  status: string;
  workdayStatus: string | null;
  hasAnalysis: boolean;
  hasInterview: boolean;
  hasReport: boolean;
  jdMatchPercentage: number | null;
  avgTenureMonths: number | null;
  humanRequested: boolean;
  complianceReview: boolean;
  rejectionReasonCode: string | null;
  createdAt: string;
}

interface PaginatedResponse {
  data: Application[];
  meta: {
    page: number;
    perPage: number;
    total: number;
    totalPages: number;
  };
}

const statusColors: Record<string, string> = {
  new: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
  downloading: 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200',
  downloaded: 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200',
  extracting: 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200',
  extracted: 'bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-200',
  generating_summary: 'bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-200',
  ready_for_review: 'bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200',
  advancing: 'bg-cyan-100 text-cyan-800 dark:bg-cyan-900 dark:text-cyan-200',
  interview_sending: 'bg-cyan-100 text-cyan-800 dark:bg-cyan-900 dark:text-cyan-200',
  interview_sent: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
  interview_received: 'bg-lime-100 text-lime-800 dark:bg-lime-900 dark:text-lime-200',
  transcribing: 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200',
  interview_ready_for_review: 'bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200',
  advanced: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
  live_interview_pending: 'bg-teal-100 text-teal-800 dark:bg-teal-900 dark:text-teal-200',
  rejected: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
  on_hold: 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200',
  error: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
};

const statusLabels: Record<string, string> = {
  new: 'New',
  downloading: 'Downloading',
  downloaded: 'Downloaded',
  extracting: 'Extracting',
  extracted: 'Extracted',
  generating_summary: 'Generating',
  ready_for_review: 'Ready for Review',
  advancing: 'Advancing',
  interview_sending: 'Sending Interview',
  interview_sent: 'Interview Sent',
  interview_received: 'Interview Received',
  transcribing: 'Transcribing',
  interview_ready_for_review: 'Interview Ready',
  advanced: 'Advanced',
  live_interview_pending: 'Live Interview',
  rejected: 'Rejected',
  on_hold: 'On Hold',
  error: 'Error',
};

// Statuses that need human attention
const REVIEW_STATUSES = ['ready_for_review', 'interview_ready_for_review'];

const PAGE_SIZE_OPTIONS = [10, 20, 50, 100];

export default function ApplicationsPage() {
  // Filter state
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState<string>('');
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(20);

  // Selection state
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

  // Drawer state
  const [selectedApp, setSelectedApp] = useState<Application | null>(null);

  // Debounce search
  const debouncedSearch = useDebounce(search, 300);

  // Build query params
  const queryParams = useMemo(() => {
    const params = new URLSearchParams();
    params.set('page', page.toString());
    params.set('per_page', perPage.toString());
    if (debouncedSearch) params.set('search', debouncedSearch);
    if (status) params.set('status', status);
    return params.toString();
  }, [page, perPage, debouncedSearch, status]);

  const { data, isLoading, error, refetch } = useQuery<PaginatedResponse>({
    queryKey: ['applications', queryParams],
    queryFn: async () => {
      const response = await api.get(`/applications?${queryParams}`);
      return response.data;
    },
  });

  // Reset to page 1 when search or filter changes
  const handleSearchChange = (value: string) => {
    setSearch(value);
    setPage(1);
  };

  const handleStatusChange = (value: string) => {
    setStatus(value === 'all' ? '' : value);
    setPage(1);
  };

  const handlePerPageChange = (value: string) => {
    setPerPage(parseInt(value, 10));
    setPage(1);
  };

  // Selection handlers
  const toggleSelection = (id: number) => {
    const newSelected = new Set(selectedIds);
    if (newSelected.has(id)) {
      newSelected.delete(id);
    } else {
      newSelected.add(id);
    }
    setSelectedIds(newSelected);
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === applications.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(applications.map((a) => a.id)));
    }
  };

  const applications = data?.data || [];
  const meta = data?.meta || { page: 1, perPage: 20, total: 0, totalPages: 1 };

  // Count items needing review
  const needsReviewCount = applications.filter((a) => REVIEW_STATUSES.includes(a.status)).length;

  // Calculate display range
  const startItem = meta.total === 0 ? 0 : (meta.page - 1) * meta.perPage + 1;
  const endItem = Math.min(meta.page * meta.perPage, meta.total);

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Applications</h1>
          <p className="text-muted-foreground">
            {meta.total} total application{meta.total !== 1 ? 's' : ''}
            {needsReviewCount > 0 && (
              <span className="ml-2 text-amber-600 dark:text-amber-400">
                ({needsReviewCount} need{needsReviewCount === 1 ? 's' : ''} review)
              </span>
            )}
          </p>
        </div>
        <Button variant="outline" onClick={() => refetch()} disabled={isLoading}>
          <RefreshCw className={`h-4 w-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-4 mb-6">
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search candidates..."
            value={search}
            onChange={(e) => handleSearchChange(e.target.value)}
            className="pl-10"
          />
        </div>
        <Select value={status || 'all'} onValueChange={handleStatusChange}>
          <SelectTrigger className="w-[200px]">
            <SelectValue placeholder="All Statuses" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Statuses</SelectItem>
            <SelectItem value="ready_for_review">Ready for Review</SelectItem>
            <SelectItem value="interview_ready_for_review">Interview Ready</SelectItem>
            <SelectItem value="on_hold">On Hold</SelectItem>
            <SelectItem value="new">New</SelectItem>
            <SelectItem value="extracting">Processing</SelectItem>
            <SelectItem value="interview_sent">Interview Sent</SelectItem>
            <SelectItem value="advanced">Advanced</SelectItem>
            <SelectItem value="rejected">Rejected</SelectItem>
            <SelectItem value="error">Error</SelectItem>
          </SelectContent>
        </Select>
        <div className="flex items-center gap-2 ml-auto">
          <Label className="text-sm text-muted-foreground">Show:</Label>
          <Select value={perPage.toString()} onValueChange={handlePerPageChange}>
            <SelectTrigger className="w-[80px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {PAGE_SIZE_OPTIONS.map((size) => (
                <SelectItem key={size} value={size.toString()}>
                  {size}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin h-8 w-8 border-4 border-primary border-t-transparent rounded-full" />
        </div>
      ) : error ? (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-destructive">Failed to load applications</p>
            <Button variant="outline" onClick={() => refetch()} className="mt-4">
              Retry
            </Button>
          </CardContent>
        </Card>
      ) : applications.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-muted-foreground">
              {search || status ? 'No applications match your filters' : 'No applications found'}
            </p>
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="rounded-lg border overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[800px]">
                <thead className="bg-muted">
                  <tr>
                    <th scope="col" className="w-12 px-4 py-3">
                      <Checkbox
                        checked={selectedIds.size === applications.length}
                        indeterminate={selectedIds.size > 0 && selectedIds.size < applications.length}
                        onCheckedChange={toggleSelectAll}
                      />
                    </th>
                    <th scope="col" className="px-4 py-3 text-left text-sm font-medium">Candidate</th>
                    <th scope="col" className="px-4 py-3 text-left text-sm font-medium hidden sm:table-cell">Position</th>
                    <th scope="col" className="px-4 py-3 text-left text-sm font-medium">Status</th>
                    <th scope="col" className="px-4 py-3 text-left text-sm font-medium w-32">JD Match</th>
                    <th scope="col" className="px-4 py-3 text-left text-sm font-medium hidden lg:table-cell">Tenure</th>
                    <th scope="col" className="px-4 py-3 text-left text-sm font-medium hidden md:table-cell">Applied</th>
                  </tr>
                </thead>
              <tbody className="divide-y">
                {applications.map((app) => (
                  <tr
                    key={app.id}
                    onClick={() => setSelectedApp(app)}
                    className={cn(
                      'hover:bg-muted/50 cursor-pointer',
                      REVIEW_STATUSES.includes(app.status) && 'bg-amber-50 dark:bg-amber-950/20',
                      selectedIds.has(app.id) && 'bg-primary/5'
                    )}
                  >
                    <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
                      <Checkbox
                        checked={selectedIds.has(app.id)}
                        onCheckedChange={() => toggleSelection(app.id)}
                      />
                    </td>
                    <td className="px-4 py-3">
                      <div className="font-medium flex items-center gap-2">
                        {app.candidateName}
                        {app.humanRequested && (
                          <span title="Human review requested">
                            <AlertCircle className="h-4 w-4 text-amber-500" />
                          </span>
                        )}
                        {app.status === 'on_hold' && (
                          <span title="On hold">
                            <Clock className="h-4 w-4 text-gray-500" />
                          </span>
                        )}
                      </div>
                      <div className="text-sm text-muted-foreground">{app.candidateEmail}</div>
                    </td>
                    <td className="px-4 py-3 text-sm hidden sm:table-cell">{app.requisitionName}</td>
                    <td className="px-4 py-3">
                      <span
                        className={cn(
                          'px-2 py-1 text-xs rounded-full',
                          statusColors[app.status] || 'bg-gray-100 text-gray-800'
                        )}
                      >
                        {statusLabels[app.status] || app.status}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {app.jdMatchPercentage !== null ? (
                        <div className="flex items-center gap-2">
                          <Progress value={app.jdMatchPercentage} className="h-2 w-16" />
                          <span className="text-xs text-muted-foreground">{app.jdMatchPercentage}%</span>
                        </div>
                      ) : (
                        <span className="text-muted-foreground text-sm">-</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-sm hidden lg:table-cell">
                      {app.avgTenureMonths !== null ? (
                        <span>{Math.round(app.avgTenureMonths)} mo</span>
                      ) : (
                        <span className="text-muted-foreground">-</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-sm text-muted-foreground hidden md:table-cell">
                      {formatRelativeTime(app.createdAt)}
                    </td>
                  </tr>
                ))}
              </tbody>
              </table>
            </div>
          </div>

          {/* Pagination */}
          {meta.totalPages > 1 && (
            <div className="flex items-center justify-between mt-6 pt-4 border-t">
              <p className="text-sm text-muted-foreground">
                Showing {startItem}-{endItem} of {meta.total}
              </p>
              <div className="flex items-center gap-1">
                <Button
                  variant="outline"
                  size="icon"
                  onClick={() => setPage(1)}
                  disabled={page === 1}
                  title="First page"
                >
                  <ChevronsLeft className="h-4 w-4" />
                </Button>
                <Button
                  variant="outline"
                  size="icon"
                  onClick={() => setPage(page - 1)}
                  disabled={page === 1}
                  title="Previous page"
                >
                  <ChevronLeft className="h-4 w-4" />
                </Button>
                <span className="px-3 py-2 text-sm">
                  Page {meta.page} of {meta.totalPages}
                </span>
                <Button
                  variant="outline"
                  size="icon"
                  onClick={() => setPage(page + 1)}
                  disabled={page === meta.totalPages}
                  title="Next page"
                >
                  <ChevronRight className="h-4 w-4" />
                </Button>
                <Button
                  variant="outline"
                  size="icon"
                  onClick={() => setPage(meta.totalPages)}
                  disabled={page === meta.totalPages}
                  title="Last page"
                >
                  <ChevronsRight className="h-4 w-4" />
                </Button>
              </div>
            </div>
          )}
        </>
      )}

      {/* Application Drawer */}
      <ApplicationDrawer
        application={selectedApp}
        applications={applications}
        onClose={() => setSelectedApp(null)}
        onNavigate={setSelectedApp}
      />
    </div>
  );
}
