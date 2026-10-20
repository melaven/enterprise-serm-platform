import * as React from 'react';
import { X } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface DialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  children: React.ReactNode;
}

/**
 * Modal overlay с backdrop
 * Accessibility: role="dialog", aria-modal, Escape key handling
 */
export function Dialog({ open, onOpenChange, children }: DialogProps) {
  React.useEffect(() => {
    if (open) {
      document.body.style.overflow = 'hidden';
      
      // Keyboard navigation: Escape closes modal
      const handleEscape = (event: KeyboardEvent) => {
        if (event.key === 'Escape') {
          onOpenChange(false);
        }
      };
      
      document.addEventListener('keydown', handleEscape);
      return () => {
        document.body.style.overflow = '';
        document.removeEventListener('keydown', handleEscape);
      };
    } else {
      document.body.style.overflow = '';
    }
  }, [open, onOpenChange]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80"
      onClick={() => onOpenChange(false)}
      role="presentation"
    >
      {children}
    </div>
  );
}

export interface DialogContentProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
}

/**
 * Контент диалога: ink-950 bg, border-2 border-chrome-600, max-w-2xl
 * Accessibility: role="dialog", aria-modal, aria-labelledby
 */
export const DialogContent = React.forwardRef<HTMLDivElement, DialogContentProps>(
  ({ className, children, ...props }, ref) => (
    <div
      ref={ref}
      role="dialog"
      aria-modal="true"
      aria-labelledby="dialog-title"
      className={cn(
        'relative w-full max-w-2xl rounded-sm border-2 border-chrome-600 bg-ink-950 p-6 shadow-xl',
        'max-h-[90vh] overflow-y-auto',
        className,
      )}
      onClick={(e) => e.stopPropagation()}
      {...props}
    >
      {children}
    </div>
  ),
);
DialogContent.displayName = 'DialogContent';

export interface DialogHeaderProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
}

export function DialogHeader({ className, children, ...props }: DialogHeaderProps) {
  return (
    <div className={cn('mb-6 flex items-start justify-between', className)} {...props}>
      {children}
    </div>
  );
}

export interface DialogTitleProps extends React.HTMLAttributes<HTMLHeadingElement> {
  children: React.ReactNode;
}

export function DialogTitle({ className, children, ...props }: DialogTitleProps) {
  return (
    <h2 id="dialog-title" className={cn('text-2xl font-semibold text-white', className)} {...props}>
      {children}
    </h2>
  );
}

export interface DialogDescriptionProps extends React.HTMLAttributes<HTMLParagraphElement> {
  children: React.ReactNode;
}

export function DialogDescription({ className, children, ...props }: DialogDescriptionProps) {
  return (
    <p className={cn('text-sm text-chrome-400', className)} {...props}>
      {children}
    </p>
  );
}

export interface DialogCloseProps {
  onClose: () => void;
}

export function DialogClose({ onClose }: DialogCloseProps) {
  return (
    <button
      onClick={onClose}
      className="rounded-sm text-chrome-400 transition-colors hover:text-white focus:outline-none focus:ring-2 focus:ring-lime focus:ring-offset-2 focus:ring-offset-ink-950"
      aria-label="Закрыть диалог"
      type="button"
    >
      <X className="h-5 w-5" />
    </button>
  );
}

export interface DialogBodyProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
}

export function DialogBody({ className, children, ...props }: DialogBodyProps) {
  return (
    <div className={cn('space-y-4', className)} {...props}>
      {children}
    </div>
  );
}

export interface DialogFooterProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
}

export function DialogFooter({ className, children, ...props }: DialogFooterProps) {
  return (
    <div className={cn('mt-6 flex items-center justify-end gap-3', className)} {...props}>
      {children}
    </div>
  );
}
