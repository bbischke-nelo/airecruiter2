'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { RefreshCw, Play, Trash2, RotateCcw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { api } from '@/lib/api';
import { formatRelativeTime, cn } from '@/lib/utils';
import { useToast } from '@/hooks/use-toast';

interface QueueStatus {
  pending: number;
  running: number;
  completed: number;
  failed: number;
  dead: number;
}

interface QueueItem {
  id: number;
  jobType: string;
  applicationId: number | null;
  requisitionId: number | null;
  status: string;
  attempts: number;
  maxAttempts: number;
  lastError: string | null;
  scheduledFor: string;
  createdAt: string;
}

export default function QueuePage() {
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const { data: status, isLoading: statusLoading } = useQuery<{ status: QueueStatus }>({
    queryKey: ['queue-status'],
    queryFn: async () => {
      const response = await api.get('/queue/status');
      return response.data;
    },
    refetchInterval: 5000, // Refresh every 5 seconds
  });

  const { data: items, isLoading: itemsLoading, refetch } = useQuery<{ data: QueueItem[] }>({
    queryKey: ['queue-items'],
    queryFn: async () => {
      const response = await api.get('/queue');
      return response.data;
    },
    refetchInterval: 5000,
  });

  const retryMutation = useMutation({
    mutationFn: async (jobId: number) => {
      await api.post(`/queue/${jobId}/retry`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['queue-items'] });
      queryClient.invalidateQueries({ queryKey: ['queue-status'] });
      toast({ title: 'Job queued for retry' });
    },
    onError: () => {
      toast({ title: 'Failed to retry job', variant: 'destructive' });
    },
  });

  const clearMutation = useMutation({
    mutationFn: async () => {
      await api.delete('/queue/completed');
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['queue-items'] });
      queryClient.invalidateQueries({ queryKey: ['queue-status'] });
      toast({ title: 'Completed jobs cleared' });
    },
  });

  const queueStatus = status?.status || { pending: 0, running: 0, completed: 0, failed: 0, dead: 0 };
  const queueItems = items?.data || [];

  const statusColors: Record<string, string> = {
    pending: 'bg-blue-500',
    running: 'bg-yellow-500',
    completed: 'bg-green-500',
    failed: 'bg-orange-500',
    dead: 'bg-red-500',
  };

  return (
    <div>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold">Processing Queue</h1>
          <p className="text-muted-foreground">
            Background job management
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
          <Button variant="outline" onClick={() => clearMutation.mutate()}>
            <Trash2 className="h-4 w-4 mr-2" />
            Clear Completed
          </Button>
        </div>
      </div>

      {/* Status Cards */}
      <div className="grid gap-4 md:grid-cols-5 mb-6">
        {Object.entries(queueStatus).map(([key, value]) => (
          <Card key={key}>
            <CardContent className="pt-6">
              <div className="flex items-center gap-2">
                <div className={cn('w-3 h-3 rounded-full', statusColors[key])} />
                <span className="text-2xl font-bold">{value}</span>
              </div>
              <p className="text-sm text-muted-foreground capitalize">{key}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Queue Items */}
      {itemsLoading ? (
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin h-8 w-8 border-4 border-primary border-t-transparent rounded-full" />
        </div>
      ) : queueItems.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-muted-foreground">Queue is empty</p>
          </CardContent>
        </Card>
      ) : (
        <div className="rounded-lg border overflow-hidden">
          <table className="w-full">
            <thead className="bg-muted">
              <tr>
                <th className="px-4 py-3 text-left text-sm font-medium">Job Type</th>
                <th className="px-4 py-3 text-left text-sm font-medium">Target</th>
                <th className="px-4 py-3 text-left text-sm font-medium">Status</th>
                <th className="px-4 py-3 text-left text-sm font-medium">Attempts</th>
                <th className="px-4 py-3 text-left text-sm font-medium">Scheduled</th>
                <th className="px-4 py-3 text-left text-sm font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {queueItems.map((item) => (
                <tr key={item.id} className="hover:bg-muted/50">
                  <td className="px-4 py-3 font-medium">{item.jobType}</td>
                  <td className="px-4 py-3 text-sm text-muted-foreground">
                    {item.applicationId ? `App #${item.applicationId}` :
                     item.requisitionId ? `Req #${item.requisitionId}` : '-'}
                  </td>
                  <td className="px-4 py-3">
                    <span className={cn(
                      'px-2 py-1 text-xs rounded-full',
                      item.status === 'pending' ? 'bg-blue-100 text-blue-800' :
                      item.status === 'running' ? 'bg-yellow-100 text-yellow-800' :
                      item.status === 'completed' ? 'bg-green-100 text-green-800' :
                      item.status === 'dead' ? 'bg-red-100 text-red-800' :
                      'bg-orange-100 text-orange-800'
                    )}>
                      {item.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm">
                    {item.attempts}/{item.maxAttempts}
                  </td>
                  <td className="px-4 py-3 text-sm text-muted-foreground">
                    {formatRelativeTime(item.scheduledFor)}
                  </td>
                  <td className="px-4 py-3">
                    {(item.status === 'failed' || item.status === 'dead') && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => retryMutation.mutate(item.id)}
                      >
                        <RotateCcw className="h-4 w-4" />
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
