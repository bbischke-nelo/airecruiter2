'use client';

import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { RefreshCw, Search, Filter } from 'lucide-react';
import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent } from '@/components/ui/card';
import { api } from '@/lib/api';
import { formatRelativeTime, cn } from '@/lib/utils';

interface Application {
  id: number;
  candidateName: string;
  candidateEmail: string;
  requisitionName: string;
  status: string;
  workdayStatus: string;
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
  analyzed: 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200',
  interview_pending: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
  interview_complete: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
  complete: 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200',
};

export default function ApplicationsPage() {
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState<string>('');

  const { data, isLoading, error, refetch } = useQuery<PaginatedResponse>({
    queryKey: ['applications', search, status],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (search) params.set('search', search);
      if (status) params.set('status', status);
      const response = await api.get(`/applications?${params}`);
      return response.data;
    },
  });

  const applications = data?.data || [];

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Applications</h1>
          <p className="text-muted-foreground">
            {data?.meta.total || 0} total applications
          </p>
        </div>
        <Button variant="outline" onClick={() => refetch()}>
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Filters */}
      <div className="flex gap-4 mb-6">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search candidates..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-10"
          />
        </div>
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="px-3 py-2 border rounded-md bg-background"
        >
          <option value="">All Statuses</option>
          <option value="new">New</option>
          <option value="analyzed">Analyzed</option>
          <option value="interview_pending">Interview Pending</option>
          <option value="interview_complete">Interview Complete</option>
          <option value="complete">Complete</option>
        </select>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin h-8 w-8 border-4 border-primary border-t-transparent rounded-full" />
        </div>
      ) : error ? (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-destructive">Failed to load applications</p>
          </CardContent>
        </Card>
      ) : applications.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-muted-foreground">No applications found</p>
          </CardContent>
        </Card>
      ) : (
        <div className="rounded-lg border overflow-hidden">
          <table className="w-full">
            <thead className="bg-muted">
              <tr>
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
                      <div className="font-medium">{app.candidateName}</div>
                      <div className="text-sm text-muted-foreground">{app.candidateEmail}</div>
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-sm">{app.requisitionName}</td>
                  <td className="px-4 py-3">
                    <span className={cn(
                      'px-2 py-1 text-xs rounded-full',
                      statusColors[app.status] || 'bg-gray-100 text-gray-800'
                    )}>
                      {app.status.replace('_', ' ')}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    {app.riskScore !== null && (
                      <span className={cn(
                        'px-2 py-1 text-xs rounded-full',
                        app.riskScore <= 3 ? 'bg-green-100 text-green-800' :
                        app.riskScore <= 6 ? 'bg-yellow-100 text-yellow-800' :
                        'bg-red-100 text-red-800'
                      )}>
                        {app.riskScore}/10
                      </span>
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
      )}
    </div>
  );
}
