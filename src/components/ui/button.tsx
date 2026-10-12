import { Slot } from '@radix-ui/react-slot';
import { cva, type VariantProps } from 'class-variance-authority';
import * as React from 'react';

import { cn } from '@/lib/utils';

/**
 * Тяжёлая монолитная кнопка: 44px, плотная заливка, 2px, капс с трекингом.
 * Совместима с API shadcn (Button, buttonVariants, asChild).
 */
const buttonVariants = cva(
  'inline-flex shrink-0 items-center justify-center gap-2 whitespace-nowrap rounded-sm border text-sm font-semibold uppercase tracking-wider outline-none disabled:pointer-events-none disabled:opacity-40 [&_svg]:size-4 [&_svg]:shrink-0',
  {
    variants: {
      variant: {
        default: 'border-plum bg-plum text-white hover:border-plum-deep hover:bg-plum-deep',
        outline: 'border-zinc-700 bg-transparent text-zinc-100 hover:border-zinc-500 hover:bg-zinc-900',
        accent: 'border-lime bg-lime text-black hover:border-white hover:bg-white',
        ghost: 'border-transparent bg-transparent text-zinc-300 hover:bg-zinc-900 hover:text-white',
      },
      size: {
        default: 'h-11 px-6',
        sm: 'h-9 px-4 text-xs',
        lg: 'h-12 px-8',
        icon: 'size-11',
      },
    },
    defaultVariants: { variant: 'default', size: 'default' },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, type, ...props }, ref) => {
    const Comp = asChild ? Slot : 'button';
    return (
      <Comp
        ref={ref}
        {...(asChild ? {} : { type: type ?? 'button' })}
        className={cn(buttonVariants({ variant, size }), className)}
        {...props}
      />
    );
  },
);
Button.displayName = 'Button';

export { Button, buttonVariants };
