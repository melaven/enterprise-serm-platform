import { Component, ErrorInfo, ReactNode } from 'react';
import { AlertTriangle } from 'lucide-react';
import { Button } from './ui/button';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class GlobalErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    // Log error to console (in production, this would go to error tracking service)
    console.error('Global Error Boundary caught an error:', error);
    console.error('Error Info:', errorInfo);
  }

  handleReload = () => {
    // Reload the page to recover from the error
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-ink-950 flex items-center justify-center p-4">
          <div className="max-w-md w-full space-y-6 text-center">
            {/* Error Icon */}
            <div className="flex justify-center">
              <div className="p-4 rounded-full bg-ink-900 border-2 border-chrome-600">
                <AlertTriangle className="h-12 w-12 text-plum" strokeWidth={1.5} />
              </div>
            </div>

            {/* Error Message */}
            <div className="space-y-2">
              <h1 className="text-2xl font-semibold text-white">
                Что-то пошло не так
              </h1>
              <p className="text-chrome-400">
                Произошла непредвиденная ошибка. Не волнуйтесь, ваши данные в безопасности.
              </p>
              {this.state.error && (
                <p className="text-sm text-chrome-500 font-mono mt-4">
                  {this.state.error.message}
                </p>
              )}
            </div>

            {/* Reload Button */}
            <Button
              onClick={this.handleReload}
              variant="default"
              size="lg"
              className="w-full bg-lime hover:bg-lime/90 text-ink-950 font-semibold"
            >
              Перезагрузить систему
            </Button>

            {/* Support Info */}
            <p className="text-xs text-chrome-500">
              Если проблема повторяется, пожалуйста, свяжитесь с поддержкой
            </p>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
