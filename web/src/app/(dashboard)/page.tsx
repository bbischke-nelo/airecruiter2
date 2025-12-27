'use client';

import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import {
  Briefcase,
  Users,
  MessageSquare,
  CheckCircle,
  AlertCircle,
  Clock,
  TrendingUp,
  Activity,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import { formatRelativeTime, formatStatus } from '@/lib/utils';

interface DashboardStats {
  requisitions: { total: number; active: number };
  applications: { total: number; new: number; inProgress: number; complete: number };
  interviews: { total: number; pending: number; completed: number };
  queue: { pending: number; running: number; failed: number };
}

interface ActivityItem {
  id: number;
  action: string;
  applicationId: number | null;
  requisitionId: number | null;
  candidateName: string | null;
  requisitionName: string | null;
  details: Record<string, unknown> | null;
  createdAt: string;
}

interface HealthStatus {
  status: string;
  database: { status: string };
  workday: { status: string };
}

export default function DashboardPage() {
  // Fetch dashboard stats
  const { data: stats, isLoading: statsLoading } = useQuery<DashboardStats>({
    queryKey: ['dashboard-stats'],
    queryFn: async () => {
      // Fetch multiple endpoints in parallel
      const [reqRes, appRes, intRes, queueRes] = await Promise.all([
        api.get('/requisitions?per_page=1'),
        api.get('/applications?per_page=1'),
        api.get('/interviews?per_page=1'),
        api.get('/queue/status'),
      ]);

      return {
        requisitions: {
          total: reqRes.data.meta?.total || 0,
          active: reqRes.data.meta?.total || 0, // TODO: Add active filter
        },
        applications: {
          total: appRes.data.meta?.total || 0,
          new: 0,
          inProgress: 0,
          complete: 0,
        },
        interviews: {
          total: intRes.data.meta?.total || 0,
          pending: 0,
          completed: 0,
        },
        queue: queueRes.data,
      };
    },
  });

  // Fetch recent activity
  const { data: activities, isLoading: activitiesLoading } = useQuery<{ data: ActivityItem[] }>({
    queryKey: ['recent-activities'],
    queryFn: async () => {
      const response = await api.get('/logs?per_page=10');
      return response.data;
    },
  });

  // Fetch health status
  const { data: health } = useQuery<HealthStatus>({
    queryKey: ['health'],
    queryFn: async () => {
      const response = await api.get('/health');
      return response.data;
    },
    refetchInterval: 30000, // Refresh every 30s
  });

  const statCards = [
    {
      title: 'Active Requisitions',
      value: stats?.requisitions.active || 0,
      total: stats?.requisitions.total || 0,
      icon: Briefcase,
      href: '/requisitions',
      color: 'text-blue-600',
    },
    {
      title: 'Applications',
      value: stats?.applications.total || 0,
      subtitle: `${stats?.applications.new || 0} new`,
      icon: Users,
      href: '/applications',
      color: 'text-green-600',
    },
    {
      title: 'Interviews',
      value: stats?.interviews.total || 0,
      subtitle: `${stats?.interviews.pending || 0} pending`,
      icon: MessageSquare,
      href: '/interviews',
      color: 'text-purple-600',
    },
    {
      title: 'Queue',
      value: stats?.queue.pending || 0,
      subtitle: stats?.queue.failed ? `${stats.queue.failed} failed` : 'processing',
      icon: stats?.queue.failed ? AlertCircle : Clock,
      href: '/queue',
      color: stats?.queue.failed ? 'text-red-600' : 'text-orange-600',
    },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Dashboard</h1>
          <p className="text-muted-foreground">
            Overview of your recruiting pipeline
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`flex items-center gap-1 px-2 py-1 text-xs rounded-full ${
              health?.status === 'healthy'
                ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                : 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
            }`}
          >
            <span className={`w-2 h-2 rounded-full ${
              health?.status === 'healthy' ? 'bg-green-500' : 'bg-red-500'
            }`} />
            {health?.status === 'healthy' ? 'All Systems Operational' : 'System Issues'}
          </span>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {statCards.map((stat) => (
          <Link key={stat.title} href={stat.href}>
            <Card className="hover:shadow-md transition-shadow cursor-pointer">
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  {stat.title}
                </CardTitle>
                <stat.icon className={`h-5 w-5 ${stat.color}`} />
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold">
                  {statsLoading ? (
                    <span className="animate-pulse bg-muted rounded w-16 h-8 inline-block" />
                  ) : (
                    stat.value
                  )}
                </div>
                {stat.subtitle && (
                  <p className="text-xs text-muted-foreground mt-1">
                    {stat.subtitle}
                  </p>
                )}
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>

      {/* Main Content Grid */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Recent Activity */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <Activity className="h-5 w-5" />
              Recent Activity
            </CardTitle>
            <Button variant="ghost" size="sm" asChild>
              <Link href="/logs">View All</Link>
            </Button>
          </CardHeader>
          <CardContent>
            {activitiesLoading ? (
              <div className="space-y-3">
                {[1, 2, 3, 4, 5].map((i) => (
                  <div key={i} className="animate-pulse flex gap-3">
                    <div className="h-8 w-8 bg-muted rounded-full" />
                    <div className="flex-1 space-y-2">
                      <div className="h-4 bg-muted rounded w-3/4" />
                      <div className="h-3 bg-muted rounded w-1/2" />
                    </div>
                  </div>
                ))}
              </div>
            ) : activities?.data?.length ? (
              <div className="space-y-4">
                {activities.data.slice(0, 8).map((activity) => (
                  <div key={activity.id} className="flex items-start gap-3">
                    <div className="flex-shrink-0 mt-1">
                      {getActivityIcon(activity.action)}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm">
                        <span className="font-medium">{formatAction(activity.action)}</span>
                        {activity.candidateName && (
                          <span className="text-muted-foreground">
                            {' '}for {activity.candidateName}
                          </span>
                        )}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {formatRelativeTime(activity.createdAt)}
                        {activity.requisitionName && (
                          <span> - {activity.requisitionName}</span>
                        )}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-center text-muted-foreground py-8">
                No recent activity
              </p>
            )}
          </CardContent>
        </Card>

        {/* Quick Actions */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="h-5 w-5" />
              Quick Actions
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Button className="w-full justify-start" variant="outline" asChild>
              <Link href="/requisitions">
                <Briefcase className="h-4 w-4 mr-2" />
                View Active Requisitions
              </Link>
            </Button>
            <Button className="w-full justify-start" variant="outline" asChild>
              <Link href="/applications?status=new">
                <Users className="h-4 w-4 mr-2" />
                Review New Applications
              </Link>
            </Button>
            <Button className="w-full justify-start" variant="outline" asChild>
              <Link href="/interviews?status=completed">
                <MessageSquare className="h-4 w-4 mr-2" />
                View Completed Interviews
              </Link>
            </Button>
            <Button className="w-full justify-start" variant="outline" asChild>
              <Link href="/queue">
                <Clock className="h-4 w-4 mr-2" />
                Monitor Processing Queue
              </Link>
            </Button>
            <Button className="w-full justify-start" variant="outline" asChild>
              <Link href="/settings/credentials">
                <CheckCircle className="h-4 w-4 mr-2" />
                Check Workday Connection
              </Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function getActivityIcon(action: string) {
  switch (action) {
    case 'analysis_completed':
      return <CheckCircle className="h-4 w-4 text-green-500" />;
    case 'interview_sent':
      return <MessageSquare className="h-4 w-4 text-blue-500" />;
    case 'evaluation_completed':
      return <TrendingUp className="h-4 w-4 text-purple-500" />;
    case 'status_changed':
      return <Activity className="h-4 w-4 text-orange-500" />;
    default:
      return <Activity className="h-4 w-4 text-muted-foreground" />;
  }
}

function formatAction(action: string): string {
  const actionMap: Record<string, string> = {
    analysis_completed: 'Resume analyzed',
    interview_sent: 'Interview invite sent',
    evaluation_completed: 'Interview evaluated',
    status_changed: 'Status updated',
    report_generated: 'Report generated',
    report_uploaded: 'Report uploaded to Workday',
  };
  return actionMap[action] || formatStatus(action);
}
