'use client';

import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { Plus, RefreshCw, MapPin, Users } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { api } from '@/lib/api';
import { formatRelativeTime } from '@/lib/utils';

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
  const { data, isLoading, error, refetch } = useQuery<PaginatedResponse>({
    queryKey: ['requisitions'],
    queryFn: async () => {
      const response = await api.get('/requisitions');
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
          <Button>
            <Plus className="h-4 w-4 mr-2" />
            Sync All
          </Button>
        </div>
      </div>

      {requisitions.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-muted-foreground">No requisitions found</p>
            <p className="text-sm text-muted-foreground mt-2">
              Configure Workday credentials in Settings to sync requisitions
            </p>
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
