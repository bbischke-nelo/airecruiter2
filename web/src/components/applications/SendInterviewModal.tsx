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

  // Send interview mutation - prepare + activate in one step
  const sendMutation = useMutation({
    mutationFn: async () => {
      // Prepare interview
      await api.post(`/applications/${application?.id}/prepare-interview`, {
        mode,
        emailOverride: emailOverride || undefined,
        expiryDays,
      });
      // Activate interview
      const response = await api.post(`/applications/${application?.id}/activate-interview`, {
        method: mode,
        emailOverride: emailOverride || undefined,
      });
      return response.data as SendInterviewResponse;
    },
    onSuccess: async (data) => {
      setResult(data);
      setError(null);
      queryClient.invalidateQueries({ queryKey: ['applications'] });
      // Auto-copy link for link_only mode
      if (mode === 'link_only' && data.interviewUrl) {
        await navigator.clipboard.writeText(data.interviewUrl);
        setCopied(true);
        setTimeout(() => setCopied(false), 3000);
      }
    },
    onError: (err: Error) => {
      setError(err.message || 'Failed to send interview');
    },
  });

  const handleSend = () => {
    setError(null);
    sendMutation.mutate();
  };

  const handleCopyLink = async () => {
    if (result?.interviewUrl) {
      await navigator.clipboard.writeText(result.interviewUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleDone = () => {
    onSuccess();
    onOpenChange(false);
  };

  const isLoading = sendMutation.isPending;
  const effectiveEmail = emailOverride || application?.candidateEmail;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[440px]">
        <DialogHeader>
          <DialogTitle>Send Interview</DialogTitle>
          <DialogDescription>
            {application?.candidateName} &bull; {application?.requisitionName}
          </DialogDescription>
        </DialogHeader>

        <div className="py-4">
          {!result ? (
            <div className="space-y-5">
              {/* Mode Selection - Simple toggle buttons */}
              <div className="flex rounded-lg border p-1 bg-muted/30">
                <button
                  type="button"
                  onClick={() => setMode('email')}
                  className={cn(
                    'flex-1 flex items-center justify-center gap-2 py-2 px-3 rounded-md text-sm font-medium transition-colors',
                    mode === 'email'
                      ? 'bg-background shadow-sm'
                      : 'text-muted-foreground hover:text-foreground'
                  )}
                >
                  <Mail className="h-4 w-4" />
                  Email
                </button>
                <button
                  type="button"
                  onClick={() => setMode('link_only')}
                  className={cn(
                    'flex-1 flex items-center justify-center gap-2 py-2 px-3 rounded-md text-sm font-medium transition-colors',
                    mode === 'link_only'
                      ? 'bg-background shadow-sm'
                      : 'text-muted-foreground hover:text-foreground'
                  )}
                >
                  <Link2 className="h-4 w-4" />
                  Link Only
                </button>
              </div>

              {/* Email field (only for email mode) */}
              {mode === 'email' && (
                <div className="space-y-2">
                  <Label htmlFor="email">Send to</Label>
                  <Input
                    id="email"
                    type="email"
                    placeholder={application?.candidateEmail || 'Enter email'}
                    value={emailOverride}
                    onChange={(e) => setEmailOverride(e.target.value)}
                  />
                  <p className="text-xs text-muted-foreground">
                    {emailOverride
                      ? 'One-time override (won\'t update candidate record)'
                      : application?.candidateEmail
                        ? `Using: ${application.candidateEmail}`
                        : 'No email on file'}
                  </p>
                </div>
              )}

              {/* Expiry - inline with label */}
              <div className="flex items-center justify-between">
                <Label htmlFor="expiry" className="text-muted-foreground">
                  Link expires in
                </Label>
                <div className="flex items-center gap-2">
                  <Input
                    id="expiry"
                    type="number"
                    min={1}
                    max={30}
                    value={expiryDays}
                    onChange={(e) => setExpiryDays(parseInt(e.target.value) || 7)}
                    className="w-16 text-center"
                  />
                  <span className="text-sm text-muted-foreground">days</span>
                </div>
              </div>
            </div>
          ) : (
            /* Success state */
            <div className="space-y-4">
              <div className="flex items-center gap-3 p-4 rounded-lg bg-green-50 dark:bg-green-900/20">
                <CheckCircle className="h-5 w-5 text-green-600 flex-shrink-0" />
                <div>
                  <div className="font-medium text-green-800 dark:text-green-200">
                    {result.emailSent ? 'Email sent!' : 'Link copied to clipboard!'}
                  </div>
                  {result.emailSent && result.emailSentTo && (
                    <div className="text-sm text-green-700 dark:text-green-300">
                      {result.emailSentTo}
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
                  >
                    {copied ? (
                      <Check className="h-4 w-4 text-green-600" />
                    ) : (
                      <Copy className="h-4 w-4" />
                    )}
                  </Button>
                </div>
                <p className="text-xs text-muted-foreground">
                  Expires {new Date(result.expiresAt).toLocaleDateString()}
                </p>
              </div>
            </div>
          )}

          {error && (
            <div className="flex items-center gap-2 p-3 rounded-md bg-destructive/10 text-destructive mt-4">
              <AlertCircle className="h-4 w-4 flex-shrink-0" />
              <span className="text-sm">{error}</span>
            </div>
          )}
        </div>

        <DialogFooter>
          {!result ? (
            <>
              <Button variant="ghost" onClick={() => onOpenChange(false)}>
                Cancel
              </Button>
              <Button
                onClick={handleSend}
                disabled={isLoading || (mode === 'email' && !effectiveEmail)}
              >
                {isLoading && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                {mode === 'email' ? 'Send Email' : 'Get Link'}
              </Button>
            </>
          ) : (
            <Button onClick={handleDone} className="w-full">
              Done
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
