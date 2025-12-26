'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useState, useEffect } from 'react';
import { Settings2, Save, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { api } from '@/lib/api';

interface Settings {
  interviewTokenExpiryDays: number;
  autoSendInterviewDefault: boolean;
  advanceStageId: string | null;
  rejectDispositionId: string | null;
}

export default function DefaultsSettingsPage() {
  const queryClient = useQueryClient();
  const [formData, setFormData] = useState<Partial<Settings>>({});
  const [hasChanges, setHasChanges] = useState(false);

  // Fetch current settings
  const { data: settings, isLoading } = useQuery<Settings>({
    queryKey: ['settings'],
    queryFn: async () => {
      const response = await api.get('/settings');
      return response.data;
    },
  });

  // Update form when settings load
  useEffect(() => {
    if (settings) {
      setFormData(settings);
      setHasChanges(false);
    }
  }, [settings]);

  // Update settings mutation
  const updateMutation = useMutation({
    mutationFn: async (data: Partial<Settings>) => {
      await api.patch('/settings', data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] });
      setHasChanges(false);
    },
  });

  const handleChange = (key: keyof Settings, value: string | boolean | number | null) => {
    setFormData(prev => ({ ...prev, [key]: value }));
    setHasChanges(true);
  };

  const handleSave = () => {
    updateMutation.mutate(formData);
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Requisition Defaults</h1>
          <p className="text-muted-foreground">
            Global settings that apply when requisition-specific settings are not configured
          </p>
        </div>
        <Button
          onClick={handleSave}
          disabled={!hasChanges || updateMutation.isPending}
        >
          {updateMutation.isPending ? (
            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
          ) : (
            <Save className="h-4 w-4 mr-2" />
          )}
          Save Changes
        </Button>
      </div>

      {/* Auto-Send Interview Default */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Settings2 className="h-5 w-5" />
            AI Interview Settings
          </CardTitle>
          <CardDescription>
            Default behavior for automatically sending AI interviews to candidates
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label>Auto-send AI Interviews by Default</Label>
              <p className="text-sm text-muted-foreground">
                When enabled, AI interviews will be automatically sent to candidates after analysis.
                This can be overridden per-requisition.
              </p>
            </div>
            <Switch
              checked={formData.autoSendInterviewDefault ?? false}
              onCheckedChange={(checked) => handleChange('autoSendInterviewDefault', checked)}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="interviewExpiryDays">Interview Link Expiry (days)</Label>
            <Input
              id="interviewExpiryDays"
              type="number"
              min={1}
              max={30}
              value={formData.interviewTokenExpiryDays ?? 7}
              onChange={(e) => handleChange('interviewTokenExpiryDays', parseInt(e.target.value) || 7)}
              className="max-w-[200px]"
            />
            <p className="text-sm text-muted-foreground">
              Number of days before interview links expire
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Workday Stage Mapping */}
      <Card>
        <CardHeader>
          <CardTitle>Workday Stage Mapping</CardTitle>
          <CardDescription>
            Configure which Workday stages to use for candidate actions (optional - leave blank to use config defaults)
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="advanceStageId">Advance Stage ID</Label>
            <Input
              id="advanceStageId"
              placeholder="e.g., Interview or Screen"
              value={formData.advanceStageId ?? ''}
              onChange={(e) => handleChange('advanceStageId', e.target.value || null)}
            />
            <p className="text-sm text-muted-foreground">
              Workday Recruiting Stage ID to move candidates to when advanced
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="rejectDispositionId">Reject Disposition ID</Label>
            <Input
              id="rejectDispositionId"
              placeholder="e.g., Not Qualified"
              value={formData.rejectDispositionId ?? ''}
              onChange={(e) => handleChange('rejectDispositionId', e.target.value || null)}
            />
            <p className="text-sm text-muted-foreground">
              Workday Disposition ID to use when rejecting candidates
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
