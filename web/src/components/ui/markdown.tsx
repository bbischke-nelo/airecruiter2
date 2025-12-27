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
 *
 * Prose classes handle:
 * - Bold text (**text**) via prose strong styling
 * - Paragraph spacing via prose-p:my-3
 * - Line height via prose-p:leading-relaxed
 */
export function Markdown({ children, className }: MarkdownProps) {
  return (
    <div className={cn(
      // Base prose styling for markdown elements
      'prose prose-sm max-w-none',
      // Paragraph styling with proper spacing
      'prose-p:my-3 prose-p:leading-relaxed',
      // Strong/bold styling
      'prose-strong:font-semibold',
      // Additional classes (typically text color)
      className
    )}>
      <ReactMarkdown remarkPlugins={[remarkBreaks]}>{children}</ReactMarkdown>
    </div>
  );
}
