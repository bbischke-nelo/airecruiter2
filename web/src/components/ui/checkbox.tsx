'use client';

import * as React from 'react';
import { Check, Minus } from 'lucide-react';
import { cn } from '@/lib/utils';

interface CheckboxProps {
  checked?: boolean;
  indeterminate?: boolean;
  onCheckedChange?: (checked: boolean) => void;
  disabled?: boolean;
  className?: string;
}

export function Checkbox({
  checked = false,
  indeterminate = false,
  onCheckedChange,
  disabled = false,
  className,
}: CheckboxProps) {
  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={indeterminate ? 'mixed' : checked}
      disabled={disabled}
      onClick={() => onCheckedChange?.(!checked)}
      className={cn(
        // Visual size is 16px but touch target is 44px (WCAG compliant)
        'relative h-4 w-4 shrink-0 rounded-sm border border-primary ring-offset-background',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
        'disabled:cursor-not-allowed disabled:opacity-50',
        // Expand touch target with padding (visually hidden)
        'before:absolute before:-inset-3 before:content-[""]',
        (checked || indeterminate) && 'bg-primary text-primary-foreground',
        className
      )}
    >
      {indeterminate ? (
        <Minus className="h-3 w-3 mx-auto" />
      ) : checked ? (
        <Check className="h-3 w-3 mx-auto" />
      ) : null}
    </button>
  );
}
