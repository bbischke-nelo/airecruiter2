'use client';

import { useState, useEffect } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Mail, Link2, Copy, Check, Loader2, AlertCircle, CheckCircle } from 'lucide-react';
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

interface SendInterviewResponse {
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
  const [result, setResult] = useState<SendInterviewResponse | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Reset state when modal opens/closes
  useEffect(() => {
    if (open && application) {
      setMode('email');
      setEmailOverride('');
      setExpiryDays(7);
      setResult(null);
      setError(null);
      setCopied(false);
    }
  }, [open, application]);

  // Send interview mutation - single step, prepare + activate combined
  const sendMutation = useMutation({
    mutationFn: async () => {
      // First prepare
      await api.post(`/applications/${application?.id}/prepare-interview`, {
        mode,
        emailOverride: emailOverride || undefined,
        expiryDays,
      });
      // Then activate
      const response = await api.post(`/applications/${application?.id}/activate-interview`, {
        method: mode,
        emailOverride: emailOverride || undefined,
      });
      return response.data as SendInterviewResponse;
    },
    onSuccess: (data) => {
      setResult(data);
      setError(null);
      queryClient.invalidateQueries({ queryKey: ['applications'] });
    },
    onError: (err: Error) => {
      setError(err.message || 'Failed to send interview');
    },
  });

  // Handle send button click
  const handleSend = () => {
    setError(null);
    sendMutation.mutate();
  };

  // Copy link to clipboard
  const handleCopyLink = async () => {
    if (result?.interviewUrl) {
      await navigator.clipboard.writeText(result.interviewUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  // Handle done - close and trigger success
  const handleDone = () => {
    onSuccess();
    onOpenChange(false);
  };

  const isLoading = sendMutation.isPending;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>Send AI Interview</DialogTitle>
          <DialogDescription>
            Send an AI-powered screening interview to {application?.candidateName}
          </DialogDescription>
        </DialogHeader>

        <div className="py-4 space-y-6">
          {!result ? (
            <>
              {/* Mode Selection */}
              <div className="space-y-3">
                <Label>Interview Method</Label>
                <div className="grid grid-cols-2 gap-3">
                  <button
                    type="button"
                    onClick={() => setMode('email')}
                    className={cn(
                      'flex flex-col items-center justify-center rounded-md border-2 p-3 cursor-pointer transition-colors',
                      mode === 'email'
                        ? 'border-primary bg-primary/5'
                        : 'border-muted bg-popover hover:bg-accent hover:text-accent-foreground'
                    )}
                  >
                    <Mail className="mb-2 h-5 w-5" />
                    <span className="text-sm font-medium">Send Email</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setMode('link_only')}
                    className={cn(
                      'flex flex-col items-center justify-center rounded-md border-2 p-3 cursor-pointer transition-colors',
                      mode === 'link_only'
                        ? 'border-primary bg-primary/5'
                        : 'border-muted bg-popover hover:bg-accent hover:text-accent-foreground'
                    )}
                  >
                    <Link2 className="mb-2 h-5 w-5" />
                    <span className="text-sm font-medium">Link Only</span>
                  </button>
                </div>
              </div>

              {/* Email Override (for email mode) */}
              {mode === 'email' && (
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

              {/* Expiry Days */}
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
            </>
          ) : (
            /* Success state */
            <div className="space-y-4">
              <div className="flex items-center gap-3 p-4 rounded-lg bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800">
                <CheckCircle className="h-5 w-5 text-green-600 flex-shrink-0" />
                <div>
                  <div className="font-medium text-green-800 dark:text-green-200">
                    {result.emailSent ? 'Interview email sent!' : 'Interview link created!'}
                  </div>
                  {result.emailSent && result.emailSentTo && (
                    <div className="text-sm text-green-700 dark:text-green-300">
                      Sent to {result.emailSentTo}
                    </div>
                  )}
                </div>
              </div>

              <div className="space-y-2">
                <Label>Interview Link</Label>
                <div className="flex gap-2">
                  <Input
                    value={result.interviewUrl}
                    readOnly
                    className="font-mono text-xs"
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
                  Expires: {new Date(result.expiresAt).toLocaleDateString()}
                </p>
              </div>
            </div>
          )}

          {/* Error Display */}
          {error && (
            <div className="flex items-center gap-2 p-3 rounded-md bg-destructive/10 text-destructive">
              <AlertCircle className="h-4 w-4 flex-shrink-0" />
              <span className="text-sm">{error}</span>
            </div>
          )}
        </div>

        <DialogFooter>
          {!result ? (
            <>
              <Button variant="outline" onClick={() => onOpenChange(false)}>
                Cancel
              </Button>
              <Button onClick={handleSend} disabled={isLoading}>
                {isLoading && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                {mode === 'email' ? 'Send Email' : 'Generate Link'}
              </Button>
            </>
          ) : (
            <Button onClick={handleDone}>
              Done
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
