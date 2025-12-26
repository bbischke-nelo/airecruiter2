'use client';

import * as React from 'react';
import { cn } from '@/lib/utils';

interface ProgressProps {
  value?: number;
  max?: number;
  className?: string;
  indicatorClassName?: string;
}

export function Progress({
  value = 0,
  max = 100,
  className,
  indicatorClassName,
}: ProgressProps) {
  const percentage = Math.min(Math.max((value / max) * 100, 0), 100);

  return (
    <div
      className={cn(
        'relative h-2 w-full overflow-hidden rounded-full bg-secondary',
        className
      )}
    >
      <div
        className={cn(
          'h-full transition-all',
          percentage >= 70
            ? 'bg-green-500'
            : percentage >= 40
              ? 'bg-yellow-500'
              : 'bg-red-500',
          indicatorClassName
        )}
        style={{ width: `${percentage}%` }}
      />
    </div>
  );
}
