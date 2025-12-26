'use client';

import { useState, useEffect } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Mail, Link2, Copy, Check, Loader2, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';

interface PrepareInterviewResponse {
  interviewId: number;
  interviewToken: string;
  interviewUrl: string;
  expiresAt: string;
  emailPreview: {
    toEmail: string;
    subject: string;
    bodyHtml: string;
  };
}

interface ActivateInterviewResponse {
  interviewId: number;
  interviewUrl: string;
  expiresAt: string;
  emailSent: boolean;
  emailSentTo: string | null;
}

interface Application {
  id: number;
  candidateName: string;
  candidateEmail: string | null;
  requisitionName: string;
}

interface SendInterviewModalProps {
  application: Application | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess: () => void;
}

type SendMode = 'email' | 'link_only';

export function SendInterviewModal({
  application,
  open,
  onOpenChange,
  onSuccess,
}: SendInterviewModalProps) {
  const queryClient = useQueryClient();

  const [mode, setMode] = useState<SendMode>('email');
  const [emailOverride, setEmailOverride] = useState('');
  const [expiryDays, setExpiryDays] = useState(7);
  const [preparedData, setPreparedData] = useState<PrepareInterviewResponse | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Reset state when modal opens/closes
  useEffect(() => {
    if (open && application) {
      setMode('email');
      setEmailOverride('');
      setExpiryDays(7);
      setPreparedData(null);
      setError(null);
      setCopied(false);
    }
  }, [open, application]);

  // Prepare interview mutation
  const prepareMutation = useMutation({
    mutationFn: async () => {
      const response = await api.post(`/applications/${application?.id}/prepare-interview`, {
        emailOverride: emailOverride || undefined,
        expiryDays,
      });
      return response.data as PrepareInterviewResponse;
    },
    onSuccess: (data) => {
      setPreparedData(data);
      setError(null);
    },
    onError: (err: Error) => {
      setError(err.message || 'Failed to prepare interview');
    },
  });

  // Activate interview mutation
  const activateMutation = useMutation({
    mutationFn: async () => {
      const response = await api.post(`/applications/${application?.id}/activate-interview`, {
        method: mode,
        emailOverride: emailOverride || undefined,
      });
      return response.data as ActivateInterviewResponse;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['applications'] });
      onSuccess();
      onOpenChange(false);
    },
    onError: (err: Error) => {
      setError(err.message || 'Failed to send interview');
    },
  });

  // Handle prepare button click
  const handlePrepare = () => {
    setError(null);
    prepareMutation.mutate();
  };

  // Handle send/activate button click
  const handleSend = () => {
    setError(null);
    activateMutation.mutate();
  };

  // Copy link to clipboard
  const handleCopyLink = async () => {
    if (preparedData?.interviewUrl) {
      await navigator.clipboard.writeText(preparedData.interviewUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const isPreparing = prepareMutation.isPending;
  const isActivating = activateMutation.isPending;
  const isLoading = isPreparing || isActivating;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle>Send AI Interview</DialogTitle>
          <DialogDescription>
            Send an AI-powered screening interview to {application?.candidateName}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 py-4">
          {/* Mode Selection */}
          <div className="space-y-3">
            <Label>Interview Method</Label>
            <div className="grid grid-cols-2 gap-4">
              <button
                type="button"
                onClick={() => !preparedData && setMode('email')}
                disabled={!!preparedData}
                className={cn(
                  'flex flex-col items-center justify-between rounded-md border-2 p-4 cursor-pointer transition-colors',
                  mode === 'email'
                    ? 'border-primary bg-primary/5'
                    : 'border-muted bg-popover hover:bg-accent hover:text-accent-foreground',
                  preparedData && 'opacity-50 cursor-not-allowed'
                )}
              >
                <Mail className="mb-3 h-6 w-6" />
                <span className="text-sm font-medium">Send Email</span>
                <span className="text-xs text-muted-foreground text-center mt-1">
                  Candidate receives email with interview link
                </span>
              </button>
              <button
                type="button"
                onClick={() => !preparedData && setMode('link_only')}
                disabled={!!preparedData}
                className={cn(
                  'flex flex-col items-center justify-between rounded-md border-2 p-4 cursor-pointer transition-colors',
                  mode === 'link_only'
                    ? 'border-primary bg-primary/5'
                    : 'border-muted bg-popover hover:bg-accent hover:text-accent-foreground',
                  preparedData && 'opacity-50 cursor-not-allowed'
                )}
              >
                <Link2 className="mb-3 h-6 w-6" />
                <span className="text-sm font-medium">Link Only</span>
                <span className="text-xs text-muted-foreground text-center mt-1">
                  Generate link to share manually
                </span>
              </button>
            </div>
          </div>

          {/* Email Override (for email mode) */}
          {mode === 'email' && !preparedData && (
            <div className="space-y-2">
              <Label htmlFor="email-override">Email Address</Label>
              <Input
                id="email-override"
                type="email"
                placeholder={application?.candidateEmail || 'Enter email address'}
                value={emailOverride}
                onChange={(e) => setEmailOverride(e.target.value)}
              />
              <p className="text-xs text-muted-foreground">
                Leave blank to use candidate's email on file
                {application?.candidateEmail && `: ${application.candidateEmail}`}
              </p>
            </div>
          )}

          {/* Expiry Days (before prepare) */}
          {!preparedData && (
            <div className="space-y-2">
              <Label htmlFor="expiry-days">Link Expires In</Label>
              <div className="flex items-center gap-2">
                <Input
                  id="expiry-days"
                  type="number"
                  min={1}
                  max={30}
                  value={expiryDays}
                  onChange={(e) => setExpiryDays(parseInt(e.target.value) || 7)}
                  className="w-20"
                />
                <span className="text-sm text-muted-foreground">days</span>
              </div>
            </div>
          )}

          {/* Prepared Data Preview */}
          {preparedData && (
            <div className="space-y-4">
              {/* Interview Link */}
              <div className="space-y-2">
                <Label>Interview Link</Label>
                <div className="flex gap-2">
                  <Input
                    value={preparedData.interviewUrl}
                    readOnly
                    className="font-mono text-sm"
                  />
                  <Button
                    variant="outline"
                    size="icon"
                    onClick={handleCopyLink}
                    title="Copy link"
                  >
                    {copied ? (
                      <Check className="h-4 w-4 text-green-600" />
                    ) : (
                      <Copy className="h-4 w-4" />
                    )}
                  </Button>
                </div>
                <p className="text-xs text-muted-foreground">
                  Expires: {new Date(preparedData.expiresAt).toLocaleDateString()}
                </p>
              </div>

              {/* Email Preview (for email mode) */}
              {mode === 'email' && (
                <div className="space-y-2">
                  <Label>Email Preview</Label>
                  <div className="rounded-md border p-4 bg-muted/50">
                    <div className="text-sm space-y-2">
                      <p>
                        <span className="text-muted-foreground">To:</span>{' '}
                        {preparedData.emailPreview.toEmail}
                      </p>
                      <p>
                        <span className="text-muted-foreground">Subject:</span>{' '}
                        {preparedData.emailPreview.subject}
                      </p>
                      <div className="mt-4 pt-4 border-t">
                        <div
                          className="prose prose-sm max-w-none dark:prose-invert"
                          dangerouslySetInnerHTML={{
                            __html: preparedData.emailPreview.bodyHtml,
                          }}
                        />
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Error Display */}
          {error && (
            <div className="flex items-center gap-2 p-3 rounded-md bg-destructive/10 text-destructive">
              <AlertCircle className="h-4 w-4" />
              <span className="text-sm">{error}</span>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          {!preparedData ? (
            <Button onClick={handlePrepare} disabled={isLoading}>
              {isPreparing && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              Preview
            </Button>
          ) : (
            <Button onClick={handleSend} disabled={isLoading}>
              {isActivating && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              {mode === 'email' ? 'Send Email' : 'Activate Link'}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
