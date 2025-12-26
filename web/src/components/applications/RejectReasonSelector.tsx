'use client';

import { useState } from 'react';
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

// Must match api/schemas/applications.py RejectionReasonCode
// These are legally defensible, objective reason codes that don't require commentary
export const REJECTION_REASON_CODES = {
  QUAL_LICENSE: 'Missing Required License',
  QUAL_EXPERIENCE: 'Insufficient Experience',
  QUAL_SKILLS: 'Missing Required Skills',
  QUAL_EDUCATION: 'Education Requirements Not Met',
  RETENTION_RISK: 'Retention Risk',
  RECENCY_OF_SKILLS: 'Skills Not Recent',
  OVERQUALIFIED: 'Overqualified',
  LOCATION_MISMATCH: 'Location Mismatch',
  SCHEDULE_MISMATCH: 'Schedule Mismatch',
  SALARY_MISMATCH: 'Salary Expectations Mismatch',
  WITHDREW: 'Candidate Withdrew',
  NO_RESPONSE: 'No Response from Candidate',
  INTERVIEW_INCOMPLETE: 'Interview Not Completed',
  INTERVIEW_PERFORMANCE: 'Interview Performance',
  WORK_AUTHORIZATION: 'Work Authorization Issue',
  DID_NOT_SHOW: 'Did Not Show',
  POSITION_FILLED: 'Position Filled',
  DUPLICATE: 'Duplicate Application',
} as const;

export type RejectionReasonCode = keyof typeof REJECTION_REASON_CODES;

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
  const [reasonCode, setReasonCode] = useState<RejectionReasonCode | ''>('');

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
              onValueChange={(value) => setReasonCode(value as RejectionReasonCode)}
            >
              <SelectTrigger id="reason-code">
                <SelectValue placeholder="Select a reason..." />
              </SelectTrigger>
              <SelectContent>
                {Object.entries(REJECTION_REASON_CODES).map(([code, label]) => (
                  <SelectItem key={code} value={code}>
                    {label}
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
