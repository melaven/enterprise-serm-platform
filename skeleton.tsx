import * as React from 'react';

import { cn } from '@/lib/utils';

/** Плоский блок zinc-900, мигает резко (steps), без плавного pulse. */
export function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      aria-hidden="true"
      className={cn('animate-blink rounded-sm bg-zinc-900', className)}
      {...props}
    />
  );
}
