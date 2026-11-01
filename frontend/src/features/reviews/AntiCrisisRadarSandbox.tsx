import { useCallback, useMemo, useState } from 'react';
import { FlaskConical, RotateCcw, X } from 'lucide-react';

import { AntiCrisisRadar, MOCK_CRITICAL_REVIEW, MOCK_RESPONSE_DRAFTS, type ApproveHandler } from './AntiCrisisRadar.tsx';
import { ApproveError, type UserRole } from './approveDraftLogic.ts';

/**
 * Песочница для AntiCrisisRadar: мок-сервер с переключаемыми сценариями.
 * Только для разработки: в продакшен-маршрутах используйте AntiCrisisRadar + approveDraft.
 */

export type MockScenario = 'ok' | 'conflict' | 'forbidden' | 'network';

interface ScenarioMeta {
  readonly id: MockScenario;
  readonly label: string;
  readonly hint: string;
}

const SCENARIOS: readonly ScenarioMeta[] = [
  { id: 'ok', label: '200 OK', hint: 'Черновик подтверждён, поставлен в Outbox' },
  { id: 'conflict', label: '409 Conflict (Другой менеджер успел раньше)', hint: 'Подтверждён соседний черновик' },
  { id: 'forbidden', label: '403 Forbidden / Role: member', hint: 'Роль без прав на публикацию' },
  { id: 'network', label: '500 Network Error', hint: 'Ответ не отправлен, можно повторить' },
];

const MOCK_LATENCY_MS = 900;

const DEV_FOCUS =
  'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-gray-900';

function wait(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

/** Мок-сервер: ведёт себя как контракт POST .../approve в выбранном сценарии. */
export function createMockApprove(scenario: MockScenario): ApproveHandler {
  return async ({ draftId }) => {
    await wait(MOCK_LATENCY_MS);
    switch (scenario) {
      case 'ok':
        return {
          approved_draft_id: draftId,
          status: 'approved',
          outbox_queued: true,
          approved_by: 'sandbox-admin',
          approved_at: new Date().toISOString(),
        };
      case 'conflict': {
        const other = MOCK_RESPONSE_DRAFTS.find((d) => d.id !== draftId);
        throw new ApproveError(
          'conflict',
          'Another draft is already approved for this review',
          other?.id ?? null,
        );
      }
      case 'forbidden':
        throw new ApproveError('forbidden', 'Forbidden');
      case 'network':
        throw new ApproveError('network', 'Network Error');
    }
  };
}

export function AntiCrisisRadarSandbox() {
  const [scenario, setScenario] = useState<MockScenario>('ok');
  const [role, setRole] = useState<UserRole>('admin');
  const [panelOpen, setPanelOpen] = useState(true);
  const [resetKey, setResetKey] = useState(0);

  const onApprove = useMemo(() => createMockApprove(scenario), [scenario]);

  const pickScenario = useCallback((next: MockScenario): void => {
    setScenario(next);
    // Сценарий 403 моделирует пользователя с ролью member. Роль можно вернуть вручную,
    // чтобы проверить путь «UI разрешил, сервер отказал».
    if (next === 'forbidden') setRole('member');
  }, []);

  return (
    <div className="mx-auto w-full max-w-5xl space-y-4">
      {panelOpen ? (
        <aside aria-label="Панель симуляции" className="rounded-sm border border-dashed border-gray-400 bg-white px-3 py-2">
          <div className="flex items-center gap-2">
            <FlaskConical className="h-4 w-4 text-gray-700" aria-hidden="true" />
            <h2 className="text-xs font-semibold uppercase tracking-wide text-gray-700">Dev: мок-сервер</h2>
            <button
              type="button"
              onClick={() => setResetKey((k) => k + 1)}
              className={`ml-auto inline-flex items-center gap-1 rounded-sm border border-gray-200 px-2 py-1 text-xs text-gray-700 hover:bg-gray-50 ${DEV_FOCUS}`}
            >
              <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
              Сбросить
            </button>
            <button
              type="button"
              aria-label="Скрыть панель симуляции"
              onClick={() => setPanelOpen(false)}
              className={`rounded-sm border border-gray-200 p-1 text-gray-700 hover:bg-gray-50 ${DEV_FOCUS}`}
            >
              <X className="h-3.5 w-3.5" aria-hidden="true" />
            </button>
          </div>

          <div className="mt-2 grid gap-3 md:grid-cols-[1fr_auto]">
            <fieldset className="min-w-0">
              <legend className="mb-1 text-xs text-gray-500">Ответ сервера на апрув</legend>
              <div className="grid gap-1 sm:grid-cols-2">
                {SCENARIOS.map((s) => (
                  <label
                    key={s.id}
                    className={`flex cursor-pointer items-start gap-2 rounded-sm border px-2 py-1.5 text-xs ${scenario === s.id ? 'border-gray-900 bg-gray-50' : 'border-gray-200'}`}
                  >
                    <input
                      type="radio"
                      name="mock-scenario"
                      checked={scenario === s.id}
                      onChange={() => pickScenario(s.id)}
                      className="mt-0.5 accent-gray-900"
                    />
                    <span className="min-w-0">
                      <span className="block font-medium text-gray-900">{s.label}</span>
                      <span className="block text-gray-500">{s.hint}</span>
                    </span>
                  </label>
                ))}
              </div>
            </fieldset>

            <fieldset>
              <legend className="mb-1 text-xs text-gray-500">Роль пользователя</legend>
              <div className="flex gap-1">
                {(['admin', 'member'] as const).map((r) => (
                  <label
                    key={r}
                    className={`flex cursor-pointer items-center gap-2 rounded-sm border px-2 py-1.5 text-xs ${role === r ? 'border-gray-900 bg-gray-50' : 'border-gray-200'}`}
                  >
                    <input
                      type="radio"
                      name="mock-role"
                      checked={role === r}
                      onChange={() => setRole(r)}
                      className="accent-gray-900"
                    />
                    <span className="font-mono text-gray-900">{r}</span>
                  </label>
                ))}
              </div>
            </fieldset>
          </div>
        </aside>
      ) : (
        <button
          type="button"
          onClick={() => setPanelOpen(true)}
          className={`inline-flex items-center gap-1.5 rounded-sm border border-dashed border-gray-400 bg-white px-2 py-1 text-xs text-gray-700 hover:bg-gray-50 ${DEV_FOCUS}`}
        >
          <FlaskConical className="h-3.5 w-3.5" aria-hidden="true" />
          Dev-панель
        </button>
      )}

      <AntiCrisisRadar
        key={resetKey}
        review={MOCK_CRITICAL_REVIEW}
        drafts={MOCK_RESPONSE_DRAFTS}
        onApprove={onApprove}
        userRole={role}
      />
    </div>
  );
}

export default AntiCrisisRadarSandbox;
