import { cn } from "@/lib/utils"

/**
 * Skeleton для loading состояний
 * Flat-design, без анимаций pulse (простая версия)
 */
function Skeleton({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("animate-pulse-slow bg-chrome-600/30 rounded-none", className)}
      {...props}
    />
  )
}

export { Skeleton }
