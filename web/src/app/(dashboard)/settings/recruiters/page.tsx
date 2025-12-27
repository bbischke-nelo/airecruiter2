'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import {
  Users,
  Plus,
  Edit,
  Trash2,
  Save,
  X,
  Briefcase,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { api } from '@/lib/api';
import { formatDateTime } from '@/lib/utils';

interface Recruiter {
  id: number;
  externalId: string | null;
  name: string;
  email: string | null;
  phone: string | null;
  title: string | null;
  department: string | null;
  publicContactInfo: string | null;
  isActive: boolean;
  requisitionCount: number;
  createdAt: string;
  updatedAt: string | null;
}

export default function RecruitersSettingsPage() {
  const queryClient = useQueryClient();
  const [editingRecruiter, setEditingRecruiter] = useState<Recruiter | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [recruiterToDelete, setRecruiterToDelete] = useState<Recruiter | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [showCannotDeleteAlert, setShowCannotDeleteAlert] = useState(false);
  const [newRecruiter, setNewRecruiter] = useState<Partial<Recruiter>>({
    name: '',
    email: '',
    phone: '',
    title: '',
    department: '',
  });

  // Fetch recruiters
  const { data: recruiters, isLoading } = useQuery<{ data: Recruiter[] }>({
    queryKey: ['recruiters'],
    queryFn: async () => {
      const response = await api.get('/recruiters');
      return response.data;
    },
  });

  // Create recruiter mutation
  const createRecruiterMutation = useMutation({
    mutationFn: async (data: Partial<Recruiter>) => {
      await api.post('/recruiters', {
        name: data.name,
        email: data.email || null,
        phone: data.phone || null,
        title: data.title || null,
        department: data.department || null,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['recruiters'] });
      setIsCreating(false);
      setNewRecruiter({
        name: '',
        email: '',
        phone: '',
        title: '',
        department: '',
      });
    },
  });

  // Update recruiter mutation
  const updateRecruiterMutation = useMutation({
    mutationFn: async (data: Recruiter) => {
      await api.patch(`/recruiters/${data.id}`, {
        name: data.name,
        email: data.email || null,
        phone: data.phone || null,
        title: data.title || null,
        department: data.department || null,
        is_active: data.isActive,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['recruiters'] });
      setEditingRecruiter(null);
    },
  });

  // Delete recruiter mutation
  const deleteRecruiterMutation = useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/recruiters/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['recruiters'] });
    },
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Recruiters</h1>
        <p className="text-muted-foreground">
          Manage recruiter accounts and assignments
        </p>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <Users className="h-5 w-5" />
            Recruiter Accounts
          </CardTitle>
          <Button onClick={() => setIsCreating(true)} disabled={isCreating}>
            <Plus className="h-4 w-4 mr-2" />
            Add Recruiter
          </Button>
        </CardHeader>
        <CardContent>
          {/* New Recruiter Form */}
          {isCreating && (
            <div className="mb-6 p-4 border rounded-lg bg-muted/50">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-medium">New Recruiter</h3>
                <Button variant="ghost" size="icon" onClick={() => setIsCreating(false)}>
                  <X className="h-4 w-4" />
                </Button>
              </div>
              <div className="space-y-4">
                <div className="grid gap-4 md:grid-cols-2">
                  <div>
                    <label className="text-sm font-medium">Name *</label>
                    <Input
                      value={newRecruiter.name || ''}
                      onChange={(e) =>
                        setNewRecruiter({ ...newRecruiter, name: e.target.value })
                      }
                      placeholder="Full name"
                      className="mt-1"
                    />
                  </div>
                  <div>
                    <label className="text-sm font-medium">Email</label>
                    <Input
                      type="email"
                      value={newRecruiter.email || ''}
                      onChange={(e) =>
                        setNewRecruiter({ ...newRecruiter, email: e.target.value })
                      }
                      placeholder="recruiter@company.com"
                      className="mt-1"
                    />
                  </div>
                </div>
                <div className="grid gap-4 md:grid-cols-3">
                  <div>
                    <label className="text-sm font-medium">Phone</label>
                    <Input
                      value={newRecruiter.phone || ''}
                      onChange={(e) =>
                        setNewRecruiter({ ...newRecruiter, phone: e.target.value })
                      }
                      placeholder="(555) 123-4567"
                      className="mt-1"
                    />
                  </div>
                  <div>
                    <label className="text-sm font-medium">Title</label>
                    <Input
                      value={newRecruiter.title || ''}
                      onChange={(e) =>
                        setNewRecruiter({ ...newRecruiter, title: e.target.value })
                      }
                      placeholder="Senior Recruiter"
                      className="mt-1"
                    />
                  </div>
                  <div>
                    <label className="text-sm font-medium">Department</label>
                    <Input
                      value={newRecruiter.department || ''}
                      onChange={(e) =>
                        setNewRecruiter({ ...newRecruiter, department: e.target.value })
                      }
                      placeholder="Human Resources"
                      className="mt-1"
                    />
                  </div>
                </div>
                <div className="flex justify-end gap-2">
                  <Button variant="outline" onClick={() => setIsCreating(false)}>
                    Cancel
                  </Button>
                  <Button
                    onClick={() => createRecruiterMutation.mutate(newRecruiter)}
                    disabled={createRecruiterMutation.isPending || !newRecruiter.name}
                  >
                    <Save className="h-4 w-4 mr-2" />
                    Add Recruiter
                  </Button>
                </div>
              </div>
            </div>
          )}

          {/* Recruiters List */}
          {isLoading ? (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <div key={i} className="animate-pulse p-4 border rounded-lg">
                  <div className="h-4 bg-muted rounded w-1/4 mb-2" />
                  <div className="h-3 bg-muted rounded w-1/2" />
                </div>
              ))}
            </div>
          ) : recruiters?.data?.length ? (
            <div className="space-y-3">
              {recruiters.data.map((recruiter) => (
                <div
                  key={recruiter.id}
                  className="p-4 border rounded-lg hover:border-primary/50 transition-colors"
                >
                  {editingRecruiter?.id === recruiter.id ? (
                    <div className="space-y-4">
                      <div className="grid gap-4 md:grid-cols-2">
                        <div>
                          <label className="text-sm font-medium">Name</label>
                          <Input
                            value={editingRecruiter.name}
                            onChange={(e) =>
                              setEditingRecruiter({
                                ...editingRecruiter,
                                name: e.target.value,
                              })
                            }
                            className="mt-1"
                          />
                        </div>
                        <div>
                          <label className="text-sm font-medium">Email</label>
                          <Input
                            type="email"
                            value={editingRecruiter.email || ''}
                            onChange={(e) =>
                              setEditingRecruiter({
                                ...editingRecruiter,
                                email: e.target.value,
                              })
                            }
                            className="mt-1"
                          />
                        </div>
                      </div>
                      <div className="grid gap-4 md:grid-cols-3">
                        <div>
                          <label className="text-sm font-medium">Phone</label>
                          <Input
                            value={editingRecruiter.phone || ''}
                            onChange={(e) =>
                              setEditingRecruiter({
                                ...editingRecruiter,
                                phone: e.target.value,
                              })
                            }
                            className="mt-1"
                          />
                        </div>
                        <div>
                          <label className="text-sm font-medium">Title</label>
                          <Input
                            value={editingRecruiter.title || ''}
                            onChange={(e) =>
                              setEditingRecruiter({
                                ...editingRecruiter,
                                title: e.target.value,
                              })
                            }
                            className="mt-1"
                          />
                        </div>
                        <div>
                          <label className="text-sm font-medium">Department</label>
                          <Input
                            value={editingRecruiter.department || ''}
                            onChange={(e) =>
                              setEditingRecruiter({
                                ...editingRecruiter,
                                department: e.target.value,
                              })
                            }
                            className="mt-1"
                          />
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          id="isActive"
                          checked={editingRecruiter.isActive}
                          onChange={(e) =>
                            setEditingRecruiter({
                              ...editingRecruiter,
                              isActive: e.target.checked,
                            })
                          }
                        />
                        <label htmlFor="isActive" className="text-sm">
                          Active
                        </label>
                      </div>
                      <div className="flex justify-end gap-2">
                        <Button
                          variant="outline"
                          onClick={() => setEditingRecruiter(null)}
                        >
                          Cancel
                        </Button>
                        <Button
                          onClick={() => updateRecruiterMutation.mutate(editingRecruiter)}
                          disabled={updateRecruiterMutation.isPending}
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
                          <h4 className="font-medium">{recruiter.name}</h4>
                          {!recruiter.isActive && (
                            <span className="px-2 py-0.5 bg-red-100 text-red-800 rounded text-xs">
                              Inactive
                            </span>
                          )}
                          {recruiter.requisitionCount > 0 && (
                            <span className="px-2 py-0.5 bg-muted rounded text-xs flex items-center gap-1">
                              <Briefcase className="h-3 w-3" />
                              {recruiter.requisitionCount} requisitions
                            </span>
                          )}
                        </div>
                        <div className="text-sm text-muted-foreground mt-1 space-y-0.5">
                          {recruiter.title && <p>{recruiter.title}</p>}
                          {recruiter.email && <p>{recruiter.email}</p>}
                          {recruiter.phone && <p>{recruiter.phone}</p>}
                        </div>
                        <p className="text-xs text-muted-foreground mt-2">
                          Added: {formatDateTime(recruiter.createdAt)}
                        </p>
                      </div>
                      <div className="flex gap-2">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => setEditingRecruiter(recruiter)}
                        >
                          <Edit className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => {
                            setRecruiterToDelete(recruiter);
                            if (recruiter.requisitionCount > 0) {
                              setShowCannotDeleteAlert(true);
                            } else {
                              setShowDeleteConfirm(true);
                            }
                          }}
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
              <Users className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
              <p className="text-muted-foreground">No recruiters added yet</p>
              <Button className="mt-4" onClick={() => setIsCreating(true)}>
                <Plus className="h-4 w-4 mr-2" />
                Add First Recruiter
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Cannot Delete Alert */}
      <AlertDialog open={showCannotDeleteAlert} onOpenChange={setShowCannotDeleteAlert}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Cannot Delete Recruiter</AlertDialogTitle>
            <AlertDialogDescription>
              {recruiterToDelete?.name} has {recruiterToDelete?.requisitionCount} assigned requisitions.
              Please reassign or close these requisitions before deleting this recruiter.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogAction onClick={() => setShowCannotDeleteAlert(false)}>
              OK
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Delete Confirmation */}
      <AlertDialog open={showDeleteConfirm} onOpenChange={setShowDeleteConfirm}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Recruiter?</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete {recruiterToDelete?.name}? This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (recruiterToDelete) {
                  deleteRecruiterMutation.mutate(recruiterToDelete.id);
                }
                setShowDeleteConfirm(false);
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
