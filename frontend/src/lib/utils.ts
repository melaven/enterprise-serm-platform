import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

/**
 * Utility для объединения классов Tailwind
 * Используется в shadcn/ui компонентах
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
