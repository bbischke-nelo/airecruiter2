'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import {
  FileText,
  Plus,
  Edit,
  Trash2,
  Save,
  X,
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

interface ReportTemplate {
  id: number;
  name: string;
  templateType: string;
  bodyHtml: string;
  customCss: string | null;
  isActive: boolean;
  isDefault: boolean;
  createdAt: string;
  updatedAt: string | null;
}

const templateTypes = [
  { value: 'analysis', label: 'Analysis Report' },
  { value: 'interview_report', label: 'Interview Report' },
];

export default function ReportTemplatesSettingsPage() {
  const queryClient = useQueryClient();
  const [editingTemplate, setEditingTemplate] = useState<ReportTemplate | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [showInactive, setShowInactive] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null);
  const [newTemplate, setNewTemplate] = useState<Partial<ReportTemplate>>({
    name: '',
    templateType: 'analysis',
    bodyHtml: '',
    customCss: '',
    isDefault: false,
  });

  // Fetch templates - filter by active unless showInactive is checked
  const { data: templates, isLoading } = useQuery<{ data: ReportTemplate[] }>({
    queryKey: ['report-templates', showInactive],
    queryFn: async () => {
      const params = showInactive ? '' : '?is_active=true';
      const response = await api.get(`/report-templates${params}`);
      return response.data;
    },
  });

  // Create template mutation
  const createTemplateMutation = useMutation({
    mutationFn: async (data: Partial<ReportTemplate>) => {
      await api.post('/report-templates', {
        name: data.name,
        template_type: data.templateType,
        body_html: data.bodyHtml,
        custom_css: data.customCss || null,
        is_default: data.isDefault,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['report-templates'] });
      setIsCreating(false);
      setNewTemplate({
        name: '',
        templateType: 'analysis',
        bodyHtml: '',
        customCss: '',
        isDefault: false,
      });
    },
  });

  // Update template mutation
  const updateTemplateMutation = useMutation({
    mutationFn: async (data: ReportTemplate) => {
      await api.patch(`/report-templates/${data.id}`, {
        name: data.name,
        body_html: data.bodyHtml,
        custom_css: data.customCss || null,
        is_active: data.isActive,
        is_default: data.isDefault,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['report-templates'] });
      setEditingTemplate(null);
    },
  });

  // Delete template mutation
  const deleteTemplateMutation = useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/report-templates/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['report-templates'] });
    },
  });

  // Fetch full template for editing
  const fetchFullTemplate = async (templateId: number) => {
    try {
      const response = await api.get(`/report-templates/${templateId}`);
      setEditingTemplate(response.data);
    } catch (error) {
      console.error('Failed to fetch template:', error);
    }
  };

  // Seed defaults mutation
  const seedDefaultsMutation = useMutation({
    mutationFn: async () => {
      await api.post('/report-templates/seed');
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['report-templates'] });
    },
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Report Templates</h1>
        <p className="text-muted-foreground">
          Configure HTML templates for PDF report generation
        </p>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            PDF Report Templates
          </CardTitle>
          <div className="flex items-center gap-4">
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
              onClick={() => seedDefaultsMutation.mutate()}
              disabled={seedDefaultsMutation.isPending}
            >
              <RotateCcw className="h-4 w-4 mr-2" />
              Seed Defaults
            </Button>
            <Button onClick={() => setIsCreating(true)} disabled={isCreating}>
              <Plus className="h-4 w-4 mr-2" />
              New Template
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {/* New Template Form */}
          {isCreating && (
            <div className="mb-6 p-4 border rounded-lg bg-muted/50">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-medium">New Report Template</h3>
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
                      value={newTemplate.templateType || 'analysis'}
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
                  <label className="text-sm font-medium">HTML Template</label>
                  <textarea
                    value={newTemplate.bodyHtml || ''}
                    onChange={(e) =>
                      setNewTemplate({ ...newTemplate, bodyHtml: e.target.value })
                    }
                    placeholder="<!DOCTYPE html>..."
                    className="mt-1 w-full min-h-[300px] rounded-md border border-input bg-background px-3 py-2 text-sm font-mono"
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    Jinja2 template syntax supported. Variables depend on template type.
                  </p>
                </div>
                <div>
                  <label className="text-sm font-medium">Custom CSS (optional)</label>
                  <textarea
                    value={newTemplate.customCss || ''}
                    onChange={(e) =>
                      setNewTemplate({ ...newTemplate, customCss: e.target.value })
                    }
                    placeholder=".custom-class { ... }"
                    className="mt-1 w-full min-h-[100px] rounded-md border border-input bg-background px-3 py-2 text-sm font-mono"
                  />
                </div>
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="isDefault"
                    checked={newTemplate.isDefault || false}
                    onChange={(e) =>
                      setNewTemplate({ ...newTemplate, isDefault: e.target.checked })
                    }
                    className="rounded border-input"
                  />
                  <label htmlFor="isDefault" className="text-sm">
                    Set as default for this type
                  </label>
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
              {[1, 2].map((i) => (
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
                      <Input
                        value={editingTemplate.name}
                        onChange={(e) =>
                          setEditingTemplate({
                            ...editingTemplate,
                            name: e.target.value,
                          })
                        }
                        placeholder="Name"
                      />
                      <textarea
                        value={editingTemplate.bodyHtml}
                        onChange={(e) =>
                          setEditingTemplate({
                            ...editingTemplate,
                            bodyHtml: e.target.value,
                          })
                        }
                        className="w-full min-h-[300px] rounded-md border border-input bg-background px-3 py-2 text-sm font-mono"
                      />
                      <textarea
                        value={editingTemplate.customCss || ''}
                        onChange={(e) =>
                          setEditingTemplate({
                            ...editingTemplate,
                            customCss: e.target.value,
                          })
                        }
                        placeholder="Custom CSS (optional)"
                        className="w-full min-h-[100px] rounded-md border border-input bg-background px-3 py-2 text-sm font-mono"
                      />
                      <div className="flex items-center gap-4">
                        <label className="flex items-center gap-2">
                          <input
                            type="checkbox"
                            checked={editingTemplate.isActive}
                            onChange={(e) =>
                              setEditingTemplate({
                                ...editingTemplate,
                                isActive: e.target.checked,
                              })
                            }
                          />
                          <span className="text-sm">Active</span>
                        </label>
                        <label className="flex items-center gap-2">
                          <input
                            type="checkbox"
                            checked={editingTemplate.isDefault}
                            onChange={(e) =>
                              setEditingTemplate({
                                ...editingTemplate,
                                isDefault: e.target.checked,
                              })
                            }
                          />
                          <span className="text-sm">Default</span>
                        </label>
                      </div>
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
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <FileText className="h-4 w-4 text-muted-foreground" />
                          <h4 className="font-medium">{template.name}</h4>
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
                        <p className="text-xs text-muted-foreground mt-2">
                          {template.bodyHtml?.length || 0} characters &bull;{' '}
                          Updated: {formatDateTime(template.updatedAt || template.createdAt)}
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
              <FileText className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
              <p className="text-muted-foreground">No report templates yet</p>
              <p className="text-sm text-muted-foreground mt-1">
                Click &quot;Seed Defaults&quot; to load templates from config files
              </p>
              <Button className="mt-4" onClick={() => seedDefaultsMutation.mutate()}>
                <RotateCcw className="h-4 w-4 mr-2" />
                Seed Defaults
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
              Are you sure you want to delete this report template? This action cannot be undone.
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
