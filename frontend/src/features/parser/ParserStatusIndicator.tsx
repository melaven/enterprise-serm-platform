import { useEffect, useState } from 'react';
import { Loader2, CheckCircle2, XCircle, Clock } from 'lucide-react';
import { Badge } from '@/components/ui/badge';

/**
 * ParserStatusIndicator — визуализация статуса парсера с анимацией
 * 
 * Статусы:
 * - queued: в очереди (серый бейдж с Clock)
 * - in_progress: выполняется (плюм бейдж с анимированным Loader2)
 * - succeeded: успех (лайм бейдж с CheckCircle2)
 * - failed: ошибка (деструктивный бейдж с XCircle)
 */

export type ParserState = 'queued' | 'in_progress' | 'succeeded' | 'failed';

interface ParserStatusIndicatorProps {
  state: ParserState;
  jobId?: string;
  className?: string;
}

export function ParserStatusIndicator({ state, jobId, className }: ParserStatusIndicatorProps) {
  const [dots, setDots] = useState('');

  // Анимация точек для in_progress
  useEffect(() => {
    if (state !== 'in_progress') return;

    const interval = setInterval(() => {
      setDots((prev) => {
        if (prev === '...') return '';
        return prev + '.';
      });
    }, 500);

    return () => clearInterval(interval);
  }, [state]);

  const stateConfig: Record<
    ParserState,
    {
      label: string;
      icon: typeof Loader2;
      variant: 'default' | 'secondary' | 'success' | 'destructive';
      animate?: boolean;
    }
  > = {
    queued: {
      label: 'В очереди',
      icon: Clock,
      variant: 'secondary',
    },
    in_progress: {
      label: `Выполняется${dots}`,
      icon: Loader2,
      variant: 'default',
      animate: true,
    },
    succeeded: {
      label: 'Завершено',
      icon: CheckCircle2,
      variant: 'success',
    },
    failed: {
      label: 'Ошибка',
      icon: XCircle,
      variant: 'destructive',
    },
  };

  const config = stateConfig[state];
  const Icon = config.icon;

  return (
    <div className={className}>
      <Badge variant={config.variant} className="inline-flex items-center gap-2 px-3 py-1.5">
        <Icon
          className={`h-4 w-4 ${config.animate ? 'animate-spin' : ''}`}
          aria-hidden="true"
        />
        <span className="font-medium">{config.label}</span>
      </Badge>
      {jobId && (
        <p className="mt-1 text-xs text-chrome-500 font-mono">
          ID: {jobId.slice(0, 8)}...
        </p>
      )}
    </div>
  );
}
