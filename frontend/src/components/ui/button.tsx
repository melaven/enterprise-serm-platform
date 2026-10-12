import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

/**
 * Button варианты (адаптированы под наши правила flat-design)
 * НИКАКИХ ТЕНЕЙ! Только границы и flat цвета
 */
const buttonVariants = cva(
  "inline-flex items-center justify-center whitespace-nowrap rounded-sm text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-plum focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default:
          "bg-plum text-white hover:bg-plum-400 active:bg-plum-600 border-2 border-transparent",
        accent:
          "bg-lime text-black hover:bg-lime/90 active:bg-lime/80 border-2 border-transparent font-semibold",
        destructive:
          "bg-destructive text-destructive-foreground hover:bg-destructive/90 border-2 border-transparent",
        outline:
          "border-2 border-chrome-600 bg-transparent text-chrome-300 hover:bg-ink-50 hover:border-chrome-400 hover:text-white",
        secondary:
          "bg-chrome-600 text-white hover:bg-chrome-500 border-2 border-transparent",
        ghost:
          "bg-transparent text-chrome-400 hover:bg-plum-900/20 hover:text-plum border-2 border-transparent",
        link:
          "text-plum underline-offset-4 hover:underline border-none",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-8 rounded-sm px-3 text-xs",
        lg: "h-12 rounded-sm px-8",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button"
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    )
  }
)
Button.displayName = "Button"

export { Button, buttonVariants }
