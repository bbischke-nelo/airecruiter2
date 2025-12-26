'use client';

import Link from 'next/link';
import { MessageSquare, Users, Mail, FileText, Settings2 } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

const settingsPages = [
  {
    title: 'Requisition Defaults',
    description: 'Global settings for AI interviews and Workday mappings',
    href: '/settings/defaults',
    icon: Settings2,
  },
  {
    title: 'AI Prompts',
    description: 'Customize analysis and evaluation prompts',
    href: '/settings/prompts',
    icon: MessageSquare,
  },
  {
    title: 'Email Templates',
    description: 'Configure email templates for interviews',
    href: '/settings/email',
    icon: Mail,
  },
  {
    title: 'Report Templates',
    description: 'Configure PDF report templates',
    href: '/settings/reports',
    icon: FileText,
  },
  {
    title: 'Recruiters',
    description: 'Manage recruiter accounts',
    href: '/settings/recruiters',
    icon: Users,
  },
];

export default function SettingsPage() {
  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Settings</h1>
        <p className="text-muted-foreground">
          Configure AIRecruiter settings and integrations
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        {settingsPages.map((page) => (
          <Link key={page.href} href={page.href}>
            <Card className="hover:shadow-md transition-shadow cursor-pointer h-full">
              <CardHeader>
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-primary/10">
                    <page.icon className="h-5 w-5 text-primary" />
                  </div>
                  <div>
                    <CardTitle className="text-lg">{page.title}</CardTitle>
                    <CardDescription>{page.description}</CardDescription>
                  </div>
                </div>
              </CardHeader>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
