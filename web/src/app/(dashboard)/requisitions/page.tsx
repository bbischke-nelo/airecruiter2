'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import Link from 'next/link';
import { useState, useMemo } from 'react';
import {
  RefreshCw,
  MapPin,
  Users,
  Loader2,
  Search,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { api } from '@/lib/api';
import { formatRelativeTime } from '@/lib/utils';
import { useToast } from '@/hooks/use-toast';
import { useDebounce } from '@/hooks/use-debounce';

interface Requisition {
  id: number;
  externalId: string;
  name: string;
  description: string;
  location: string;
  recruiterName: string | null;
  isActive: boolean;
  autoSendInterview: boolean;
  applicationCount: number;
  pendingCount: number;
  lastSyncedAt: string | null;
  createdAt: string;
}

interface PaginatedResponse {
  data: Requisition[];
  meta: {
    page: number;
    perPage: number;
    total: number;
    totalPages: number;
  };
}

const PAGE_SIZE_OPTIONS = [10, 20, 50, 100];

export default function RequisitionsPage() {
  const queryClient = useQueryClient();
  const { toast } = useToast();

  // Filter state
  const [search, setSearch] = useState('');
  const [showInactive, setShowInactive] = useState(false);
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(20);

  // Debounce search to avoid too many API calls
  const debouncedSearch = useDebounce(search, 300);

  // Build query params
  const queryParams = useMemo(() => {
    const params = new URLSearchParams();
    params.set('page', page.toString());
    params.set('per_page', perPage.toString());
    if (debouncedSearch) params.set('search', debouncedSearch);
    if (!showInactive) params.set('is_active', 'true');
    return params.toString();
  }, [page, perPage, debouncedSearch, showInactive]);

  const { data, isLoading, error, refetch } = useQuery<PaginatedResponse>({
    queryKey: ['requisitions', queryParams],
    queryFn: async () => {
      const response = await api.get(`/requisitions?${queryParams}`);
      return response.data;
    },
  });

  const syncAllMutation = useMutation({
    mutationFn: async () => {
      const response = await api.post('/requisitions/sync');
      return response.data;
    },
    onSuccess: (data) => {
      toast({
        title: 'Sync job queued',
        description: data.message || 'All requisitions will be synced shortly',
      });
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: ['requisitions'] });
      }, 2000);
    },
    onError: (error: any) => {
      toast({
        title: 'Sync failed',
        description: error.response?.data?.message || 'Failed to start sync',
        variant: 'destructive',
      });
    },
  });

  // Reset to page 1 when search or filter changes
  const handleSearchChange = (value: string) => {
    setSearch(value);
    setPage(1);
  };

  const handleShowInactiveChange = (value: boolean) => {
    setShowInactive(value);
    setPage(1);
  };

  const handlePerPageChange = (value: string) => {
    setPerPage(parseInt(value, 10));
    setPage(1);
  };

  const requisitions = data?.data || [];
  const meta = data?.meta || { page: 1, perPage: 20, total: 0, totalPages: 1 };

  // Calculate display range
  const startItem = (meta.page - 1) * meta.perPage + 1;
  const endItem = Math.min(meta.page * meta.perPage, meta.total);

  if (error) {
    return (
      <div className="text-center py-12">
        <p className="text-destructive">Failed to load requisitions</p>
        <Button variant="outline" onClick={() => refetch()} className="mt-4">
          Retry
        </Button>
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Requisitions</h1>
          <p className="text-muted-foreground">
            {meta.total} total requisition{meta.total !== 1 ? 's' : ''}
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => refetch()} disabled={isLoading}>
            <RefreshCw className={`h-4 w-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          <Button
            onClick={() => syncAllMutation.mutate()}
            disabled={syncAllMutation.isPending}
          >
            {syncAllMutation.isPending ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4 mr-2" />
            )}
            Sync All
          </Button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-4 mb-6">
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search requisitions..."
            value={search}
            onChange={(e) => handleSearchChange(e.target.value)}
            className="pl-10"
          />
        </div>
        <div className="flex items-center gap-2">
          <Switch
            id="show-inactive"
            checked={showInactive}
            onCheckedChange={handleShowInactiveChange}
          />
          <Label htmlFor="show-inactive" className="text-sm cursor-pointer">
            Show inactive
          </Label>
        </div>
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
      ) : requisitions.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-muted-foreground">
              {search || !showInactive
                ? 'No requisitions match your filters'
                : 'No requisitions found'}
            </p>
            {!search && !showInactive && (
              <>
                <p className="text-sm text-muted-foreground mt-2">
                  Click &quot;Sync All&quot; to fetch requisitions from your TMS
                </p>
                <Button
                  className="mt-4"
                  onClick={() => syncAllMutation.mutate()}
                  disabled={syncAllMutation.isPending}
                >
                  {syncAllMutation.isPending ? (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <RefreshCw className="h-4 w-4 mr-2" />
                  )}
                  Sync All
                </Button>
              </>
            )}
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {requisitions.map((req) => (
              <Link key={req.id} href={`/requisitions/${req.id}`}>
                <Card className="hover:shadow-md transition-shadow cursor-pointer h-full">
                  <CardHeader className="pb-2">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0 flex-1">
                        <p className="text-xs font-mono text-muted-foreground mb-1">
                          {req.externalId}
                        </p>
                        <CardTitle className="text-lg line-clamp-2">
                          {req.name}
                        </CardTitle>
                      </div>
                      <span
                        className={`px-2 py-1 text-xs rounded-full whitespace-nowrap ${
                          req.isActive
                            ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                            : 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200'
                        }`}
                      >
                        {req.isActive ? 'Active' : 'Inactive'}
                      </span>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-muted-foreground">
                      {req.location && (
                        <span className="flex items-center gap-1">
                          <MapPin className="h-4 w-4 flex-shrink-0" />
                          <span className="truncate">{req.location}</span>
                        </span>
                      )}
                      <span className="flex items-center gap-1">
                        <Users className="h-4 w-4 flex-shrink-0" />
                        {req.applicationCount || 0} application{req.applicationCount !== 1 ? 's' : ''}
                        {req.pendingCount > 0 && (
                          <span className="text-yellow-600 dark:text-yellow-400">
                            ({req.pendingCount} pending)
                          </span>
                        )}
                      </span>
                    </div>
                    {req.recruiterName && (
                      <p className="text-sm text-muted-foreground mt-2">
                        Recruiter: {req.recruiterName}
                      </p>
                    )}
                    {req.lastSyncedAt && (
                      <p className="text-xs text-muted-foreground mt-2">
                        Synced {formatRelativeTime(req.lastSyncedAt)}
                      </p>
                    )}
                  </CardContent>
                </Card>
              </Link>
            ))}
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
