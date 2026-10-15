import * as Dialog from '@radix-ui/react-dialog';
import { X } from 'lucide-react';

import { Button } from '@/components/ui/button';
import type { QuotaExceededInfo } from '@/api/quota';

export interface QuotaExceededDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  info: QuotaExceededInfo;
  onUpgrade: () => void;
}

const nf = new Intl.NumberFormat('ru-RU');

const dateFmt = new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'long', timeZone: 'UTC' });

function formatReset(iso: string): string | null {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? null : dateFmt.format(d);
}

/**
 * Модалка для HTTP 402. Единственный Electric Lime на экране — CTA «Сменить тариф».
 * Оверлей: матовое стекло (bg-black/60 + backdrop-blur-2xl), дашборд просвечивает.
 * Сама панель плоская: рамка Chrome, без теней.
 */
export function QuotaExceededDialog({ open, onOpenChange, info, onUpgrade }: QuotaExceededDialogProps) {
  const inactive = info.code === 'subscription_inactive';
  const hasCounter = info.requestsUsed !== undefined && info.maxRequests !== undefined;
  const reset = info.resetDate ? formatReset(info.resetDate) : null;

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/60 backdrop-blur-2xl" />
        <Dialog.Content
          className="fixed left-1/2 top-1/2 z-50 w-[calc(100%-2rem)] max-w-md -translate-x-1/2 -translate-y-1/2 rounded-sm border border-zinc-700 bg-black p-6 focus-visible:outline-none sm:p-8"
        >
          <div className="flex items-start justify-between gap-6">
            <Dialog.Title className="text-xs font-medium uppercase tracking-wider text-zinc-400">
              {inactive ? 'Подписка неактивна' : 'Лимит исчерпан'}
            </Dialog.Title>
            <Dialog.Close
              aria-label="Закрыть"
              className="-m-2 p-2 text-zinc-400 hover:text-white"
            >
              <X className="size-4" strokeWidth={1.75} aria-hidden="true" />
            </Dialog.Close>
          </div>

          {hasCounter && !inactive ? (
            <p className="mt-6 text-4xl font-medium leading-none tracking-tight text-white tabular-nums sm:mt-8 sm:text-5xl">
              {nf.format(info.requestsUsed ?? 0)}
              <span className="ml-2 text-sm text-zinc-500 sm:text-base">/ {nf.format(info.maxRequests ?? 0)}</span>
            </p>
          ) : null}

          <Dialog.Description className="mt-4 text-sm leading-relaxed text-zinc-400 sm:mt-6">
            {info.message}
          </Dialog.Description>

          {reset ? (
            <p className="mt-3 text-xs uppercase tracking-wider text-zinc-500 sm:mt-4">
              Сброс счётчиков: <span className="text-zinc-300">{reset}</span>
            </p>
          ) : null}

          {info.correlationId ? (
            <p className="mt-3 font-mono text-xs text-zinc-600 sm:mt-4">ID: {info.correlationId}</p>
          ) : null}

          <div className="mt-8 flex flex-col-reverse gap-3 sm:mt-10 sm:flex-row sm:justify-end">
            <Button variant="outline" onClick={() => onOpenChange(false)} className="w-full sm:w-auto">
              Закрыть
            </Button>
            <Button variant="accent" onClick={onUpgrade} className="w-full sm:w-auto">
              {inactive ? 'Продлить подписку' : 'Сменить тариф'}
            </Button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
