import { Component, ErrorInfo, ReactNode } from 'react';
import { AlertTriangle } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

/**
 * Global Error Boundary для перехвата необработанных ошибок React
 * Предотвращает "белый экран смерти" и показывает премиальный error screen
 */
export class GlobalErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
    };
  }

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    // Обновляем state чтобы показать fallback UI
    return {
      hasError: true,
      error,
    };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    // Логируем ошибку для debugging
    console.error('🔴 [GlobalErrorBoundary] Caught error:', error);
    console.error('🔴 [GlobalErrorBoundary] Error info:', errorInfo);

    // Сохраняем errorInfo в state для отображения деталей
    this.setState({
      error,
      errorInfo,
    });

    // TODO: Отправить на error tracking сервис (Sentry, LogRocket, etc)
    // reportErrorToService(error, errorInfo);
  }

  handleReload = (): void => {
    // Полная перезагрузка приложения
    window.location.reload();
  };

  handleReset = (): void => {
    // Попытка восстановить состояние без перезагрузки
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
    });
  };

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-screen items-center justify-center bg-ink-950 p-6">
          <div className="w-full max-w-2xl rounded-sm border-2 border-chrome-600 bg-ink-900 p-8 text-center">
            {/* Icon */}
            <div className="mb-6 flex justify-center">
              <div className="flex h-20 w-20 items-center justify-center rounded-sm border-2 border-plum bg-plum/10">
                <AlertTriangle className="h-10 w-10 text-plum" strokeWidth={1.5} />
              </div>
            </div>

            {/* Title */}
            <h1 className="mb-3 text-2xl font-semibold text-white">
              Произошла системная ошибка рендеринга
            </h1>

            {/* Description */}
            <p className="mb-6 text-chrome-400">
              Приложение столкнулось с критической ошибкой. Мы зафиксировали проблему 
              и работаем над её устранением. Попробуйте перезагрузить приложение.
            </p>

            {/* Error Details (только в dev mode) */}
            {import.meta.env.DEV && this.state.error && (
              <div className="mb-6 rounded-sm border-2 border-chrome-600 bg-ink-950 p-4 text-left">
                <div className="mb-2 flex items-center gap-2">
                  <span className="rounded-sm bg-red-500 px-2 py-0.5 text-xs font-mono font-semibold uppercase text-white">
                    DEV MODE
                  </span>
                  <span className="text-xs font-medium text-chrome-400">Error Details</span>
                </div>
                <pre className="overflow-x-auto text-xs text-red-400">
                  {this.state.error.toString()}
                  {this.state.errorInfo && (
                    <>
                      {'\n\n'}
                      Component Stack:
                      {'\n'}
                      {this.state.errorInfo.componentStack}
                    </>
                  )}
                </pre>
              </div>
            )}

            {/* Actions */}
            <div className="flex flex-col gap-3 sm:flex-row sm:justify-center">
              <Button
                variant="accent"
                size="lg"
                onClick={this.handleReload}
                className="min-w-[200px]"
              >
                Перезагрузить приложение
              </Button>
              {import.meta.env.DEV && (
                <Button
                  variant="outline"
                  size="lg"
                  onClick={this.handleReset}
                  className="min-w-[200px]"
                >
                  Попробовать восстановить
                </Button>
              )}
            </div>

            {/* Support */}
            <p className="mt-6 text-xs text-chrome-500">
              Если проблема повторяется, свяжитесь с технической поддержкой:{' '}
              <a 
                href="mailto:support@tenable-serm.com" 
                className="text-plum hover:underline"
              >
                support@tenable-serm.com
              </a>
            </p>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
