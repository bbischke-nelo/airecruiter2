'use client';

import ReactMarkdown from 'react-markdown';
import remarkBreaks from 'remark-breaks';
import { cn } from '@/lib/utils';

interface MarkdownProps {
  children: string;
  className?: string;
}

/**
 * Markdown component for rendering AI-generated text.
 * Uses remark-breaks to preserve single line breaks as <br> elements.
 */
export function Markdown({ children, className }: MarkdownProps) {
  return (
    <div className={cn('prose prose-sm max-w-none prose-p:my-2 prose-p:leading-relaxed', className)}>
      <ReactMarkdown remarkPlugins={[remarkBreaks]}>{children}</ReactMarkdown>
    </div>
  );
}
