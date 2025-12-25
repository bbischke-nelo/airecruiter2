'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import Link from 'next/link';
import { RefreshCw, MapPin, Users, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { api } from '@/lib/api';
import { formatRelativeTime } from '@/lib/utils';
import { useToast } from '@/hooks/use-toast';

interface Requisition {
  id: number;
  externalId: string;
  name: string;
  description: string;
  location: string;
  isActive: boolean;
  syncEnabled: boolean;
  applicationCount: number;
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

export default function RequisitionsPage() {
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const { data, isLoading, error, refetch } = useQuery<PaginatedResponse>({
    queryKey: ['requisitions'],
    queryFn: async () => {
      const response = await api.get('/requisitions');
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
      // Refetch after a delay to show updated data
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
        <p className="text-destructive">Failed to load requisitions</p>
        <Button variant="outline" onClick={() => refetch()} className="mt-4">
          Retry
        </Button>
      </div>
    );
  }

  const requisitions = data?.data || [];

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Requisitions</h1>
          <p className="text-muted-foreground">
            {data?.meta.total || 0} total requisitions
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => refetch()}>
            <RefreshCw className="h-4 w-4 mr-2" />
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

      {requisitions.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-muted-foreground">No requisitions found</p>
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
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {requisitions.map((req) => (
            <Link key={req.id} href={`/requisitions/${req.id}`}>
              <Card className="hover:shadow-md transition-shadow cursor-pointer">
                <CardHeader className="pb-2">
                  <div className="flex items-start justify-between">
                    <CardTitle className="text-lg line-clamp-2">
                      {req.name}
                    </CardTitle>
                    <span
                      className={`px-2 py-1 text-xs rounded-full ${
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
                  <p className="text-sm text-muted-foreground line-clamp-2 mb-4">
                    {req.description || 'No description'}
                  </p>
                  <div className="flex items-center gap-4 text-sm text-muted-foreground">
                    {req.location && (
                      <span className="flex items-center gap-1">
                        <MapPin className="h-4 w-4" />
                        {req.location}
                      </span>
                    )}
                    <span className="flex items-center gap-1">
                      <Users className="h-4 w-4" />
                      {req.applicationCount || 0} applications
                    </span>
                  </div>
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
      )}
    </div>
  );
}
