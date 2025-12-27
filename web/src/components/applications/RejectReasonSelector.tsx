'use client';

import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogCancel,
} from '@/components/ui/alert-dialog';
import { api } from '@/lib/api';

interface DispositionOption {
  id: string;
  name: string;
  workdayId?: string;
}

// The reason code is now the disposition ID from Workday
export type RejectionReasonCode = string;

interface RejectReasonSelectorProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: (reasonCode: RejectionReasonCode) => void;
  isLoading?: boolean;
  candidateName?: string;
}

export function RejectReasonSelector({
  open,
  onOpenChange,
  onConfirm,
  isLoading = false,
  candidateName,
}: RejectReasonSelectorProps) {
  const [reasonCode, setReasonCode] = useState<string>('');

  // Fetch dispositions from Workday via API
  const { data: dispositions, isLoading: dispositionsLoading } = useQuery<DispositionOption[]>({
    queryKey: ['dispositions'],
    queryFn: async () => {
      const response = await api.get('/settings/dispositions');
      return response.data;
    },
    staleTime: 5 * 60 * 1000, // Cache for 5 minutes
  });

  const handleConfirm = () => {
    if (reasonCode) {
      onConfirm(reasonCode);
      setReasonCode('');
    }
  };

  const handleCancel = () => {
    setReasonCode('');
    onOpenChange(false);
  };

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent className="max-w-lg">
        <AlertDialogHeader>
          <AlertDialogTitle>Reject Application</AlertDialogTitle>
          <AlertDialogDescription>
            {candidateName
              ? `Select a reason for rejecting ${candidateName}'s application.`
              : 'Select a reason for rejection. This will be logged for compliance.'}
          </AlertDialogDescription>
        </AlertDialogHeader>

        <div className="py-4">
          <div className="space-y-2">
            <Label htmlFor="reason-code">Rejection Reason</Label>
            <Select
              value={reasonCode}
              onValueChange={(value) => setReasonCode(value)}
              disabled={dispositionsLoading}
            >
              <SelectTrigger id="reason-code">
                <SelectValue placeholder={dispositionsLoading ? "Loading..." : "Select a reason..."} />
              </SelectTrigger>
              <SelectContent>
                {dispositions?.map((disposition) => (
                  <SelectItem key={disposition.id} value={disposition.id}>
                    {disposition.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <AlertDialogFooter>
          <AlertDialogCancel onClick={handleCancel}>Cancel</AlertDialogCancel>
          <Button
            variant="destructive"
            onClick={handleConfirm}
            disabled={!reasonCode || isLoading}
          >
            {isLoading ? 'Rejecting...' : 'Reject Application'}
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
