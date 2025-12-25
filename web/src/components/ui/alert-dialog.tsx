'use client';

import * as React from 'react';
import { cn } from '@/lib/utils';
import { Button } from './button';

interface AlertDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  children: React.ReactNode;
}

interface AlertDialogContentProps {
  children: React.ReactNode;
  className?: string;
}

interface AlertDialogHeaderProps {
  children: React.ReactNode;
  className?: string;
}

interface AlertDialogFooterProps {
  children: React.ReactNode;
  className?: string;
}

interface AlertDialogTitleProps {
  children: React.ReactNode;
  className?: string;
}

interface AlertDialogDescriptionProps {
  children: React.ReactNode;
  className?: string;
}

const AlertDialogContext = React.createContext<{
  onOpenChange: (open: boolean) => void;
}>({ onOpenChange: () => {} });

export function AlertDialog({ open, onOpenChange, children }: AlertDialogProps) {
  if (!open) return null;

  return (
    <AlertDialogContext.Provider value={{ onOpenChange }}>
      <div className="fixed inset-0 z-50 flex items-center justify-center">
        {/* Backdrop */}
        <div
          className="fixed inset-0 bg-black/50"
          onClick={() => onOpenChange(false)}
        />
        {/* Content */}
        {children}
      </div>
    </AlertDialogContext.Provider>
  );
}

export function AlertDialogContent({ children, className }: AlertDialogContentProps) {
  return (
    <div
      className={cn(
        'relative z-50 w-full max-w-md rounded-lg bg-background p-6 shadow-lg',
        className
      )}
    >
      {children}
    </div>
  );
}

export function AlertDialogHeader({ children, className }: AlertDialogHeaderProps) {
  return (
    <div className={cn('flex flex-col space-y-2 text-center sm:text-left', className)}>
      {children}
    </div>
  );
}

export function AlertDialogFooter({ children, className }: AlertDialogFooterProps) {
  return (
    <div
      className={cn(
        'flex flex-col-reverse sm:flex-row sm:justify-end sm:space-x-2 mt-4',
        className
      )}
    >
      {children}
    </div>
  );
}

export function AlertDialogTitle({ children, className }: AlertDialogTitleProps) {
  return <h2 className={cn('text-lg font-semibold', className)}>{children}</h2>;
}

export function AlertDialogDescription({ children, className }: AlertDialogDescriptionProps) {
  return (
    <p className={cn('text-sm text-muted-foreground', className)}>{children}</p>
  );
}

export function AlertDialogCancel({
  children,
  onClick,
}: {
  children: React.ReactNode;
  onClick?: () => void;
}) {
  const { onOpenChange } = React.useContext(AlertDialogContext);
  return (
    <Button
      variant="outline"
      onClick={() => {
        onClick?.();
        onOpenChange(false);
      }}
    >
      {children}
    </Button>
  );
}

export function AlertDialogAction({
  children,
  onClick,
  variant = 'default',
}: {
  children: React.ReactNode;
  onClick?: () => void;
  variant?: 'default' | 'destructive';
}) {
  const { onOpenChange } = React.useContext(AlertDialogContext);
  return (
    <Button
      variant={variant}
      onClick={() => {
        onClick?.();
        onOpenChange(false);
      }}
    >
      {children}
    </Button>
  );
}
