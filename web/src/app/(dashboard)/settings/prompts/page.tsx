'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import {
  MessageSquare,
  Plus,
  Edit,
  Trash2,
  Save,
  X,
  FileText,
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
import { formatDateTime } from '@/lib/utils';

interface Prompt {
  id: number;
  name: string;
  promptType: string;
  templateContent: string;
  schemaContent: string | null;
  description: string | null;
  requisitionId: number | null;
  isActive: boolean;
  isDefault: boolean;
  version: number;
  createdAt: string;
  updatedAt: string | null;
}

interface PromptListItem {
  id: number;
  name: string;
  promptType: string;
  requisitionId: number | null;
  isActive: boolean;
  isDefault: boolean;
  version: number;
  createdAt: string;
}

const promptTypes = [
  { value: 'resume_analysis', label: 'Resume Analysis' },
  { value: 'interview', label: 'Interview' },
  { value: 'self_service_interview', label: 'Self-Service Interview' },
  { value: 'evaluation', label: 'Evaluation' },
  { value: 'interview_email', label: 'Interview Email' },
];

export default function PromptsSettingsPage() {
  const queryClient = useQueryClient();
  const [editingPrompt, setEditingPrompt] = useState<Prompt | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [showInactive, setShowInactive] = useState(false);
  const [isLoadingPrompt, setIsLoadingPrompt] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null);
  const [newPrompt, setNewPrompt] = useState<Partial<Prompt>>({
    name: '',
    promptType: 'resume_analysis',
    templateContent: '',
    schemaContent: '',
    description: '',
    isDefault: false,
  });

  // Fetch prompts - filter by active unless showInactive is checked
  const { data: prompts, isLoading } = useQuery<{ data: PromptListItem[] }>({
    queryKey: ['prompts', showInactive],
    queryFn: async () => {
      const params = showInactive ? '' : '?is_active=true';
      const response = await api.get(`/prompts${params}`);
      return response.data;
    },
  });

  // Create prompt mutation
  const createPromptMutation = useMutation({
    mutationFn: async (data: Partial<Prompt>) => {
      await api.post('/prompts', {
        name: data.name,
        prompt_type: data.promptType,
        template_content: data.templateContent,
        schema_content: data.schemaContent || null,
        description: data.description || null,
        is_default: data.isDefault,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['prompts'] });
      setIsCreating(false);
      setNewPrompt({
        name: '',
        promptType: 'resume_analysis',
        templateContent: '',
        schemaContent: '',
        description: '',
        isDefault: false,
      });
    },
  });

  // Update prompt mutation
  const updatePromptMutation = useMutation({
    mutationFn: async (data: Prompt) => {
      await api.patch(`/prompts/${data.id}`, {
        name: data.name,
        template_content: data.templateContent,
        schema_content: data.schemaContent || null,
        description: data.description || null,
        is_active: data.isActive,
        is_default: data.isDefault,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['prompts'] });
      setEditingPrompt(null);
    },
  });

  // Delete prompt mutation
  const deletePromptMutation = useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/prompts/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['prompts'] });
    },
  });

  // Fetch full prompt for editing
  const fetchFullPrompt = async (promptId: number) => {
    setIsLoadingPrompt(true);
    try {
      const response = await api.get(`/prompts/${promptId}`);
      // Response uses camelCase from CamelModel
      setEditingPrompt(response.data);
    } catch (error) {
      console.error('Failed to fetch prompt:', error);
    } finally {
      setIsLoadingPrompt(false);
    }
  };

  // Seed defaults mutation
  const seedDefaultsMutation = useMutation({
    mutationFn: async () => {
      await api.post('/prompts/seed');
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['prompts'] });
    },
  });

  // Group prompts by type
  const groupedPrompts = prompts?.data?.reduce(
    (acc, prompt) => {
      const type = prompt.promptType;
      if (!acc[type]) acc[type] = [];
      acc[type].push(prompt);
      return acc;
    },
    {} as Record<string, PromptListItem[]>
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">AI Prompts</h1>
        <p className="text-muted-foreground">
          Configure prompts for resume analysis, interviews, and evaluations
        </p>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <MessageSquare className="h-5 w-5" />
            Prompt Templates
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
              New Prompt
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {/* New Prompt Form */}
          {isCreating && (
            <div className="mb-6 p-4 border rounded-lg bg-muted/50">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-medium">New Prompt</h3>
                <Button variant="ghost" size="icon" onClick={() => setIsCreating(false)}>
                  <X className="h-4 w-4" />
                </Button>
              </div>
              <div className="space-y-4">
                <div className="grid gap-4 md:grid-cols-2">
                  <div>
                    <label className="text-sm font-medium">Name</label>
                    <Input
                      value={newPrompt.name || ''}
                      onChange={(e) =>
                        setNewPrompt({ ...newPrompt, name: e.target.value })
                      }
                      placeholder="Prompt name"
                      className="mt-1"
                    />
                  </div>
                  <div>
                    <label className="text-sm font-medium">Type</label>
                    <select
                      value={newPrompt.promptType || 'resume_analysis'}
                      onChange={(e) =>
                        setNewPrompt({ ...newPrompt, promptType: e.target.value })
                      }
                      className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                    >
                      {promptTypes.map((type) => (
                        <option key={type.value} value={type.value}>
                          {type.label}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
                <div>
                  <label className="text-sm font-medium">Description</label>
                  <Input
                    value={newPrompt.description || ''}
                    onChange={(e) =>
                      setNewPrompt({ ...newPrompt, description: e.target.value })
                    }
                    placeholder="Brief description of this prompt"
                    className="mt-1"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium">Prompt Template</label>
                  <textarea
                    value={newPrompt.templateContent || ''}
                    onChange={(e) =>
                      setNewPrompt({ ...newPrompt, templateContent: e.target.value })
                    }
                    placeholder="Enter the prompt template..."
                    className="mt-1 w-full min-h-[200px] rounded-md border border-input bg-background px-3 py-2 text-sm font-mono"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium">JSON Schema (optional)</label>
                  <textarea
                    value={newPrompt.schemaContent || ''}
                    onChange={(e) =>
                      setNewPrompt({ ...newPrompt, schemaContent: e.target.value })
                    }
                    placeholder='{"type": "object", ...}'
                    className="mt-1 w-full min-h-[100px] rounded-md border border-input bg-background px-3 py-2 text-sm font-mono"
                  />
                </div>
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="isDefault"
                    checked={newPrompt.isDefault || false}
                    onChange={(e) =>
                      setNewPrompt({ ...newPrompt, isDefault: e.target.checked })
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
                    onClick={() => createPromptMutation.mutate(newPrompt)}
                    disabled={createPromptMutation.isPending}
                  >
                    <Save className="h-4 w-4 mr-2" />
                    Create Prompt
                  </Button>
                </div>
              </div>
            </div>
          )}

          {/* Prompts List */}
          {isLoading ? (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <div key={i} className="animate-pulse p-4 border rounded-lg">
                  <div className="h-4 bg-muted rounded w-1/4 mb-2" />
                  <div className="h-3 bg-muted rounded w-1/2" />
                </div>
              ))}
            </div>
          ) : prompts?.data?.length ? (
            <div className="space-y-6">
              {promptTypes.map((type) => {
                const typePrompts = groupedPrompts?.[type.value] || [];
                if (typePrompts.length === 0) return null;

                return (
                  <div key={type.value}>
                    <h3 className="text-sm font-semibold text-muted-foreground mb-3 uppercase tracking-wide">
                      {type.label}
                    </h3>
                    <div className="space-y-3">
                      {typePrompts.map((prompt) => (
                        <div
                          key={prompt.id}
                          className="p-4 border rounded-lg hover:border-primary/50 transition-colors"
                        >
                          {editingPrompt?.id === prompt.id ? (
                            <div className="space-y-4">
                              <Input
                                value={editingPrompt.name}
                                onChange={(e) =>
                                  setEditingPrompt({
                                    ...editingPrompt,
                                    name: e.target.value,
                                  })
                                }
                                placeholder="Name"
                              />
                              <Input
                                value={editingPrompt.description || ''}
                                onChange={(e) =>
                                  setEditingPrompt({
                                    ...editingPrompt,
                                    description: e.target.value,
                                  })
                                }
                                placeholder="Description"
                              />
                              <textarea
                                value={editingPrompt.templateContent}
                                onChange={(e) =>
                                  setEditingPrompt({
                                    ...editingPrompt,
                                    templateContent: e.target.value,
                                  })
                                }
                                className="w-full min-h-[200px] rounded-md border border-input bg-background px-3 py-2 text-sm font-mono"
                              />
                              <textarea
                                value={editingPrompt.schemaContent || ''}
                                onChange={(e) =>
                                  setEditingPrompt({
                                    ...editingPrompt,
                                    schemaContent: e.target.value,
                                  })
                                }
                                placeholder="JSON Schema (optional)"
                                className="w-full min-h-[100px] rounded-md border border-input bg-background px-3 py-2 text-sm font-mono"
                              />
                              <div className="flex items-center gap-4">
                                <label className="flex items-center gap-2">
                                  <input
                                    type="checkbox"
                                    checked={editingPrompt.isActive}
                                    onChange={(e) =>
                                      setEditingPrompt({
                                        ...editingPrompt,
                                        isActive: e.target.checked,
                                      })
                                    }
                                  />
                                  <span className="text-sm">Active</span>
                                </label>
                                <label className="flex items-center gap-2">
                                  <input
                                    type="checkbox"
                                    checked={editingPrompt.isDefault}
                                    onChange={(e) =>
                                      setEditingPrompt({
                                        ...editingPrompt,
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
                                  onClick={() => setEditingPrompt(null)}
                                >
                                  Cancel
                                </Button>
                                <Button
                                  onClick={() => updatePromptMutation.mutate(editingPrompt)}
                                  disabled={updatePromptMutation.isPending}
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
                                  <h4 className="font-medium">{prompt.name}</h4>
                                  {prompt.isDefault && (
                                    <span className="px-2 py-0.5 bg-primary/10 text-primary rounded text-xs">
                                      Default
                                    </span>
                                  )}
                                  {!prompt.isActive && (
                                    <span className="px-2 py-0.5 bg-red-100 text-red-800 rounded text-xs">
                                      Inactive
                                    </span>
                                  )}
                                  <span className="px-2 py-0.5 bg-muted rounded text-xs">
                                    v{prompt.version}
                                  </span>
                                </div>
                                <p className="text-xs text-muted-foreground mt-2">
                                  Created: {formatDateTime(prompt.createdAt)}
                                </p>
                              </div>
                              <div className="flex gap-2">
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  onClick={() => fetchFullPrompt(prompt.id)}
                                  disabled={isLoadingPrompt}
                                >
                                  <Edit className="h-4 w-4" />
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  onClick={() => setDeleteConfirm(prompt.id)}
                                >
                                  <Trash2 className="h-4 w-4 text-destructive" />
                                </Button>
                              </div>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="text-center py-8">
              <MessageSquare className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
              <p className="text-muted-foreground">No prompts configured yet</p>
              <Button className="mt-4" onClick={() => setIsCreating(true)}>
                <Plus className="h-4 w-4 mr-2" />
                Create First Prompt
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteConfirm !== null} onOpenChange={() => setDeleteConfirm(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Prompt</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete this prompt? This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              onClick={() => {
                if (deleteConfirm) {
                  deletePromptMutation.mutate(deleteConfirm);
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
