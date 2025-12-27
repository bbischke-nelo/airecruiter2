'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useState, useEffect } from 'react';
import {
  Mail,
  Plus,
  Edit,
  Trash2,
  Save,
  X,
  CheckCircle,
  RotateCcw,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogCancel,
  AlertDialogAction,
} from '@/components/ui/alert-dialog';
import { api } from '@/lib/api';
import { formatDateTime, formatStatus } from '@/lib/utils';

interface EmailTemplate {
  id: number;
  name: string;
  templateType: string;
  subject: string;
  bodyHtml: string;
  bodyText: string | null;
  isActive: boolean;
  isDefault: boolean;
  createdAt: string;
  updatedAt: string | null;
}

interface EmailSettings {
  fromAddress: string;
  fromName: string;
  provider: string;
}

export default function EmailSettingsPage() {
  const queryClient = useQueryClient();
  const [editingTemplate, setEditingTemplate] = useState<EmailTemplate | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [showInactive, setShowInactive] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null);
  const [newTemplate, setNewTemplate] = useState<Partial<EmailTemplate>>({
    name: '',
    templateType: 'interview_invite',
    subject: '',
    bodyHtml: '',
    bodyText: '',
    isActive: true,
    isDefault: false,
  });

  // Local state for email settings form
  const [fromAddress, setFromAddress] = useState('');
  const [fromName, setFromName] = useState('');
  const [settingsDirty, setSettingsDirty] = useState(false);

  // Fetch settings
  const { data: settings } = useQuery<EmailSettings>({
    queryKey: ['email-settings'],
    queryFn: async () => {
      const response = await api.get('/settings');
      const data = response.data;
      return {
        fromAddress: data.email_from_address || '',
        fromName: data.email_from_name || '',
        provider: data.email_provider || 'ses',
      };
    },
  });

  // Sync local state with fetched settings
  useEffect(() => {
    if (settings) {
      setFromAddress(settings.fromAddress);
      setFromName(settings.fromName);
      setSettingsDirty(false);
    }
  }, [settings]);

  // Fetch templates - filter by active unless showInactive is checked
  const { data: templates, isLoading } = useQuery<{ data: EmailTemplate[] }>({
    queryKey: ['email-templates', showInactive],
    queryFn: async () => {
      const params = showInactive ? '' : '?is_active=true';
      const response = await api.get(`/email-templates${params}`);
      return response.data;
    },
  });

  // Fetch full template for editing
  const fetchFullTemplate = async (templateId: number) => {
    try {
      const response = await api.get(`/email-templates/${templateId}`);
      setEditingTemplate(response.data);
    } catch (error) {
      console.error('Failed to fetch template:', error);
    }
  };

  // Update settings mutation
  const updateSettingsMutation = useMutation({
    mutationFn: async () => {
      await api.patch('/settings', {
        email_from_address: fromAddress,
        email_from_name: fromName,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['email-settings'] });
      setSettingsDirty(false);
    },
  });

  // Create template mutation
  const createTemplateMutation = useMutation({
    mutationFn: async (data: Partial<EmailTemplate>) => {
      await api.post('/email-templates', data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['email-templates'] });
      setIsCreating(false);
      setNewTemplate({
        name: '',
        templateType: 'interview_invite',
        subject: '',
        bodyHtml: '',
        bodyText: '',
        isActive: true,
        isDefault: false,
      });
    },
  });

  // Update template mutation
  const updateTemplateMutation = useMutation({
    mutationFn: async (data: EmailTemplate) => {
      await api.patch(`/email-templates/${data.id}`, data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['email-templates'] });
      setEditingTemplate(null);
    },
  });

  // Delete template mutation
  const deleteTemplateMutation = useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/email-templates/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['email-templates'] });
    },
  });

  // Seed defaults mutation
  const seedDefaultsMutation = useMutation({
    mutationFn: async () => {
      await api.post('/email-templates/seed');
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['email-templates'] });
    },
  });

  const templateTypes = [
    { value: 'interview_invite', label: 'Interview Invite' },
    { value: 'reminder', label: 'Reminder' },
    { value: 'completion', label: 'Completion' },
    { value: 'alert', label: 'Alert' },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Email Settings</h1>
        <p className="text-muted-foreground">
          Configure email sending and manage templates
        </p>
      </div>

      {/* Email Configuration */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Mail className="h-5 w-5" />
            Email Configuration
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <label className="text-sm font-medium">From Address</label>
              <Input
                value={fromAddress}
                onChange={(e) => {
                  setFromAddress(e.target.value);
                  setSettingsDirty(true);
                }}
                placeholder="jobs@ccfs.com"
                className="mt-1"
              />
            </div>
            <div>
              <label className="text-sm font-medium">From Name</label>
              <Input
                value={fromName}
                onChange={(e) => {
                  setFromName(e.target.value);
                  setSettingsDirty(true);
                }}
                placeholder="CCFS Talent Team"
                className="mt-1"
              />
            </div>
          </div>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm">
              <span className="text-muted-foreground">Provider:</span>
              <span className="px-2 py-1 bg-muted rounded text-xs font-mono">
                {settings?.provider || 'AWS SES'}
              </span>
              <CheckCircle className="h-4 w-4 text-green-500" />
              <span className="text-green-600 text-xs">Connected</span>
            </div>
            {settingsDirty && (
              <Button
                size="sm"
                onClick={() => updateSettingsMutation.mutate()}
                disabled={updateSettingsMutation.isPending}
              >
                <Save className="h-4 w-4 mr-2" />
                Save
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Email Templates */}
      <Card>
        <CardHeader className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <CardTitle>Email Templates</CardTitle>
          <div className="flex flex-wrap items-center gap-2 sm:gap-4">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={showInactive}
                onChange={(e) => setShowInactive(e.target.checked)}
                className="rounded border-input"
              />
              Show inactive
            </label>
            <Button
              variant="outline"
              size="sm"
              onClick={() => seedDefaultsMutation.mutate()}
              disabled={seedDefaultsMutation.isPending}
            >
              <RotateCcw className="h-4 w-4 sm:mr-2" />
              <span className="hidden sm:inline">Seed Defaults</span>
            </Button>
            <Button size="sm" onClick={() => setIsCreating(true)} disabled={isCreating}>
              <Plus className="h-4 w-4 sm:mr-2" />
              <span className="hidden sm:inline">New Template</span>
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {/* New Template Form */}
          {isCreating && (
            <div className="mb-6 p-4 border rounded-lg bg-muted/50">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-medium">New Template</h3>
                <Button variant="ghost" size="icon" onClick={() => setIsCreating(false)}>
                  <X className="h-4 w-4" />
                </Button>
              </div>
              <div className="space-y-4">
                <div className="grid gap-4 md:grid-cols-2">
                  <div>
                    <label className="text-sm font-medium">Name</label>
                    <Input
                      value={newTemplate.name || ''}
                      onChange={(e) =>
                        setNewTemplate({ ...newTemplate, name: e.target.value })
                      }
                      placeholder="Template name"
                      className="mt-1"
                    />
                  </div>
                  <div>
                    <label className="text-sm font-medium">Type</label>
                    <select
                      value={newTemplate.templateType || 'interview_invite'}
                      onChange={(e) =>
                        setNewTemplate({ ...newTemplate, templateType: e.target.value })
                      }
                      className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                    >
                      {templateTypes.map((type) => (
                        <option key={type.value} value={type.value}>
                          {type.label}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
                <div>
                  <label className="text-sm font-medium">Subject</label>
                  <Input
                    value={newTemplate.subject || ''}
                    onChange={(e) =>
                      setNewTemplate({ ...newTemplate, subject: e.target.value })
                    }
                    placeholder="Email subject line"
                    className="mt-1"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium">Body (HTML)</label>
                  <textarea
                    value={newTemplate.bodyHtml || ''}
                    onChange={(e) =>
                      setNewTemplate({ ...newTemplate, bodyHtml: e.target.value })
                    }
                    placeholder="<p>Email content...</p>"
                    className="mt-1 w-full min-h-[150px] rounded-md border border-input bg-background px-3 py-2 text-sm font-mono"
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    Available variables: {'{candidate_name}'}, {'{position}'},{' '}
                    {'{interview_link}'}, {'{recruiter_name}'}
                  </p>
                </div>
                <div className="flex justify-end gap-2">
                  <Button variant="outline" onClick={() => setIsCreating(false)}>
                    Cancel
                  </Button>
                  <Button
                    onClick={() => createTemplateMutation.mutate(newTemplate)}
                    disabled={createTemplateMutation.isPending}
                  >
                    <Save className="h-4 w-4 mr-2" />
                    Create Template
                  </Button>
                </div>
              </div>
            </div>
          )}

          {/* Templates List */}
          {isLoading ? (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <div key={i} className="animate-pulse p-4 border rounded-lg">
                  <div className="h-4 bg-muted rounded w-1/4 mb-2" />
                  <div className="h-3 bg-muted rounded w-1/2" />
                </div>
              ))}
            </div>
          ) : templates?.data?.length ? (
            <div className="space-y-3">
              {templates.data.map((template) => (
                <div
                  key={template.id}
                  className="p-4 border rounded-lg hover:border-primary/50 transition-colors"
                >
                  {editingTemplate?.id === template.id ? (
                    <div className="space-y-4">
                      <div className="grid gap-4 md:grid-cols-2">
                        <Input
                          value={editingTemplate.name}
                          onChange={(e) =>
                            setEditingTemplate({
                              ...editingTemplate,
                              name: e.target.value,
                            })
                          }
                        />
                        <select
                          value={editingTemplate.templateType}
                          onChange={(e) =>
                            setEditingTemplate({
                              ...editingTemplate,
                              templateType: e.target.value,
                            })
                          }
                          className="rounded-md border border-input bg-background px-3 py-2 text-sm"
                        >
                          {templateTypes.map((type) => (
                            <option key={type.value} value={type.value}>
                              {type.label}
                            </option>
                          ))}
                        </select>
                      </div>
                      <Input
                        value={editingTemplate.subject}
                        onChange={(e) =>
                          setEditingTemplate({
                            ...editingTemplate,
                            subject: e.target.value,
                          })
                        }
                        placeholder="Subject"
                      />
                      <textarea
                        value={editingTemplate.bodyHtml}
                        onChange={(e) =>
                          setEditingTemplate({
                            ...editingTemplate,
                            bodyHtml: e.target.value,
                          })
                        }
                        className="w-full min-h-[150px] rounded-md border border-input bg-background px-3 py-2 text-sm font-mono"
                      />
                      <div className="flex justify-end gap-2">
                        <Button
                          variant="outline"
                          onClick={() => setEditingTemplate(null)}
                        >
                          Cancel
                        </Button>
                        <Button
                          onClick={() => updateTemplateMutation.mutate(editingTemplate)}
                          disabled={updateTemplateMutation.isPending}
                        >
                          <Save className="h-4 w-4 mr-2" />
                          Save
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <div className="flex items-start justify-between">
                      <div>
                        <div className="flex items-center gap-2">
                          <h3 className="font-medium">{template.name}</h3>
                          <span className="px-2 py-0.5 bg-muted rounded text-xs">
                            {formatStatus(template.templateType)}
                          </span>
                          {template.isDefault && (
                            <span className="px-2 py-0.5 bg-primary/10 text-primary rounded text-xs">
                              Default
                            </span>
                          )}
                          {!template.isActive && (
                            <span className="px-2 py-0.5 bg-red-100 text-red-800 rounded text-xs">
                              Inactive
                            </span>
                          )}
                        </div>
                        <p className="text-sm text-muted-foreground mt-1">
                          {template.subject}
                        </p>
                        <p className="text-xs text-muted-foreground mt-2">
                          Last updated:{' '}
                          {template.updatedAt
                            ? formatDateTime(template.updatedAt)
                            : formatDateTime(template.createdAt)}
                        </p>
                      </div>
                      <div className="flex gap-2">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => fetchFullTemplate(template.id)}
                        >
                          <Edit className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => setDeleteConfirm(template.id)}
                        >
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8">
              <Mail className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
              <p className="text-muted-foreground">No templates yet</p>
              <Button className="mt-4" onClick={() => setIsCreating(true)}>
                <Plus className="h-4 w-4 mr-2" />
                Create First Template
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteConfirm !== null} onOpenChange={() => setDeleteConfirm(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Template</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete this email template? This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              onClick={() => {
                if (deleteConfirm) {
                  deleteTemplateMutation.mutate(deleteConfirm);
                }
              }}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
