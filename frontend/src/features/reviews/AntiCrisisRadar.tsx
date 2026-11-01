import { useCallback, useEffect, useRef, useState, type ChangeEvent, type ReactNode } from 'react';
import {
  Check,
  Clock,
  HandCoins,
  LoaderCircle,
  Lock,
  MessageCircleQuestion,
  Pencil,
  Scale,
  Send,
  ShieldAlert,
  TriangleAlert,
  X,
  type LucideIcon,
} from 'lucide-react';

import {
  ApproveError,
  canPublishCritical,
  type ApproveRequest,
  type ApproveResult,
  type UserRole,
} from './approveDraftLogic.ts';
import { toast } from 'sonner';
import type { DraftResponse, DraftStrategy } from './draftsApi';

/* ------------------------------------------------------------------ */
/* Типы                                                                */
/* ------------------------------------------------------------------ */

export interface CriticalReview {
  /** Внутренний идентификатор отзыва ({review_id} в API). */
  readonly id: string;
  readonly platform: string | null;
  readonly author_hash: string | null;
  readonly rating: number;
  readonly published_at: string | null;
  readonly intercepted_at?: string | null;
  readonly risk_level: string;
  readonly risk_signals?: readonly string[] | null;
  readonly text: string;
}

export type ApproveHandler = (request: ApproveRequest) => Promise<ApproveResult>;

export interface AntiCrisisRadarProps {
  readonly review?: CriticalReview;
  readonly drafts?: readonly DraftResponse[];
  /**
   * Реальный апрув (см. approveDraftApi.ts). Обязан дождаться ответа сервера и при
   * любой неудаче бросить ApproveError: компонент не делает optimistic UI.
   */
  readonly onApprove: ApproveHandler;
  /** Роль текущего пользователя. UI-ограничение: окончательное решение за сервером (403). */
  readonly userRole?: UserRole;
}

/* ------------------------------------------------------------------ */
/* Моковые данные                                                      */
/* ------------------------------------------------------------------ */

export const MOCK_CRITICAL_REVIEW: CriticalReview = {
  id: 'b3c1f5a2-7d0e-4c58-9a41-5e2f6a1d9c03',
  platform: 'yandex',
  author_hash: 'usr_9f3a1c7e2b40',
  rating: 1,
  published_at: '2026-11-01T18:12:00+05:00',
  intercepted_at: '2026-11-01T18:14:00+05:00',
  risk_level: 'critical_risk',
  risk_signals: ['Угроза судом', 'Персональные данные', 'Обращение в регулятор', 'Призыв к бойкоту'],
  text:
    'Вчера вечером на мой телефон пришло SMS от неизвестной организации: там указаны мои ФИО, ' +
    'паспортные данные и адрес. Договор я оформлял только здесь, больше нигде эти данные не оставлял. ' +
    'Это утечка персональных данных. Обращусь в Роскомнадзор и прокуратуру, подам иск о компенсации ' +
    'морального вреда. Всем, кто собирается оставлять здесь документы: не делайте этого.',
};

export const MOCK_RESPONSE_DRAFTS: readonly DraftResponse[] = [
  {
    id: 'draft_legal',
    strategy: 'LEGAL_STRICT',
    body:
      'Здравствуйте. Мы получили ваше обращение и относимся к вопросам защиты персональных данных ' +
      'со всей серьёзностью. Запущена внутренняя проверка, о её результатах мы сообщим в сроки, ' +
      'установленные законодательством. Чтобы идентифицировать ваше обращение, направьте номер договора ' +
      'на privacy@company.example. Просим не публиковать персональные данные в отзыве.',
    is_approved: false,
    approved_by: null,
    approved_at: null,
    created_at: '2026-11-01T18:14:00+05:00',
    updated_at: '2026-11-01T18:14:00+05:00',
  },
  {
    id: 'draft_appeasement',
    strategy: 'APPEASEMENT',
    body:
      'Здравствуйте. Нам очень жаль, что вы столкнулись с такой ситуацией: это не тот уровень ' +
      'доверия, который мы хотим оправдывать. Мы уже начали разбираться, как это могло произойти. ' +
      'Готовы обсудить компенсацию и обязательно свяжемся с вами лично. Напишите нам удобный способ связи ' +
      'на support@company.example, ответим в течение одного рабочего дня.',
    is_approved: false,
    approved_by: null,
    approved_at: null,
    created_at: '2026-11-01T18:14:00+05:00',
    updated_at: '2026-11-01T18:14:00+05:00',
  },
  {
    id: 'draft_info',
    strategy: 'INFO_REQUEST',
    body:
      'Здравствуйте. Спасибо, что сообщили. Чтобы быстрее найти причину, нам нужны детали: время ' +
      'получения SMS, номер отправителя и скриншот сообщения. Пришлите их, пожалуйста, на ' +
      'support@company.example вместе с номером договора. Персональные данные в публичных комментариях ' +
      'указывать не нужно.',
    is_approved: false,
    approved_by: null,
    approved_at: null,
    created_at: '2026-11-01T18:14:00+05:00',
    updated_at: '2026-11-01T18:14:00+05:00',
  },
];

/* ------------------------------------------------------------------ */
/* Справочники и тексты                                                */
/* ------------------------------------------------------------------ */

interface StrategyMeta {
  readonly title: string;
  readonly code: string;
  readonly hint: string;
  readonly icon: LucideIcon;
}

const STRATEGY: Readonly<Record<DraftStrategy, StrategyMeta>> = {
  LEGAL_STRICT: {
    title: 'Юридически строгий',
    code: 'Legal Strict',
    hint: 'Без признания вины, со ссылкой на процедуру проверки.',
    icon: Scale,
  },
  APPEASEMENT: {
    title: 'Сглаживающий с компенсацией',
    code: 'Appeasement',
    hint: 'Извинение и готовность к компенсации в личном порядке.',
    icon: HandCoins,
  },
  INFO_REQUEST: {
    title: 'Запрос деталей',
    code: 'Info Request',
    hint: 'Уточнение фактов через закрытый канал связи.',
    icon: MessageCircleQuestion,
  },
};

const PLATFORM_LABEL: Readonly<Record<string, string>> = {
  yandex: 'Яндекс Карты',
  '2gis': '2ГИС',
};

const RBAC_MESSAGE = 'Требуются права Owner или Admin для публикации ответа категории CRITICAL_RISK';

const FAILURE_MESSAGE: Readonly<Record<'validation' | 'network' | 'server', string>> = {
  validation: 'Сервер отклонил текст: он пустой или не прошёл проверку. Исправьте ответ и повторите.',
  network: 'Нет связи с сервером. Ответ не отправлен, повторите попытку.',
  server: 'Ошибка сервера. Ответ не отправлен, повторите попытку.',
};

const DATE_FORMAT = new Intl.DateTimeFormat('ru-RU', {
  day: '2-digit',
  month: 'long',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
});

const FOCUS =
  'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-gray-900';

const BTN =
  'inline-flex items-center justify-center gap-1.5 rounded-sm border px-3 py-2 text-sm font-medium ' +
  'disabled:cursor-not-allowed disabled:opacity-50 aria-disabled:cursor-not-allowed aria-disabled:opacity-50 ' +
  FOCUS;
const BTN_PRIMARY = `${BTN} border-gray-900 bg-gray-900 text-white hover:bg-black aria-disabled:hover:bg-gray-900`;
const BTN_SECONDARY = `${BTN} border-gray-200 bg-white text-gray-700 hover:bg-gray-50 aria-disabled:hover:bg-white`;

function formatDate(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? '—' : DATE_FORMAT.format(date);
}

/* ------------------------------------------------------------------ */
/* Состояние потока апрува                                             */
/* ------------------------------------------------------------------ */

type FailureKind = 'validation' | 'network' | 'server';

type Flow =
  | { readonly phase: 'idle' }
  | { readonly phase: 'confirm'; readonly draftId: string }
  | { readonly phase: 'sending'; readonly draftId: string }
  | {
      readonly phase: 'approved';
      /** Подтверждённый черновик. null: сервер не назвал его (редкий 409 без approved_draft_id). */
      readonly draftId: string | null;
      readonly origin: 'self' | 'conflict' | 'server';
      readonly outboxQueued: boolean;
      readonly approvedBy: string | null;
      readonly approvedAt: string | null;
    }
  | { readonly phase: 'failed'; readonly draftId: string; readonly kind: FailureKind };

const IDLE_FLOW: Flow = { phase: 'idle' };

/* ------------------------------------------------------------------ */
/* Тултип (монохромный, доступный с клавиатуры)                        */
/* ------------------------------------------------------------------ */

interface TipProps {
  readonly id: string;
  readonly message: string | null;
  readonly wrapperClass?: string;
  readonly align?: 'left' | 'right';
  readonly children: ReactNode;
}

function Tip({ id, message, wrapperClass = '', align = 'left', children }: TipProps) {
  return (
    <span className={`group relative inline-flex ${wrapperClass}`}>
      {children}
      {message !== null && (
        <span
          id={id}
          role="tooltip"
          className={`pointer-events-none absolute bottom-full z-10 mb-1 hidden w-64 rounded-sm border border-gray-900 bg-gray-900 px-3 py-2 text-xs leading-5 text-white group-focus-within:block group-hover:block ${align === 'left' ? 'left-0' : 'right-0'}`}
        >
          {message}
        </span>
      )}
    </span>
  );
}

/* ------------------------------------------------------------------ */
/* Компонент                                                           */
/* ------------------------------------------------------------------ */

export function AntiCrisisRadar({
  review = MOCK_CRITICAL_REVIEW,
  drafts = MOCK_RESPONSE_DRAFTS,
  onApprove,
  userRole = 'admin',
}: AntiCrisisRadarProps) {
  const [texts, setTexts] = useState<Readonly<Record<string, string>>>(() =>
    Object.fromEntries(drafts.map((d) => [d.id, d.body])),
  );
  const [editingId, setEditingId] = useState<string | null>(null);
  const [flow, setFlow] = useState<Flow>(IDLE_FLOW);
  /** Сервер ответил 403, хотя по роли в UI права были: блокируем интерфейс до перезагрузки. */
  const [serverForbidden, setServerForbidden] = useState(false);

  const mounted = useRef(true);
  const inFlight = useRef(false);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  useEffect(() => {
    const approvedDraft = drafts.find((draft) => draft.is_approved);
    if (approvedDraft === undefined) return;

    setFlow((current) => {
      if (
        current.phase === 'approved' &&
        current.draftId === approvedDraft.id &&
        current.approvedBy === approvedDraft.approved_by &&
        current.approvedAt === approvedDraft.approved_at
      ) {
        return current;
      }
      return {
        phase: 'approved',
        draftId: approvedDraft.id,
        origin: 'server',
        outboxQueued: true,
        approvedBy: approvedDraft.approved_by,
        approvedAt: approvedDraft.approved_at,
      };
    });
  }, [drafts]);

  const roleAllowed = canPublishCritical(userRole);
  const readOnly = !roleAllowed || serverForbidden;
  const locked = flow.phase === 'sending' || flow.phase === 'approved';
  const rbacHint = readOnly ? RBAC_MESSAGE : null;

  const send = useCallback(
    async (draftId: string): Promise<void> => {
      if (inFlight.current || readOnly) return;
      const content = (texts[draftId] ?? '').trim();
      if (content.length === 0) return;

      inFlight.current = true;
      setEditingId(null);
      setFlow({ phase: 'sending', draftId });
      try {
        // Никакого optimistic UI: статус меняется только после ответа сервера.
        const result = await onApprove({ reviewId: review.id, draftId, content });
        if (!mounted.current) return;
        setFlow({
          phase: 'approved',
          draftId: result.approved_draft_id,
          origin: 'self',
          outboxQueued: result.outbox_queued,
          approvedBy: result.approved_by,
          approvedAt: result.approved_at,
        });
      } catch (error: unknown) {
        if (!mounted.current) return;
        const kind = error instanceof ApproveError ? error.kind : 'server';
        const errorMessage = error instanceof ApproveError ? error.message : 'Попробуйте ещё раз.';
        toast.error('Не удалось подтвердить ответ', { description: errorMessage });
        if (kind === 'conflict') {
          // Гонка менеджеров: приводим UI к состоянию сервера.
          setFlow({
            phase: 'approved',
            draftId: error instanceof ApproveError ? error.approvedDraftId : null,
            origin: 'conflict',
            outboxQueued: true,
            approvedBy: error instanceof ApproveError ? error.approvedBy : null,
            approvedAt: error instanceof ApproveError ? error.approvedAt : null,
          });
        } else if (kind === 'forbidden') {
          setServerForbidden(true);
          setFlow(IDLE_FLOW);
        } else {
          setFlow({ phase: 'failed', draftId, kind });
        }
      } finally {
        inFlight.current = false;
      }
    },
    [onApprove, readOnly, review.id, texts],
  );

  const approvedFlow = flow.phase === 'approved' ? flow : null;

  return (
    <section aria-labelledby="radar-title" className="mx-auto w-full max-w-5xl space-y-4 text-gray-900">
      {/* Верхняя плашка: критический алерт / консистентное состояние после апрува */}
      {approvedFlow === null && (
        <div role="alert" className="flex items-start gap-3 rounded-sm border border-gray-900 bg-gray-100 px-3 py-3">
          <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0 text-gray-900" aria-hidden="true" />
          <div className="min-w-0 flex-1">
            <h2 id="radar-title" className="text-sm font-semibold text-gray-900">
              Перехвачен отзыв с риском CRITICAL_RISK
            </h2>
            <p className="mt-0.5 text-sm text-gray-700">
              Автоответ заблокирован. SI-Ассистент подготовил {drafts.length} варианта ответа: выберите один и
              подтвердите отправку.
            </p>
          </div>
          <span className="hidden shrink-0 items-center gap-1 text-xs text-gray-700 sm:inline-flex">
            <Clock className="h-3.5 w-3.5" aria-hidden="true" />
            {review.intercepted_at !== null && review.intercepted_at !== undefined
              ? `Перехвачен ${formatDate(review.intercepted_at)}`
              : 'Требует срочного внимания'}
          </span>
        </div>
      )}

      {approvedFlow !== null && approvedFlow.origin === 'conflict' && (
        <div role="alert" className="flex items-start gap-3 rounded-sm border border-gray-900 bg-gray-100 px-3 py-3">
          <TriangleAlert className="mt-0.5 h-5 w-5 shrink-0 text-gray-900" aria-hidden="true" />
          <div className="min-w-0 flex-1">
            <h2 id="radar-title" className="text-sm font-semibold text-gray-900">
              {approvedFlow.approvedBy !== null
                ? `Другой администратор (${approvedFlow.approvedBy}) уже отправил ответ по этому инциденту`
                : 'Другой администратор уже отправил ответ по этому инциденту'}
            </h2>
            <p className="mt-0.5 text-sm text-gray-700">
              Интерфейс синхронизирован с сервером: ваш ответ не отправлен, повторная публикация не требуется.
            </p>
            {approvedFlow.approvedAt !== null && (
              <time className="mt-1 block text-xs text-gray-600" dateTime={approvedFlow.approvedAt}>
                Утверждено {formatDate(approvedFlow.approvedAt)}
              </time>
            )}
          </div>
        </div>
      )}

      {approvedFlow !== null && approvedFlow.origin === 'server' && (
        <div role="status" className="flex items-start gap-3 rounded-sm border border-gray-900 bg-gray-100 px-3 py-3">
          <Check className="mt-0.5 h-5 w-5 shrink-0 text-gray-900" aria-hidden="true" />
          <div className="min-w-0 flex-1">
            <h2 id="radar-title" className="text-sm font-semibold text-gray-900">
              {approvedFlow.approvedBy !== null
                ? `Другой администратор (${approvedFlow.approvedBy}) уже отправил ответ по этому инциденту`
                : 'Ответ по этому инциденту уже утверждён'}
            </h2>
            {approvedFlow.approvedAt !== null && (
              <time className="mt-1 block text-xs text-gray-600" dateTime={approvedFlow.approvedAt}>
                Утверждено {formatDate(approvedFlow.approvedAt)}
              </time>
            )}
          </div>
        </div>
      )}

      {approvedFlow !== null && approvedFlow.origin === 'self' && (
        <div role="status" className="flex items-start gap-3 rounded-sm border border-gray-900 bg-gray-100 px-3 py-3">
          <Check className="mt-0.5 h-5 w-5 shrink-0 text-gray-900" aria-hidden="true" />
          <div className="min-w-0 flex-1">
            <h2 id="radar-title" className="text-sm font-semibold text-gray-900">
              {approvedFlow.outboxQueued ? 'Ответ отправлен в Outbox' : 'Ответ подтверждён'}
            </h2>
            <p className="mt-0.5 text-sm text-gray-700">
              Публикация на площадке выполнится из очереди. Повторная отправка не нужна.
            </p>
          </div>
        </div>
      )}

      {/* RBAC: режим просмотра */}
      {readOnly && (
        <div role="note" className="flex items-start gap-3 rounded-sm border border-gray-300 bg-gray-50 px-3 py-2">
          <Lock className="mt-0.5 h-4 w-4 shrink-0 text-gray-700" aria-hidden="true" />
          <p className="text-sm text-gray-700">
            <span className="font-medium text-gray-900">Режим просмотра.</span> {RBAC_MESSAGE}.
            {serverForbidden && ' Сервер отклонил запрос (403): права вашей роли изменились или недостаточны.'}
          </p>
        </div>
      )}

      {/* Отзыв */}
      <article className="rounded-sm border border-gray-200 bg-white">
        <header className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-gray-200 px-3 py-2 text-xs text-gray-600">
          <span className="font-medium text-gray-900">
            {review.platform === null
              ? 'Площадка не указана'
              : PLATFORM_LABEL[review.platform] ?? review.platform}
          </span>
          {review.published_at !== null && (
            <time dateTime={review.published_at}>{formatDate(review.published_at)}</time>
          )}
          <span className="font-mono">{review.author_hash ?? 'Автор не указан'}</span>
          <span className="inline-flex items-center gap-1.5" aria-label={`Рейтинг ${review.rating} из 5`}>
            <span className="inline-flex gap-0.5" aria-hidden="true">
              {[1, 2, 3, 4, 5].map((n) => (
                <span
                  key={n}
                  className={`h-2.5 w-2.5 border ${n <= review.rating ? 'border-gray-900 bg-gray-900' : 'border-gray-300 bg-white'}`}
                />
              ))}
            </span>
            {review.rating}/5
          </span>
          <span className="ml-auto rounded-sm border border-gray-900 px-2 py-0.5 font-mono text-gray-900">
            {review.risk_level.toUpperCase()}
          </span>
        </header>
        <div className="space-y-3 px-3 py-3">
          <blockquote className="text-sm leading-6 text-gray-800">{review.text}</blockquote>
          {(review.risk_signals?.length ?? 0) > 0 && (
            <ul className="flex flex-wrap gap-1.5" aria-label="Сигналы риска">
              {review.risk_signals?.map((signal) => (
                <li key={signal} className="rounded-sm border border-gray-300 bg-gray-50 px-2 py-0.5 text-xs text-gray-700">
                  {signal}
                </li>
              ))}
            </ul>
          )}
        </div>
      </article>

      {/* Варианты ответа */}
      <div className="grid gap-4 lg:grid-cols-3">
        {drafts.map((draft) => {
          const meta = STRATEGY[draft.strategy];
          const Icon = meta.icon;
          const text = texts[draft.id] ?? draft.body;

          const isEditing = editingId === draft.id && !readOnly;
          const isConfirming = flow.phase === 'confirm' && flow.draftId === draft.id && !readOnly;
          const isSending = flow.phase === 'sending' && flow.draftId === draft.id;
          const isApproved = approvedFlow !== null && approvedFlow.draftId === draft.id;
          const failure = flow.phase === 'failed' && flow.draftId === draft.id ? flow.kind : null;
          const dimmed = (locked && !isSending && !isApproved) || (readOnly && !locked);

          const border = isSending || isApproved ? 'border-gray-900' : 'border-gray-200';
          const surface = isApproved ? 'bg-gray-50' : 'bg-white';

          return (
            <article
              key={draft.id}
              aria-labelledby={`${draft.id}-title`}
              aria-busy={isSending}
              className={`flex min-w-0 flex-col rounded-sm border ${border} ${surface} ${dimmed ? 'opacity-60' : ''}`}
            >
              <header className="flex items-start gap-2 border-b border-gray-200 px-3 py-2">
                <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-sm border border-gray-200 bg-gray-50">
                  <Icon className="h-4 w-4 text-gray-700" aria-hidden="true" />
                </span>
                <div className="min-w-0">
                  <h3 id={`${draft.id}-title`} className="text-sm font-semibold leading-5">
                    {meta.title}
                  </h3>
                  <p className="font-mono text-xs uppercase tracking-wide text-gray-500">{meta.code}</p>
                </div>
              </header>

              <div className="flex-1 space-y-2 px-3 py-3">
                <p className="text-xs text-gray-500">{meta.hint}</p>
                {isEditing ? (
                  <textarea
                    id={`${draft.id}-text`}
                    aria-label={`Текст ответа: ${meta.title}`}
                    value={text}
                    rows={9}
                    disabled={locked}
                    onChange={(e: ChangeEvent<HTMLTextAreaElement>) =>
                      setTexts((prev) => ({ ...prev, [draft.id]: e.target.value }))
                    }
                    className={`w-full resize-y rounded-sm border border-gray-300 bg-white px-3 py-2 text-sm leading-6 text-gray-900 ${FOCUS}`}
                  />
                ) : (
                  <p className="whitespace-pre-line text-sm leading-6 text-gray-800">{text}</p>
                )}
              </div>

              <footer className="space-y-2 border-t border-gray-200 px-3 py-2">
                {isApproved && approvedFlow !== null ? (
                  <div role="status" className="space-y-0.5">
                    <p className="flex items-center gap-1.5 text-sm font-medium text-gray-900">
                      <Check className="h-4 w-4" aria-hidden="true" />
                      {approvedFlow.origin === 'conflict'
                        ? 'Отправлено другим администратором'
                        : approvedFlow.origin === 'server'
                          ? 'Утверждено на сервере'
                        : approvedFlow.outboxQueued
                          ? 'Отправлено в Outbox'
                          : 'Подтверждён'}
                    </p>
                    {(approvedFlow.origin === 'conflict' || approvedFlow.origin === 'server') && (
                      <p className="text-xs text-gray-600">
                        {approvedFlow.approvedBy !== null
                          ? `Подтвердил: ${approvedFlow.approvedBy}.`
                          : 'Автор подтверждения не указан.'}
                        {approvedFlow.approvedAt !== null
                          ? ` Время: ${formatDate(approvedFlow.approvedAt)}.`
                          : ''}
                        {approvedFlow.origin === 'conflict'
                          ? ' Опубликованный текст мог отличаться от показанного здесь.'
                          : ''}
                      </p>
                    )}
                  </div>
                ) : approvedFlow !== null ? (
                  <p className="text-xs text-gray-500">Не отправлен: по инциденту уже подтверждён другой вариант.</p>
                ) : isConfirming ? (
                  <div className="space-y-2">
                    <p className="text-xs text-gray-600">
                      Ответ будет поставлен в очередь публикации от имени компании. Действие нельзя отменить.
                    </p>
                    <div className="flex gap-2">
                      <button type="button" onClick={() => void send(draft.id)} className={`${BTN_PRIMARY} flex-1`}>
                        <Send className="h-4 w-4" aria-hidden="true" />
                        Подтвердить
                      </button>
                      <button type="button" onClick={() => setFlow(IDLE_FLOW)} className={BTN_SECONDARY}>
                        <X className="h-4 w-4" aria-hidden="true" />
                        Отмена
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="flex gap-2">
                    <Tip id={`${draft.id}-approve-tip`} message={rbacHint} wrapperClass="flex-1">
                      <button
                        type="button"
                        disabled={(locked && !readOnly) || (!readOnly && text.trim().length === 0)}
                        aria-disabled={readOnly || undefined}
                        aria-describedby={rbacHint !== null ? `${draft.id}-approve-tip` : undefined}
                        aria-label={`Апрув и Отправка (Approve & Send): ${meta.title}`}
                        onClick={() => {
                          if (readOnly) return;
                          setEditingId(null);
                          setFlow({ phase: 'confirm', draftId: draft.id });
                        }}
                        className={`${BTN_PRIMARY} w-full`}
                      >
                        {isSending ? (
                          <LoaderCircle className="h-4 w-4 animate-spin" aria-hidden="true" />
                        ) : (
                          <Send className="h-4 w-4" aria-hidden="true" />
                        )}
                        {isSending ? 'Отправка…' : 'Апрув и Отправка'}
                      </button>
                    </Tip>
                    <Tip id={`${draft.id}-edit-tip`} message={rbacHint} align="right">
                      <button
                        type="button"
                        disabled={locked && !readOnly}
                        aria-disabled={readOnly || undefined}
                        aria-pressed={isEditing}
                        aria-describedby={rbacHint !== null ? `${draft.id}-edit-tip` : undefined}
                        aria-label={`Редактировать: ${meta.title}`}
                        onClick={() => {
                          if (readOnly) return;
                          setEditingId(isEditing ? null : draft.id);
                        }}
                        className={BTN_SECONDARY}
                      >
                        {isEditing ? (
                          <Check className="h-4 w-4" aria-hidden="true" />
                        ) : (
                          <Pencil className="h-4 w-4" aria-hidden="true" />
                        )}
                      </button>
                    </Tip>
                  </div>
                )}
                {failure !== null && (
                  <p role="alert" className="flex items-start gap-1.5 border border-gray-900 bg-gray-100 px-2 py-1.5 text-xs text-gray-900">
                    <TriangleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                    {FAILURE_MESSAGE[failure]}
                  </p>
                )}
                {isSending && (
                  <p role="status" className="text-xs text-gray-600">
                    Ждём подтверждения сервера. Не закрывайте страницу.
                  </p>
                )}
              </footer>
            </article>
          );
        })}
      </div>
    </section>
  );
}

export default AntiCrisisRadar;
