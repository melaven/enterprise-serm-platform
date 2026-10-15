import * as React from "react"

import { cn } from "@/lib/utils"
import { Skeleton } from "./skeleton"

/**
 * AsyncView компонент для асинхронных операций
 * Поддерживает loading, error, empty и success состояния
 */

interface AsyncViewProps {
  isLoading?: boolean
  error?: Error | string | null
  isEmpty?: boolean
  emptyMessage?: string
  children: React.ReactNode
  loadingComponent?: React.ReactNode
  errorComponent?: React.ReactNode
  emptyComponent?: React.ReactNode
  className?: string
}

const AsyncView = React.forwardRef<HTMLDivElement, AsyncViewProps>(
  (
    {
      isLoading = false,
      error = null,
      isEmpty = false,
      emptyMessage = "No data available",
      children,
      loadingComponent,
      errorComponent,
      emptyComponent,
      className,
      ...props
    },
    ref
  ) => {
    // Loading state
    if (isLoading) {
      if (loadingComponent) {
        return <>{loadingComponent}</>
      }

      return (
        <div
          ref={ref}
          className={cn("flex flex-col gap-4 p-6", className)}
          {...props}
        >
          <Skeleton className="h-8 w-1/3" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-5/6" />
          <Skeleton className="h-4 w-4/6" />
        </div>
      )
    }

    // Error state
    if (error) {
      if (errorComponent) {
        return <>{errorComponent}</>
      }

      const errorMessage = typeof error === "string" ? error : error.message

      return (
        <div
          ref={ref}
          className={cn(
            "border-2 border-plum-700 bg-plum-900/10 rounded-sm p-6",
            className
          )}
          {...props}
        >
          <div className="flex items-start gap-3">
            <div className="text-plum-300 mt-0.5">
              <svg
                className="w-5 h-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
            </div>
            <div className="flex-1">
              <h4 className="text-sm font-semibold text-plum-300 mb-1">
                Error
              </h4>
              <p className="text-sm text-chrome-400">{errorMessage}</p>
            </div>
          </div>
        </div>
      )
    }

    // Empty state
    if (isEmpty) {
      if (emptyComponent) {
        return <>{emptyComponent}</>
      }

      return (
        <div
          ref={ref}
          className={cn(
            "border-2 border-chrome-600/50 bg-ink-50 rounded-sm p-12 text-center",
            className
          )}
          {...props}
        >
          <div className="text-chrome-500 mb-4">
            <svg
              className="w-12 h-12 mx-auto"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4"
              />
            </svg>
          </div>
          <p className="text-sm text-chrome-400">{emptyMessage}</p>
        </div>
      )
    }

    // Success state with children
    return (
      <div ref={ref} className={cn("", className)} {...props}>
        {children}
      </div>
    )
  }
)

AsyncView.displayName = "AsyncView"

export { AsyncView }
