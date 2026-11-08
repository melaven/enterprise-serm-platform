import { useState } from 'react';
import { toast } from 'sonner';
import { DashboardLayout } from '@/features/dashboard/DashboardLayout';
import { useAppStore } from '@/store/useAppStore';

/**
 * IntegrationsPage — Data Sources and Webhooks Management
 * 
 * Features:
 * - Review platforms status (Yandex, 2GIS, Google Business)
 * - Corporate buses and alerting (Telegram, amoCRM, Webhooks)
 * - API token management
 * - Sync controls
 * 
 * Design System: Strict B2B enterprise with slate palette
 */

interface PlatformIntegration {
  id: string;
  name: string;
  icon: React.ReactNode;
  status: 'connected' | 'requires_token' | 'error';
  branches?: number;
  lastSync?: string;
  description: string;
}

interface EscalationChannel {
  id: string;
  name: string;
  icon: React.ReactNode;
  description: string;
  enabled: boolean;
  config?: {
    chatId?: string;
    webhookUrl?: string;
  };
}

export default function IntegrationsPage() {
  const { user, logout } = useAppStore();
  const [isSyncing, setIsSyncing] = useState(false);
  const [isRotating, setIsRotating] = useState(false);
  
  const [platforms] = useState<PlatformIntegration[]>([
    {
      id: 'yandex',
      name: 'Яндекс Карты',
      status: 'connected',
      branches: 4,
      lastSync: '2 мин назад',
      description: 'Автоматический парсинг и публикация ответов',
      icon: (
        <svg className="w-6 h-6 text-red-600" fill="currentColor" viewBox="0 0 24 24">
          <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm-1-13h2v6h-2zm0 8h2v2h-2z" />
        </svg>
      ),
    },
    {
      id: '2gis',
      name: '2ГИС',
      status: 'connected',
      branches: 4,
      lastSync: '5 мин назад',
      description: 'Двусторонняя синхронизация отзывов',
      icon: (
        <svg className="w-6 h-6 text-emerald-600" fill="currentColor" viewBox="0 0 24 24">
          <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z" />
        </svg>
      ),
    },
    {
      id: 'google',
      name: 'Google Business Profile',
      status: 'requires_token',
      description: 'Требуется OAuth токен для доступа к локациям',
      icon: (
        <svg className="w-6 h-6 text-blue-600" fill="currentColor" viewBox="0 0 24 24">
          <path d="M12.545,10.239v3.821h5.445c-0.712,2.315-2.647,3.972-5.445,3.972c-3.332,0-6.033-2.701-6.033-6.032s2.701-6.032,6.033-6.032c1.498,0,2.866,0.549,3.921,1.453l2.814-2.814C17.503,2.988,15.139,2,12.545,2C7.021,2,2.543,6.477,2.543,12s4.478,10,10.002,10c8.396,0,10.249-7.85,9.426-11.748L12.545,10.239z" />
        </svg>
      ),
    },
  ]);

  const [channels, setChannels] = useState<EscalationChannel[]>([
    {
      id: 'telegram',
      name: 'Telegram SI-Bot',
      description: 'Мгновенные алерты об отзывах 1-2 звезды в чат руководства',
      enabled: true,
      config: { chatId: '-1001234567890' },
      icon: (
        <svg className="w-6 h-6 text-blue-500" fill="currentColor" viewBox="0 0 24 24">
          <path d="M9.78 18.65l.28-4.23 7.68-6.92c.34-.31-.07-.46-.52-.19L7.74 13.3 3.64 12c-.88-.25-.89-.86.2-1.3l15.97-6.16c.73-.33 1.43.18 1.15 1.3l-2.72 12.81c-.19.91-.74 1.13-1.5.71L12.6 16.3l-1.99 1.93c-.23.23-.42.42-.83.42z" />
        </svg>
      ),
    },
    {
      id: 'amocrm',
      name: 'amoCRM',
      description: 'Авто-создание сделки/задачи в воронке контроля качества при негативе',
      enabled: false,
      config: { webhookUrl: '' },
      icon: (
        <svg className="w-6 h-6 text-orange-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
      ),
    },
    {
      id: 'webhook',
      name: 'Custom Outbox Webhook',
      description: 'Отправка подписанных JSON-событий review.reply.publish_requested во внутреннюю ERP',
      enabled: false,
      config: { webhookUrl: '' },
      icon: (
        <svg className="w-6 h-6 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
        </svg>
      ),
    },
  ]);

  const [configModal, setConfigModal] = useState<{
    type: 'platform' | 'channel';
    id: string;
    title: string;
  } | null>(null);

  const handleForceSync = async () => {
    setIsSyncing(true);
    setIsRotating(true);
    
    try {
      // TODO: API integration
      await new Promise((resolve) => setTimeout(resolve, 2000));
      toast.success('Синхронизация завершена', {
        description: 'Получено 12 новых отзывов',
      });
    } catch (error) {
      toast.error('Ошибка синхронизации', {
        description: error instanceof Error ? error.message : 'Попробуйте снова',
      });
    } finally {
      setIsSyncing(false);
      setTimeout(() => setIsRotating(false), 500);
    }
  };

  const handleTestPing = async () => {
    try {
      // TODO: API integration
      await new Promise((resolve) => setTimeout(resolve, 1000));
      toast.success('Тестовое сообщение отправлено', {
        description: 'Проверьте канал уведомлений',
      });
    } catch (error) {
      toast.error('Ошибка отправки', {
        description: error instanceof Error ? error.message : 'Проверьте настройки',
      });
    }
  };

  const toggleChannel = (channelId: string) => {
    setChannels((prev) =>
      prev.map((ch) => (ch.id === channelId ? { ...ch, enabled: !ch.enabled } : ch))
    );
  };

  const getStatusBadge = (status: PlatformIntegration['status']) => {
    switch (status) {
      case 'connected':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-md text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
            Подключено
          </span>
        );
      case 'requires_token':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-md text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200">
            Требуется токен
          </span>
        );
      case 'error':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-md text-xs font-medium bg-rose-50 text-rose-700 border border-rose-200">
            Ошибка
          </span>
        );
    }
  };

  return (
    <DashboardLayout
      title="Интеграции"
      userEmail={user?.email}
      quota={null}
      online
      onLogout={logout}
    >
      <div className="min-h-full bg-slate-50 p-6 space-y-6">
        {/* Header */}
        <header className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold text-slate-900">
              Источники данных и вебхуки
            </h1>
            <p className="text-sm text-slate-600 mt-1">
              Управление потоками отзывов и каналами эскалации инцидентов
            </p>
          </div>
          <button
            onClick={handleForceSync}
            disabled={isSyncing}
            className="
              inline-flex items-center gap-2
              px-4 py-2.5
              bg-white
              border border-slate-200
              rounded-lg
              text-sm font-medium text-slate-700
              hover:bg-slate-50 hover:border-slate-300
              active:bg-slate-100
              disabled:opacity-50 disabled:cursor-not-allowed
              transition-colors
              shadow-sm
            "
          >
            <svg
              className={`w-4 h-4 ${isRotating ? 'animate-spin' : ''}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
              />
            </svg>
            {isSyncing ? 'Синхронизация...' : 'Принудительная синхронизация'}
          </button>
        </header>

        {/* Section 1: Review Platforms */}
        <section className="space-y-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">
              Площадки отзывов (Ingest & Write-back)
            </h2>
            <p className="text-sm text-slate-600 mt-0.5">
              Двусторонняя интеграция с платформами для чтения отзывов и публикации ответов
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {platforms.map((platform) => (
              <div
                key={platform.id}
                className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm hover:shadow-md transition-shadow"
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-3">
                    {platform.icon}
                    <div>
                      <h3 className="text-sm font-semibold text-slate-900">
                        {platform.name}
                      </h3>
                    </div>
                  </div>
                  {getStatusBadge(platform.status)}
                </div>

                <p className="text-xs text-slate-600 mb-3 leading-relaxed">
                  {platform.description}
                </p>

                {platform.status === 'connected' && (
                  <div className="space-y-2 mb-4">
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-slate-500">Филиалов:</span>
                      <span className="font-medium text-slate-900">{platform.branches}</span>
                    </div>
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-slate-500">Последняя синхронизация:</span>
                      <span className="font-medium text-slate-900">{platform.lastSync}</span>
                    </div>
                  </div>
                )}

                <button
                  onClick={() =>
                    setConfigModal({
                      type: 'platform',
                      id: platform.id,
                      title: platform.name,
                    })
                  }
                  className={`
                    w-full
                    px-3 py-2
                    text-sm font-medium
                    rounded-lg
                    transition-colors
                    ${
                      platform.status === 'requires_token'
                        ? 'bg-slate-900 text-white hover:bg-slate-800'
                        : 'bg-slate-50 text-slate-700 border border-slate-200 hover:bg-slate-100'
                    }
                  `}
                >
                  {platform.status === 'requires_token' ? 'Подключить API' : 'Настроить'}
                </button>
              </div>
            ))}
          </div>
        </section>

        {/* Section 2: Escalation Channels */}
        <section className="space-y-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">
              Корпоративные шины и Алертинг (Escalation & CRM)
            </h2>
            <p className="text-sm text-slate-600 mt-0.5">
              Интеграция с внутренними системами и каналами уведомлений
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {channels.map((channel) => (
              <div
                key={channel.id}
                className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm hover:shadow-md transition-shadow"
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-3">
                    {channel.icon}
                    <div>
                      <h3 className="text-sm font-semibold text-slate-900">
                        {channel.name}
                      </h3>
                    </div>
                  </div>
                  <button
                    onClick={() => toggleChannel(channel.id)}
                    className={`
                      relative
                      inline-flex
                      h-5
                      w-9
                      items-center
                      rounded-full
                      transition-colors
                      focus:outline-none
                      focus:ring-2
                      focus:ring-slate-500
                      focus:ring-offset-2
                      ${channel.enabled ? 'bg-slate-900' : 'bg-slate-300'}
                    `}
                  >
                    <span
                      className={`
                        inline-block
                        h-3
                        w-3
                        transform
                        rounded-full
                        bg-white
                        transition-transform
                        ${channel.enabled ? 'translate-x-5' : 'translate-x-1'}
                      `}
                    />
                  </button>
                </div>

                <p className="text-xs text-slate-600 mb-4 leading-relaxed">
                  {channel.description}
                </p>

                {channel.enabled && (
                  <div className="space-y-2">
                    {channel.id === 'telegram' && channel.config?.chatId && (
                      <div className="text-xs text-slate-600 mb-2">
                        <span className="font-medium">Chat ID:</span> {channel.config.chatId}
                      </div>
                    )}
                    
                    <div className="flex gap-2">
                      <button
                        onClick={() =>
                          setConfigModal({
                            type: 'channel',
                            id: channel.id,
                            title: channel.name,
                          })
                        }
                        className="
                          flex-1
                          px-3 py-2
                          text-sm font-medium
                          bg-slate-50 text-slate-700
                          border border-slate-200
                          rounded-lg
                          hover:bg-slate-100
                          transition-colors
                        "
                      >
                        Настроить
                      </button>
                      
                      {channel.id === 'telegram' && (
                        <button
                          onClick={() => handleTestPing()}
                          className="
                            px-3 py-2
                            text-sm font-medium
                            bg-white text-slate-700
                            border border-slate-200
                            rounded-lg
                            hover:bg-slate-50
                            transition-colors
                          "
                        >
                          Тестовый пинг
                        </button>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>

        {/* Configuration Modal */}
        {configModal && (
          <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-slate-900">
                  Настройка: {configModal.title}
                </h3>
                <button
                  onClick={() => setConfigModal(null)}
                  className="text-slate-400 hover:text-slate-600 transition-colors"
                >
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>

              <div className="space-y-4">
                {configModal.type === 'platform' && configModal.id === 'google' && (
                  <>
                    <div>
                      <label className="block text-sm font-medium text-slate-700 mb-2">
                        OAuth 2.0 Token
                      </label>
                      <input
                        type="text"
                        placeholder="ya29.a0AfH6SMBx..."
                        className="
                          w-full
                          px-3 py-2
                          text-sm
                          text-slate-800
                          bg-white
                          border border-slate-200
                          rounded-md
                          focus:ring-2
                          focus:ring-slate-500
                          focus:border-slate-500
                          focus:outline-none
                        "
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-slate-700 mb-2">
                        Location ID
                      </label>
                      <input
                        type="text"
                        placeholder="locations/123456789"
                        className="
                          w-full
                          px-3 py-2
                          text-sm
                          text-slate-800
                          bg-white
                          border border-slate-200
                          rounded-md
                          focus:ring-2
                          focus:ring-slate-500
                          focus:border-slate-500
                          focus:outline-none
                        "
                      />
                    </div>
                  </>
                )}

                {configModal.type === 'channel' && (
                  <>
                    {configModal.id === 'telegram' && (
                      <div>
                        <label className="block text-sm font-medium text-slate-700 mb-2">
                          Chat ID
                        </label>
                        <input
                          type="text"
                          placeholder="-1001234567890"
                          className="
                            w-full
                            px-3 py-2
                            text-sm
                            text-slate-800
                            bg-white
                            border border-slate-200
                            rounded-md
                            focus:ring-2
                            focus:ring-slate-500
                            focus:border-slate-500
                            focus:outline-none
                          "
                        />
                      </div>
                    )}
                    
                    {(configModal.id === 'amocrm' || configModal.id === 'webhook') && (
                      <div>
                        <label className="block text-sm font-medium text-slate-700 mb-2">
                          Webhook URL
                        </label>
                        <input
                          type="url"
                          placeholder="https://your-domain.com/webhook"
                          className="
                            w-full
                            px-3 py-2
                            text-sm
                            text-slate-800
                            bg-white
                            border border-slate-200
                            rounded-md
                            focus:ring-2
                            focus:ring-slate-500
                            focus:border-slate-500
                            focus:outline-none
                          "
                        />
                      </div>
                    )}
                  </>
                )}

                <div className="flex gap-2 pt-2">
                  <button
                    onClick={() => setConfigModal(null)}
                    className="
                      flex-1
                      px-4 py-2
                      text-sm font-medium
                      text-slate-600
                      bg-white
                      border border-slate-300
                      rounded-lg
                      hover:bg-slate-50
                      transition-colors
                    "
                  >
                    Отмена
                  </button>
                  <button
                    onClick={() => {
                      toast.success('Настройки сохранены');
                      setConfigModal(null);
                    }}
                    className="
                      flex-1
                      px-4 py-2
                      text-sm font-medium
                      text-white
                      bg-slate-900
                      rounded-lg
                      hover:bg-slate-800
                      transition-colors
                    "
                  >
                    Сохранить
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
