import { useCallback, useSyncExternalStore } from 'react';
import { useNavigate } from 'react-router-dom';

import { PaywallModal } from '@/features/billing/PaywallModal';
import { quotaStore } from '@/api/quota';

export interface QuotaExceededHostProps {
  /** Куда вести по кнопке «Сменить тариф». */
  upgradePath?: string;
}

/**
 * Монтируется ОДИН раз внутри <BrowserRouter> (рядом с <Toaster />):
 * слушает глобальный стор 402 и показывает модалку поверх любого экрана.
 * 
 * UPDATED: Использует новый PaywallModal для seamless upgrade experience
 */
export function QuotaExceededHost({ upgradePath = '/billing' }: QuotaExceededHostProps) {
  const info = useSyncExternalStore(
    quotaStore.subscribe,
    quotaStore.getSnapshot,
    quotaStore.getServerSnapshot,
  );

  const handleClose = useCallback(() => {
    quotaStore.dismiss();
  }, []);

  if (info === null) return null;

  // Determine reason from quota info message
  let reason: 'parser_limit' | 'review_limit' | 'token_limit' = 'parser_limit';
  if (info.message.toLowerCase().includes('review')) {
    reason = 'review_limit';
  } else if (info.message.toLowerCase().includes('token')) {
    reason = 'token_limit';
  }

  return (
    <PaywallModal
      open
      onClose={handleClose}
      reason={reason}
      usage={{
        used: info.used ?? 0,
        limit: info.limit ?? 0,
      }}
    />
  );
}
