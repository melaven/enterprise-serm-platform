import { useState } from 'react';
import { toast } from 'sonner';
import { DashboardLayout } from '@/features/dashboard/DashboardLayout';
import { useAppStore } from '@/store/useAppStore';

/**
 * SIConfigPage — SI Core Configuration Page
 * 
 * Features:
 * - Tone of Voice matrix (4 communication styles)
 * - Brand context and compliance guardrails
 * - Autonomy rules with toggles
 * - Live SI preview simulator
 * 
 * Design System: Strict B2B enterprise minimalism with slate palette
 */

type ToneOfVoice = 'corporate' | 'empathetic' | 'friendly' | 'custom';

interface SIConfig {
  toneOfVoice: ToneOfVoice;
  customPrompt: string;
  officialSignature: string;
  escalationChannel: string;
  stopWords: string;
  autoPublish5Stars: boolean;
  instantAlertCritical: boolean;
  requestContractNumber: boolean;
}

const TONE_OPTIONS = [
  {
    value: 'corporate' as const,
    title: 'Строгий корпоративный',
    description: 'B2B, финтех, юристы — сухо, по делу, на «Вы»',
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
      </svg>
    ),
  },
  {
    value: 'empathetic' as const,
    title: 'Эмпатичный сервис',
    description: 'Ритейл, клиники, HoReCa — забота, сглаживание углов',
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
      </svg>
    ),
  },
  {
    value: 'friendly' as const,
    title: 'Дружелюбный эксперт',
    description: 'IT, SaaS, EdTech — живо, без канцеляризмов',
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.828 14.828a4 4 0 01-5.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
  },
  {
    value: 'custom' as const,
    title: 'Кастомная директива',
    description: 'Собственный системный промпт для SI',
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
    ),
  },
];

const SAMPLE_REVIEW = {
  author: 'Александр М.',
  platform: '2GIS',
  rating: 1,
  text: 'Ужасное обслуживание! Ждал 40 минут, менеджер хамил, в итоге даже не извинились. Больше не приду и всем расскажу. Деньги на ветер.',
};

function generateSampleReply(config: SIConfig): string {
  const signatures: Record<ToneOfVoice, string> = {
    corporate: `${config.officialSignature || 'С уважением, Служба контроля качества'}`,
    empathetic: `${config.officialSignature || 'С заботой о вас, команда поддержки'}`,
    friendly: `${config.officialSignature || 'Всегда на связи, команда SentiGuard'}`,
    custom: config.officialSignature,
  };

  const responses: Record<ToneOfVoice, string> = {
    corporate: `Уважаемый ${SAMPLE_REVIEW.author},

Примите наши извинения за доставленные неудобства. Ваше обращение принято к рассмотрению. Ситуация будет проанализирована в соответствии с внутренними процедурами контроля качества.

${config.requestContractNumber ? 'Для ускорения рассмотрения просим предоставить номер договора или заказа.\n\n' : ''}Связаться с нами: ${config.escalationChannel || 'support@company.ru'}

${signatures.corporate}`,

    empathetic: `Здравствуйте, ${SAMPLE_REVIEW.author}!

Нам очень жаль, что вы столкнулись с такой ситуацией. Мы понимаем ваше разочарование и искренне хотим всё исправить.

${config.requestContractNumber ? 'Пожалуйста, напишите нам номер заказа — мы разберёмся в деталях и найдём решение.\n\n' : ''}Мы на связи: ${config.escalationChannel || 'support@company.ru'}

${signatures.empathetic}`,

    friendly: `Привет, ${SAMPLE_REVIEW.author}!

Очень неприятно это слышать 😔 Давайте разберёмся и всё исправим! Никто не должен уходить расстроенным.

${config.requestContractNumber ? 'Скиньте номер заказа, и мы сразу посмотрим, что пошло не так.\n\n' : ''}Пишите сюда: ${config.escalationChannel || 'support@company.ru'}

${signatures.friendly}`,

    custom: config.customPrompt
      ? `[Кастомный промпт применён]\n\n${config.customPrompt}\n\n${signatures.custom}`
      : 'Настройте кастомную директиву в поле ниже',
  };

  return responses[config.toneOfVoice];
}

export default function SIConfigPage() {
  const { user, logout } = useAppStore();
  const [config, setConfig] = useState<SIConfig>({
    toneOfVoice: 'corporate',
    customPrompt: '',
    officialSignature: 'С уважением, Служба контроля качества CloudCore',
    escalationChannel: 'support@company.ru',
    stopWords: 'Не обещать возврат средств без верификации, избегать сленга',
    autoPublish5Stars: true,
    instantAlertCritical: true,
    requestContractNumber: false,
  });

  const [isSaving, setIsSaving] = useState(false);

  const handleSave = async () => {
    setIsSaving(true);
    try {
      // TODO: API integration
      await new Promise((resolve) => setTimeout(resolve, 1500));
      toast.success('Конфигурация SI сохранена', {
        description: 'Настройки применятся к новым отзывам',
      });
    } catch (error) {
      toast.error('Ошибка сохранения', {
        description: error instanceof Error ? error.message : 'Попробуйте снова',
      });
    } finally {
      setIsSaving(false);
    }
  };

  const sampleReply = generateSampleReply(config);

  return (
    <DashboardLayout
      title="Конфигурация SI"
      userEmail={user?.email}
      quota={null}
      online
      onLogout={logout}
    >
      <div className="min-h-full bg-slate-50 p-6">
        {/* Header */}
        <header className="mb-6">
          <h1 className="text-3xl font-bold text-slate-900 mb-2">
            Конфигурация SI-ядра
          </h1>
          <p className="text-sm text-slate-600">
            Настройте правила генерации ответов Synthetic Intelligence для вашего бренда
          </p>
        </header>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column: Configuration */}
          <div className="lg:col-span-2 space-y-6">
            
            {/* Tone of Voice Matrix */}
            <section className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
              <h2 className="text-lg font-semibold text-slate-900 mb-1">
                Tone of Voice — Матрица коммуникации SI
              </h2>
              <p className="text-sm text-slate-500 mb-4">
                Выберите стиль общения для автоматических ответов
              </p>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {TONE_OPTIONS.map((option) => (
                  <button
                    key={option.value}
                    onClick={() => setConfig({ ...config, toneOfVoice: option.value })}
                    className={`
                      p-4
                      border-2
                      rounded-lg
                      text-left
                      transition-all
                      ${
                        config.toneOfVoice === option.value
                          ? 'border-slate-900 bg-slate-50/50 ring-1 ring-slate-900'
                          : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50'
                      }
                    `}
                  >
                    <div className="flex items-start gap-3">
                      <div
                        className={`
                          mt-0.5
                          ${
                            config.toneOfVoice === option.value
                              ? 'text-slate-900'
                              : 'text-slate-400'
                          }
                        `}
                      >
                        {option.icon}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-semibold text-slate-900 mb-1">
                          {option.title}
                        </p>
                        <p className="text-xs text-slate-600 leading-relaxed">
                          {option.description}
                        </p>
                      </div>
                      {config.toneOfVoice === option.value && (
                        <svg
                          className="w-5 h-5 text-slate-900 flex-shrink-0"
                          fill="currentColor"
                          viewBox="0 0 20 20"
                        >
                          <path
                            fillRule="evenodd"
                            d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                            clipRule="evenodd"
                          />
                        </svg>
                      )}
                    </div>
                  </button>
                ))}
              </div>

              {/* Custom Prompt Textarea */}
              {config.toneOfVoice === 'custom' && (
                <div className="mt-4">
                  <label className="block text-sm font-medium text-slate-700 mb-2">
                    Кастомная системная директива
                  </label>
                  <textarea
                    value={config.customPrompt}
                    onChange={(e) => setConfig({ ...config, customPrompt: e.target.value })}
                    placeholder="Введите собственный промпт для SI..."
                    className="
                      w-full
                      min-h-[100px]
                      p-3
                      text-sm
                      text-slate-800
                      bg-white
                      border
                      border-slate-300
                      rounded-md
                      focus:ring-2
                      focus:ring-slate-500
                      focus:border-slate-500
                      focus:outline-none
                      resize-y
                      placeholder:text-slate-400
                    "
                  />
                </div>
              )}
            </section>

            {/* Brand & Compliance */}
            <section className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
              <h2 className="text-lg font-semibold text-slate-900 mb-1">
                Контекст бренда и комплаенс
              </h2>
              <p className="text-sm text-slate-500 mb-4">
                Brand identity и жёсткие ограничения для SI
              </p>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">
                    Официальная подпись
                  </label>
                  <input
                    type="text"
                    value={config.officialSignature}
                    onChange={(e) => setConfig({ ...config, officialSignature: e.target.value })}
                    placeholder="С уважением, Служба контроля качества CloudCore"
                    className="
                      w-full
                      px-3
                      py-2
                      text-sm
                      text-slate-800
                      bg-white
                      border
                      border-slate-200
                      rounded-md
                      focus:ring-2
                      focus:ring-slate-500
                      focus:border-slate-500
                      focus:outline-none
                      placeholder:text-slate-400
                    "
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">
                    Канал эскалации инцидентов
                  </label>
                  <input
                    type="text"
                    value={config.escalationChannel}
                    onChange={(e) => setConfig({ ...config, escalationChannel: e.target.value })}
                    placeholder="support@company.ru или Telegram @support_bot"
                    className="
                      w-full
                      px-3
                      py-2
                      text-sm
                      text-slate-800
                      bg-white
                      border
                      border-slate-200
                      rounded-md
                      focus:ring-2
                      focus:ring-slate-500
                      focus:border-slate-500
                      focus:outline-none
                      placeholder:text-slate-400
                    "
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">
                    Стоп-слова и жёсткие ограничения
                  </label>
                  <textarea
                    value={config.stopWords}
                    onChange={(e) => setConfig({ ...config, stopWords: e.target.value })}
                    placeholder="Чего SI никогда не должен обещать..."
                    className="
                      w-full
                      min-h-[80px]
                      p-3
                      text-sm
                      text-slate-800
                      bg-white
                      border
                      border-slate-200
                      rounded-md
                      focus:ring-2
                      focus:ring-slate-500
                      focus:border-slate-500
                      focus:outline-none
                      resize-y
                      placeholder:text-slate-400
                    "
                  />
                  <p className="text-xs text-slate-500 mt-1">
                    Например: "Не обещать возврат средств без верификации, избегать сленга"
                  </p>
                </div>
              </div>
            </section>

            {/* Autonomy Rules */}
            <section className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
              <h2 className="text-lg font-semibold text-slate-900 mb-1">
                Правила автономности — SI Auto-Pilot
              </h2>
              <p className="text-sm text-slate-500 mb-4">
                Настройте автоматические действия системы
              </p>

              <div className="space-y-4">
                <label className="flex items-center justify-between p-4 bg-slate-50 border border-slate-200 rounded-lg hover:bg-slate-100/50 transition-colors cursor-pointer">
                  <div className="flex-1">
                    <p className="text-sm font-medium text-slate-900 mb-0.5">
                      Авто-публикация ответов на 5 звёзд
                    </p>
                    <p className="text-xs text-slate-600">
                      Без участия оператора — моментальный ответ на позитивные отзывы
                    </p>
                  </div>
                  <button
                    onClick={() =>
                      setConfig({ ...config, autoPublish5Stars: !config.autoPublish5Stars })
                    }
                    className={`
                      relative
                      inline-flex
                      h-6
                      w-11
                      items-center
                      rounded-full
                      transition-colors
                      focus:outline-none
                      focus:ring-2
                      focus:ring-slate-500
                      focus:ring-offset-2
                      ${config.autoPublish5Stars ? 'bg-slate-900' : 'bg-slate-300'}
                    `}
                  >
                    <span
                      className={`
                        inline-block
                        h-4
                        w-4
                        transform
                        rounded-full
                        bg-white
                        transition-transform
                        ${config.autoPublish5Stars ? 'translate-x-6' : 'translate-x-1'}
                      `}
                    />
                  </button>
                </label>

                <label className="flex items-center justify-between p-4 bg-slate-50 border border-slate-200 rounded-lg hover:bg-slate-100/50 transition-colors cursor-pointer">
                  <div className="flex-1">
                    <p className="text-sm font-medium text-slate-900 mb-0.5">
                      Мгновенный алерт в Telegram при критическом отзыве
                    </p>
                    <p className="text-xs text-slate-600">
                      1-2 звезды — instant push-уведомление менеджерам
                    </p>
                  </div>
                  <button
                    onClick={() =>
                      setConfig({ ...config, instantAlertCritical: !config.instantAlertCritical })
                    }
                    className={`
                      relative
                      inline-flex
                      h-6
                      w-11
                      items-center
                      rounded-full
                      transition-colors
                      focus:outline-none
                      focus:ring-2
                      focus:ring-slate-500
                      focus:ring-offset-2
                      ${config.instantAlertCritical ? 'bg-slate-900' : 'bg-slate-300'}
                    `}
                  >
                    <span
                      className={`
                        inline-block
                        h-4
                        w-4
                        transform
                        rounded-full
                        bg-white
                        transition-transform
                        ${config.instantAlertCritical ? 'translate-x-6' : 'translate-x-1'}
                      `}
                    />
                  </button>
                </label>

                <label className="flex items-center justify-between p-4 bg-slate-50 border border-slate-200 rounded-lg hover:bg-slate-100/50 transition-colors cursor-pointer">
                  <div className="flex-1">
                    <p className="text-sm font-medium text-slate-900 mb-0.5">
                      Запрашивать номер договора/заказа при негативе
                    </p>
                    <p className="text-xs text-slate-600">
                      SI автоматически просит детали для верификации проблемы
                    </p>
                  </div>
                  <button
                    onClick={() =>
                      setConfig({
                        ...config,
                        requestContractNumber: !config.requestContractNumber,
                      })
                    }
                    className={`
                      relative
                      inline-flex
                      h-6
                      w-11
                      items-center
                      rounded-full
                      transition-colors
                      focus:outline-none
                      focus:ring-2
                      focus:ring-slate-500
                      focus:ring-offset-2
                      ${config.requestContractNumber ? 'bg-slate-900' : 'bg-slate-300'}
                    `}
                  >
                    <span
                      className={`
                        inline-block
                        h-4
                        w-4
                        transform
                        rounded-full
                        bg-white
                        transition-transform
                        ${config.requestContractNumber ? 'translate-x-6' : 'translate-x-1'}
                      `}
                    />
                  </button>
                </label>
              </div>
            </section>
          </div>

          {/* Right Column: Live Preview */}
          <div className="lg:col-span-1">
            <div className="sticky top-6">
              <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
                <h2 className="text-lg font-semibold text-slate-900 mb-1">
                  Live SI Preview
                </h2>
                <p className="text-sm text-slate-500 mb-4">
                  Симулятор ответа на негатив
                </p>

                {/* Sample Review */}
                <div className="mb-4 p-4 bg-rose-50 border border-rose-200 rounded-lg">
                  <div className="flex items-start gap-3 mb-2">
                    <div className="flex-1">
                      <p className="text-xs font-medium text-slate-600 mb-1">
                        {SAMPLE_REVIEW.platform} • {SAMPLE_REVIEW.author}
                      </p>
                      <div className="flex items-center gap-1 mb-2">
                        {Array.from({ length: 5 }).map((_, i) => (
                          <span
                            key={i}
                            className={`text-sm ${
                              i < SAMPLE_REVIEW.rating ? 'text-rose-500' : 'text-slate-300'
                            }`}
                          >
                            ★
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                  <p className="text-sm text-slate-800 leading-relaxed">
                    {SAMPLE_REVIEW.text}
                  </p>
                </div>

                {/* Generated Reply */}
                <div className="p-4 bg-slate-50 border-l-2 border-slate-400 rounded-r-md">
                  <div className="flex items-center gap-1.5 mb-3">
                    <svg
                      className="w-3.5 h-3.5 text-slate-500"
                      fill="currentColor"
                      viewBox="0 0 20 20"
                    >
                      <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                    </svg>
                    <span className="text-xs text-slate-500 uppercase font-semibold tracking-wide">
                      SentiGuard SI
                    </span>
                  </div>
                  <p className="text-sm text-slate-700 whitespace-pre-wrap leading-relaxed">
                    {sampleReply}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Bottom Action Bar */}
        <div className="mt-6 flex items-center justify-end gap-3">
          <button
            onClick={() =>
              setConfig({
                toneOfVoice: 'corporate',
                customPrompt: '',
                officialSignature: 'С уважением, Служба контроля качества CloudCore',
                escalationChannel: 'support@company.ru',
                stopWords: 'Не обещать возврат средств без верификации, избегать сленга',
                autoPublish5Stars: true,
                instantAlertCritical: true,
                requestContractNumber: false,
              })
            }
            className="
              px-4
              py-2.5
              text-sm
              font-medium
              text-slate-600
              bg-white
              border
              border-slate-300
              rounded-lg
              hover:bg-slate-50
              hover:border-slate-400
              transition-colors
            "
          >
            Сбросить
          </button>
          <button
            onClick={handleSave}
            disabled={isSaving}
            className="
              px-6
              py-2.5
              text-sm
              font-medium
              text-white
              bg-slate-900
              rounded-lg
              hover:bg-slate-800
              active:bg-slate-950
              disabled:opacity-50
              disabled:cursor-not-allowed
              transition-colors
              focus:outline-none
              focus:ring-2
              focus:ring-slate-500
              focus:ring-offset-2
            "
          >
            {isSaving ? 'Сохранение...' : 'Сохранить конфигурацию SI'}
          </button>
        </div>
      </div>
    </DashboardLayout>
  );
}
