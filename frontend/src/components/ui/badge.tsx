import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

/**
 * Badge варианты (flat-design, без теней)
 */
const badgeVariants = cva(
  "inline-flex items-center rounded-sm border px-2 py-0.5 text-xs font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      variant: {
        default:
          "border-transparent bg-plum-900 text-plum-300 border-plum-700",
        secondary:
          "border-transparent bg-chrome-600/20 text-chrome-300 border-chrome-600",
        destructive:
          "border-transparent bg-destructive/10 text-destructive border-destructive/30",
        success:
          "border-transparent bg-lime text-ink",
        outline:
          "text-chrome-400 border-chrome-600 bg-transparent",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  )
}

export { Badge, badgeVariants }
