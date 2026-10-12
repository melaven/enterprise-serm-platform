import { useCallback, useSyncExternalStore } from 'react';
import { useNavigate } from 'react-router-dom';

import { QuotaExceededDialog } from '@/components/QuotaExceededDialog';
import { quotaStore } from '@/lib/api/quota.ts';

export interface QuotaExceededHostProps {
  /** Куда вести по кнопке «Сменить тариф». */
  upgradePath?: string;
}

/**
 * Монтируется ОДИН раз внутри <BrowserRouter> (рядом с <Toaster />):
 * слушает глобальный стор 402 и показывает модалку поверх любого экрана.
 */
export function QuotaExceededHost({ upgradePath = '/settings' }: QuotaExceededHostProps) {
  const info = useSyncExternalStore(
    quotaStore.subscribe,
    quotaStore.getSnapshot,
    quotaStore.getServerSnapshot,
  );
  const navigate = useNavigate();

  const handleUpgrade = useCallback(() => {
    quotaStore.dismiss();
    navigate(upgradePath);
  }, [navigate, upgradePath]);

  if (info === null) return null;

  return (
    <QuotaExceededDialog
      open
      onOpenChange={(open) => {
        if (!open) quotaStore.dismiss();
      }}
      info={info}
      onUpgrade={handleUpgrade}
    />
  );
}
