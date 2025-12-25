'use client';

import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { useState, useMemo } from 'react';
import {
  RefreshCw,
  Search,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
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

interface Application {
  id: number;
  externalApplicationId: string;
  candidateName: string;
  candidateEmail: string;
  requisitionId: number;
  requisitionName: string;
  status: string;
  workdayStatus: string;
  hasAnalysis: boolean;
  hasInterview: boolean;
  hasReport: boolean;
  riskScore: number | null;
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
  analyzing: 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200',
  analyzed: 'bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-200',
  interview_pending: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
  interview_complete: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
  complete: 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200',
  error: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
};

const statusLabels: Record<string, string> = {
  new: 'New',
  analyzing: 'Analyzing',
  analyzed: 'Analyzed',
  interview_pending: 'Interview Pending',
  interview_complete: 'Interview Complete',
  complete: 'Complete',
  error: 'Error',
};

const PAGE_SIZE_OPTIONS = [10, 20, 50, 100];

export default function ApplicationsPage() {
  // Filter state
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState<string>('');
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(20);

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

  const applications = data?.data || [];
  const meta = data?.meta || { page: 1, perPage: 20, total: 0, totalPages: 1 };

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
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="All Statuses" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Statuses</SelectItem>
            <SelectItem value="new">New</SelectItem>
            <SelectItem value="analyzing">Analyzing</SelectItem>
            <SelectItem value="analyzed">Analyzed</SelectItem>
            <SelectItem value="interview_pending">Interview Pending</SelectItem>
            <SelectItem value="interview_complete">Interview Complete</SelectItem>
            <SelectItem value="complete">Complete</SelectItem>
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
            <table className="w-full">
              <thead className="bg-muted">
                <tr>
                  <th className="px-4 py-3 text-left text-sm font-medium">Application ID</th>
                  <th className="px-4 py-3 text-left text-sm font-medium">Candidate</th>
                  <th className="px-4 py-3 text-left text-sm font-medium">Position</th>
                  <th className="px-4 py-3 text-left text-sm font-medium">Status</th>
                  <th className="px-4 py-3 text-left text-sm font-medium">Risk</th>
                  <th className="px-4 py-3 text-left text-sm font-medium">Applied</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {applications.map((app) => (
                  <tr key={app.id} className="hover:bg-muted/50">
                    <td className="px-4 py-3">
                      <Link href={`/applications/${app.id}`} className="hover:underline">
                        <span className="font-mono text-sm">{app.externalApplicationId}</span>
                      </Link>
                    </td>
                    <td className="px-4 py-3">
                      <Link href={`/applications/${app.id}`} className="hover:underline">
                        <div className="font-medium">{app.candidateName}</div>
                        <div className="text-sm text-muted-foreground">{app.candidateEmail}</div>
                      </Link>
                    </td>
                    <td className="px-4 py-3">
                      <Link href={`/requisitions/${app.requisitionId}`} className="text-sm hover:underline">
                        {app.requisitionName}
                      </Link>
                    </td>
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
                      {app.riskScore !== null ? (
                        <span
                          className={cn(
                            'px-2 py-1 text-xs rounded-full',
                            app.riskScore <= 3
                              ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                              : app.riskScore <= 6
                                ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200'
                                : 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
                          )}
                        >
                          {app.riskScore}/10
                        </span>
                      ) : (
                        <span className="text-muted-foreground text-sm">-</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-sm text-muted-foreground">
                      {formatRelativeTime(app.createdAt)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
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
    </div>
  );
}
