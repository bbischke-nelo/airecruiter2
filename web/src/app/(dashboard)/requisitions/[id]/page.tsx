'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { useState } from 'react';
import {
  ArrowLeft,
  RefreshCw,
  MapPin,
  Users,
  Calendar,
  Settings,
  FileText,
  Play,
  Save,
  ExternalLink,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { api } from '@/lib/api';
import { formatDateTime, formatRelativeTime } from '@/lib/utils';
import { Requisition, Application } from '@/types';

type TabType = 'overview' | 'applications' | 'settings';

export default function RequisitionDetailPage() {
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<TabType>('overview');
  const [isEditing, setIsEditing] = useState(false);
  const [formData, setFormData] = useState<Partial<Requisition>>({});

  const { data: requisition, isLoading } = useQuery<Requisition>({
    queryKey: ['requisition', params.id],
    queryFn: async () => {
      const response = await api.get(`/requisitions/${params.id}`);
      setFormData(response.data);
      return response.data;
    },
  });

  const { data: applications } = useQuery<{ data: Application[] }>({
    queryKey: ['requisition-applications', params.id],
    queryFn: async () => {
      const response = await api.get(`/applications?requisition_id=${params.id}`);
      return response.data;
    },
    enabled: activeTab === 'applications',
  });

  const syncMutation = useMutation({
    mutationFn: async () => {
      await api.post(`/requisitions/${params.id}/sync`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['requisition', params.id] });
      queryClient.invalidateQueries({ queryKey: ['requisition-applications', params.id] });
    },
  });

  const updateMutation = useMutation({
    mutationFn: async (data: Partial<Requisition>) => {
      await api.patch(`/requisitions/${params.id}`, data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['requisition', params.id] });
      setIsEditing(false);
    },
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin h-8 w-8 border-4 border-primary border-t-transparent rounded-full" />
      </div>
    );
  }

  if (!requisition) {
    return (
      <div className="text-center py-12">
        <p className="text-muted-foreground">Requisition not found</p>
        <Button variant="outline" onClick={() => router.back()} className="mt-4">
          Go Back
        </Button>
      </div>
    );
  }

  const tabs = [
    { id: 'overview' as const, label: 'Overview', icon: FileText },
    { id: 'applications' as const, label: 'Applications', icon: Users },
    { id: 'settings' as const, label: 'Settings', icon: Settings },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-4">
          <Button variant="ghost" size="icon" onClick={() => router.back()}>
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold">{requisition.name}</h1>
              <span
                className={`px-2 py-1 text-xs rounded-full ${
                  requisition.isActive
                    ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                    : 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200'
                }`}
              >
                {requisition.isActive ? 'Active' : 'Inactive'}
              </span>
            </div>
            <p className="text-sm text-muted-foreground mt-1">
              {requisition.externalId}
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => syncMutation.mutate()}
            disabled={syncMutation.isPending}
          >
            <RefreshCw className={`h-4 w-4 mr-2 ${syncMutation.isPending ? 'animate-spin' : ''}`} />
            Sync Now
          </Button>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b">
        <nav className="flex gap-4">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-2 border-b-2 transition-colors ${
                activeTab === tab.id
                  ? 'border-primary text-primary'
                  : 'border-transparent text-muted-foreground hover:text-foreground'
              }`}
            >
              <tab.icon className="h-4 w-4" />
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content */}
      {activeTab === 'overview' && (
        <div className="grid gap-6 lg:grid-cols-3">
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle>Job Description</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="whitespace-pre-wrap">
                {requisition.detailedDescription || requisition.description || 'No description available'}
              </p>
            </CardContent>
          </Card>

          <div className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Details</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {requisition.location && (
                  <div className="flex items-center gap-2 text-sm">
                    <MapPin className="h-4 w-4 text-muted-foreground" />
                    {requisition.location}
                  </div>
                )}
                <div className="flex items-center gap-2 text-sm">
                  <Users className="h-4 w-4 text-muted-foreground" />
                  {requisition.applicationCount || 0} applications
                </div>
                <div className="flex items-center gap-2 text-sm">
                  <Calendar className="h-4 w-4 text-muted-foreground" />
                  Created {formatDateTime(requisition.createdAt)}
                </div>
                {requisition.lastSyncedAt && (
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <RefreshCw className="h-4 w-4" />
                    Last synced {formatRelativeTime(requisition.lastSyncedAt)}
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Interview Settings</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Auto-send interviews</span>
                  <span>{requisition.autoSendInterview ? 'Yes' : 'No'}</span>
                </div>
                {requisition.autoSendOnStatus && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Trigger status</span>
                    <span>{requisition.autoSendOnStatus}</span>
                  </div>
                )}
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Lookback hours</span>
                  <span>{requisition.lookbackHours || 'Default'}</span>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      )}

      {activeTab === 'applications' && (
        <div>
          {applications?.data?.length ? (
            <div className="space-y-2">
              {applications.data.map((app) => (
                <Link key={app.id} href={`/applications/${app.id}`}>
                  <Card className="hover:shadow-md transition-shadow cursor-pointer">
                    <CardContent className="flex items-center justify-between py-4">
                      <div>
                        <p className="font-medium">{app.candidateName}</p>
                        <p className="text-sm text-muted-foreground">{app.candidateEmail}</p>
                      </div>
                      <div className="flex items-center gap-4">
                        <span
                          className={`px-2 py-1 text-xs rounded-full ${getStatusColor(app.status)}`}
                        >
                          {app.status.replace(/_/g, ' ')}
                        </span>
                        {app.riskScore !== null && (
                          <span className="text-sm">
                            Risk: {app.riskScore}
                          </span>
                        )}
                        <ExternalLink className="h-4 w-4 text-muted-foreground" />
                      </div>
                    </CardContent>
                  </Card>
                </Link>
              ))}
            </div>
          ) : (
            <Card>
              <CardContent className="py-12 text-center">
                <p className="text-muted-foreground">No applications yet</p>
                <Button
                  variant="outline"
                  className="mt-4"
                  onClick={() => syncMutation.mutate()}
                >
                  <RefreshCw className="h-4 w-4 mr-2" />
                  Sync from Workday
                </Button>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {activeTab === 'settings' && (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>Requisition Settings</CardTitle>
            {isEditing ? (
              <div className="flex gap-2">
                <Button variant="outline" onClick={() => setIsEditing(false)}>
                  Cancel
                </Button>
                <Button
                  onClick={() => updateMutation.mutate(formData)}
                  disabled={updateMutation.isPending}
                >
                  <Save className="h-4 w-4 mr-2" />
                  Save
                </Button>
              </div>
            ) : (
              <Button variant="outline" onClick={() => setIsEditing(true)}>
                Edit
              </Button>
            )}
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="text-sm font-medium">Auto-send Interviews</label>
              <div className="flex items-center gap-2 mt-1">
                <input
                  type="checkbox"
                  checked={formData.autoSendInterview || false}
                  onChange={(e) =>
                    setFormData({ ...formData, autoSendInterview: e.target.checked })
                  }
                  disabled={!isEditing}
                  className="h-4 w-4"
                />
                <span className="text-sm text-muted-foreground">
                  Automatically send interview invites when candidates reach trigger status
                </span>
              </div>
            </div>

            <div>
              <label className="text-sm font-medium">Trigger Status</label>
              <Input
                value={formData.autoSendOnStatus || ''}
                onChange={(e) =>
                  setFormData({ ...formData, autoSendOnStatus: e.target.value })
                }
                disabled={!isEditing}
                placeholder="e.g., Screen"
                className="mt-1"
              />
            </div>

            <div>
              <label className="text-sm font-medium">Lookback Hours</label>
              <Input
                type="number"
                value={formData.lookbackHours || ''}
                onChange={(e) =>
                  setFormData({ ...formData, lookbackHours: parseInt(e.target.value) || undefined })
                }
                disabled={!isEditing}
                placeholder="Default: 24"
                className="mt-1"
              />
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function getStatusColor(status: string): string {
  const colors: Record<string, string> = {
    new: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
    analyzed: 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200',
    interview_pending: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
    interview_complete: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
    complete: 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200',
  };
  return colors[status] || 'bg-gray-100 text-gray-800';
}
