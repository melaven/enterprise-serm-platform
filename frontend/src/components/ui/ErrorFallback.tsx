import type { FallbackProps } from 'react-error-boundary';

export function ErrorFallback({ resetErrorBoundary }: FallbackProps) {
  return (
    <div
      role="alert"
      className="flex min-h-40 flex-col items-center justify-center gap-3 rounded-sm border border-gray-200 bg-white p-6 text-center text-gray-700"
    >
      <p>Something went wrong in this widget</p>
      <button
        type="button"
        onClick={resetErrorBoundary}
        className="rounded-sm border border-gray-300 px-3 py-1.5 text-sm text-gray-800 hover:bg-gray-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gray-900"
      >
        Retry
      </button>
    </div>
  );
}
