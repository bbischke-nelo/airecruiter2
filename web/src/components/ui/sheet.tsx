'use client';

import * as React from 'react';
import { X } from 'lucide-react';
import { cn } from '@/lib/utils';

interface SheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  children: React.ReactNode;
}

interface SheetContentProps {
  children: React.ReactNode;
  className?: string;
  side?: 'left' | 'right';
}

interface SheetHeaderProps {
  children: React.ReactNode;
  className?: string;
}

interface SheetTitleProps {
  children: React.ReactNode;
  className?: string;
}

interface SheetDescriptionProps {
  children: React.ReactNode;
  className?: string;
}

const SheetContext = React.createContext<{
  onOpenChange: (open: boolean) => void;
}>({ onOpenChange: () => {} });

export function Sheet({ open, onOpenChange, children }: SheetProps) {
  // Handle escape key
  React.useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onOpenChange(false);
    };
    if (open) {
      document.addEventListener('keydown', handleEscape);
      document.body.style.overflow = 'hidden';
    }
    return () => {
      document.removeEventListener('keydown', handleEscape);
      document.body.style.overflow = '';
    };
  }, [open, onOpenChange]);

  if (!open) return null;

  return (
    <SheetContext.Provider value={{ onOpenChange }}>
      <div className="fixed inset-0 z-50">
        {/* Backdrop */}
        <div
          className="fixed inset-0 bg-black/50 transition-opacity"
          onClick={() => onOpenChange(false)}
        />
        {children}
      </div>
    </SheetContext.Provider>
  );
}

export function SheetContent({ children, className, side = 'right' }: SheetContentProps) {
  const { onOpenChange } = React.useContext(SheetContext);

  return (
    <div
      className={cn(
        'fixed inset-y-0 z-50 flex flex-col bg-background shadow-lg transition-transform',
        side === 'right' ? 'right-0' : 'left-0',
        'w-full max-w-2xl',
        className
      )}
    >
      <button
        onClick={() => onOpenChange(false)}
        className="absolute right-4 top-4 rounded-sm opacity-70 hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring"
      >
        <X className="h-5 w-5" />
        <span className="sr-only">Close</span>
      </button>
      {children}
    </div>
  );
}

export function SheetHeader({ children, className }: SheetHeaderProps) {
  return (
    <div className={cn('flex flex-col space-y-2 p-6 pb-4 border-b', className)}>
      {children}
    </div>
  );
}

export function SheetTitle({ children, className }: SheetTitleProps) {
  return <h2 className={cn('text-lg font-semibold', className)}>{children}</h2>;
}

export function SheetDescription({ children, className }: SheetDescriptionProps) {
  return <p className={cn('text-sm text-muted-foreground', className)}>{children}</p>;
}

export function SheetBody({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cn('flex-1 overflow-y-auto p-6', className)}>{children}</div>;
}

export function SheetFooter({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={cn('flex items-center justify-end gap-2 p-6 pt-4 border-t', className)}>
      {children}
    </div>
  );
}
