import { useEffect, useState } from 'react';
import { 
  CreditCard, 
  Zap, 
  Check, 
  TrendingUp, 
  Key, 
  Trash2,
  AlertCircle,
  Webhook as WebhookIcon
} from 'lucide-react';
import { toast } from 'sonner';

import { DashboardLayout } from '@/features/dashboard/DashboardLayout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Skeleton } from '@/components/ui/skeleton';
import { useAppStore } from '@/store/useAppStore';
import { WebhookManagement } from '@/features/webhooks/WebhookManagement';
import type { QuotaStatus, SubscriptionTier, APIKey, Webhook } from '@/api/services';
import * as demoApi from '@/api/demoService';
import * as api from '@/api/services';

export function SettingsPage() {
  const { user, logout } = useAppStore();
  const [quotaStatus, setQuotaStatus] = useState<QuotaStatus | null>(null);
  const [tiers, setTiers] = useState<SubscriptionTier[]>([]);
  const [apiKeys, setApiKeys] = useState<APIKey[]>([]);
  const [webhooks, setWebhooks] = useState<Webhook[]>([]);
  const [activeTab, setActiveTab] = useState<'usage' | 'subscription' | 'api-keys' | 'webhooks'>('usage');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      try {
        const [quota, subscriptionTiers, keys, hooks] = await Promise.all([
          demoApi.getQuotaStatus(),
          demoApi.getSubscriptionTiers(),
          demoApi.getAPIKeys(),
          api.getWebhooks(),
        ]);
        setQuotaStatus(quota);
        setTiers(subscriptionTiers);
        setApiKeys(keys);
        setWebhooks(hooks);
      } catch (error) {
        toast.error('Не удалось загрузить данные', {
          description: error instanceof Error ? error.message : 'Попробуйте обновить страницу',
        });
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, []);

  const handleRevokeKey = async (keyId: string) => {
    try {
      await demoApi.revokeAPIKey(keyId);
      setApiKeys((prev) => prev.filter((k) => k.id !== keyId));
      toast.success('API ключ отозван');
    } catch (error) {
      toast.error('Не удалось отозвать ключ');
    }
  };

  const handleWebhookCreated = (webhook: Webhook) => {
    setWebhooks((prev) => [...prev, webhook]);
  };

  const handleWebhookDeleted = (webhookId: string) => {
    setWebhooks((prev) => prev.filter((w) => w.id !== webhookId));
  };

  const handleUpgrade = (tierId: string) => {
    toast.info(`Переход на тариф ${tierId}`, {
      description: 'Эта функция будет доступна после интеграции платежей',
    });
  };

  const formatNumber = (num: number): string => {
    return new Intl.NumberFormat('ru-RU').format(num);
  };

  const formatDate = (dateString: string | null): string => {
    if (!dateString) return 'Никогда';
    return new Date(dateString).toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  // Current tier detection (based on limits)
  const currentTier = tiers.find(
    (t) => 
      t.limits.max_llm_tokens === quotaStatus?.limits.max_llm_tokens &&
      t.limits.max_reviews === quotaStatus?.limits.max_reviews
  );

  return (
    <DashboardLayout
      title="Настройки"
      userEmail={user?.email}
      quota={null}
      online
      onLogout={logout}
    >
      <div className="space-y-6">
        {/* Tab Navigation */}
        <div className="flex gap-2 border-b-2 border-gray-700 pb-4">
          <Button
            variant={activeTab === 'usage' ? 'default' : 'ghost'}
            onClick={() => setActiveTab('usage')}
            className={activeTab === 'usage' ? 'bg-plum text-white hover:bg-plum-700' : 'text-chrome-400 hover:text-white'}
          >
            <Zap className="h-4 w-4 mr-2" />
            Использование
          </Button>
          <Button
            variant={activeTab === 'subscription' ? 'default' : 'ghost'}
            onClick={() => setActiveTab('subscription')}
            className={activeTab === 'subscription' ? 'bg-plum text-white hover:bg-plum-700' : 'text-chrome-400 hover:text-white'}
          >
            <CreditCard className="h-4 w-4 mr-2" />
            Тарифы
          </Button>
          <Button
            variant={activeTab === 'api-keys' ? 'default' : 'ghost'}
            onClick={() => setActiveTab('api-keys')}
            className={activeTab === 'api-keys' ? 'bg-plum text-white hover:bg-plum-700' : 'text-chrome-400 hover:text-white'}
          >
            <Key className="h-4 w-4 mr-2" />
            API Ключи
          </Button>
          <Button
            variant={activeTab === 'webhooks' ? 'default' : 'ghost'}
            onClick={() => setActiveTab('webhooks')}
            className={activeTab === 'webhooks' ? 'bg-plum text-white hover:bg-plum-700' : 'text-chrome-400 hover:text-white'}
          >
            <WebhookIcon className="h-4 w-4 mr-2" />
            Webhooks
          </Button>
        </div>

        {/* Usage & Limits Section */}
        {activeTab === 'usage' && (
          <section>
            <h2 className="mb-4 flex items-center gap-2 text-2xl font-semibold text-white">
              <Zap className="h-6 w-6 text-plum" aria-hidden="true" />
              Использование и лимиты
            </h2>

          {loading && !quotaStatus ? (
            <Card>
              <CardHeader>
                <Skeleton className="h-6 w-1/3" />
                <Skeleton className="h-4 w-1/2" />
              </CardHeader>
              <CardContent className="space-y-6">
                <Skeleton className="h-20 w-full" />
                <Skeleton className="h-20 w-full" />
              </CardContent>
            </Card>
          ) : quotaStatus ? (
            <Card>
              <CardHeader>
                <CardTitle>Квоты текущего периода</CardTitle>
                <CardDescription>
                  Обновлено: {formatDate(quotaStatus.updated_at)}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* SI analysis quota */}
                <div className="space-y-3">
                  <div className="flex items-baseline justify-between">
                    <div>
                      <h4 className="text-sm font-semibold text-white">Токены SI-анализа</h4>
                      <p className="text-xs text-chrome-400">
                        Использовано для обработки отзывов
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="font-mono text-sm font-medium text-white">
                        {formatNumber(quotaStatus.total_tokens_committed ?? 0)} / {formatNumber(quotaStatus.limits.max_llm_tokens)}
                      </p>
                      <p className="font-mono text-xs text-chrome-400">
                        {quotaStatus.tokens_usage_percent?.toFixed(1)}% использовано
                      </p>
                    </div>
                  </div>
                  <Progress 
                    value={quotaStatus.tokens_usage_percent ?? 0} 
                    max={100}
                  />
                  {(quotaStatus.tokens_usage_percent ?? 0) >= 80 && (
                    <div className="flex items-start gap-2 rounded-sm border-2 border-yellow-500 bg-yellow-500/10 p-3">
                      <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-yellow-500" />
                      <p className="text-xs text-yellow-500">
                        Вы израсходовали более 80% лимита. Рекомендуем обновить тариф.
                      </p>
                    </div>
                  )}
                </div>

                {/* Reviews Progress */}
                <div className="space-y-3">
                  <div className="flex items-baseline justify-between">
                    <div>
                      <h4 className="text-sm font-semibold text-white">Обработанные отзывы</h4>
                      <p className="text-xs text-chrome-400">
                        Количество собранных отзывов
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="font-mono text-sm font-medium text-white">
                        {formatNumber(quotaStatus.usage.used_reviews)} / {formatNumber(quotaStatus.limits.max_reviews)}
                      </p>
                      <p className="font-mono text-xs text-chrome-400">
                        {quotaStatus.reviews_usage_percent?.toFixed(1)}% использовано
                      </p>
                    </div>
                  </div>
                  <Progress 
                    value={quotaStatus.reviews_usage_percent ?? 0} 
                    max={100}
                  />
                  {(quotaStatus.reviews_usage_percent ?? 0) >= 80 && (
                    <div className="flex items-start gap-2 rounded-sm border-2 border-yellow-500 bg-yellow-500/10 p-3">
                      <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-yellow-500" />
                      <p className="text-xs text-yellow-500">
                        Вы израсходовали более 80% лимита отзывов. Рекомендуем обновить тариф.
                      </p>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          ) : null}
          </section>
        )}

        {/* Subscription Tiers Section */}
        {activeTab === 'subscription' && (
          <section>
            <h2 className="mb-4 flex items-center gap-2 text-2xl font-semibold text-white">
              <CreditCard className="h-6 w-6 text-plum" aria-hidden="true" />
              Тарифные планы
            </h2>

          {loading && tiers.length === 0 ? (
            <div className="grid gap-6 md:grid-cols-3">
              {[1, 2, 3].map((i) => (
                <Card key={i}>
                  <CardHeader>
                    <Skeleton className="h-6 w-1/2" />
                    <Skeleton className="h-8 w-1/3" />
                  </CardHeader>
                  <CardContent>
                    <Skeleton className="h-40 w-full" />
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : (
            <div className="grid gap-6 md:grid-cols-3">
              {tiers.map((tier) => {
                const isActive = currentTier?.id === tier.id;
                
                return (
                  <Card
                    key={tier.id}
                    className={isActive ? 'border-plum' : ''}
                  >
                    <CardHeader>
                      <div className="flex items-start justify-between">
                        <CardTitle className="text-lg">{tier.name}</CardTitle>
                        {isActive && (
                          <Badge variant="secondary" className="bg-plum text-white">
                            Текущий план
                          </Badge>
                        )}
                        {tier.recommended && !isActive && (
                          <Badge variant="outline">
                            Рекомендуем
                          </Badge>
                        )}
                      </div>
                      <div className="mt-2">
                        <span className="text-3xl font-bold text-white">
                          ${tier.price}
                        </span>
                        <span className="text-chrome-400">/{tier.interval === 'month' ? 'месяц' : 'год'}</span>
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <ul className="space-y-2">
                        {tier.features.map((feature, idx) => (
                          <li key={idx} className="flex items-start gap-2 text-sm">
                            <Check className="mt-0.5 h-4 w-4 shrink-0 text-lime" aria-hidden="true" />
                            <span className="text-chrome-300">{feature}</span>
                          </li>
                        ))}
                      </ul>

                      {isActive ? (
                        <Button variant="outline" disabled className="w-full">
                          <Check className="mr-2 h-4 w-4" />
                          Активный план
                        </Button>
                      ) : (
                        <Button 
                          variant={tier.recommended ? 'accent' : 'default'} 
                          className="w-full"
                          onClick={() => handleUpgrade(tier.id)}
                        >
                          <TrendingUp className="mr-2 h-4 w-4" />
                          Перейти на {tier.name}
                        </Button>
                      )}
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          )}
        </section>
        )}

        {/* API Keys Section */}
        {activeTab === 'api-keys' && (
          <section>
            <h2 className="mb-4 flex items-center gap-2 text-2xl font-semibold text-white">
              <Key className="h-6 w-6 text-plum" aria-hidden="true" />
              API Ключи
            </h2>

          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Управление API ключами</CardTitle>
                  <CardDescription>
                    Используйте API ключи для интеграции с внешними системами
                  </CardDescription>
                </div>
                <Button variant="default" size="sm">
                  Создать ключ
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {loading && apiKeys.length === 0 ? (
                <div className="space-y-3">
                  {[1, 2, 3].map((i) => (
                    <Skeleton key={i} className="h-16 w-full" />
                  ))}
                </div>
              ) : apiKeys.length === 0 ? (
                <div className="rounded-sm border-2 border-chrome-600 bg-ink-950 p-8 text-center">
                  <Key className="mx-auto mb-3 h-10 w-10 text-chrome-600" strokeWidth={1.25} />
                  <p className="text-sm font-medium text-white">API ключи не созданы</p>
                  <p className="mt-1 text-xs text-chrome-400">
                    Создайте первый ключ для доступа к API
                  </p>
                </div>
              ) : (
                <div className="space-y-3">
                  {apiKeys.map((key) => (
                    <div
                      key={key.id}
                      className="flex items-center justify-between rounded-sm border-2 border-chrome-600 bg-ink-900 p-4"
                    >
                      <div className="flex-1 space-y-1">
                        <div className="flex items-center gap-2">
                          <p className="text-sm font-medium text-white">{key.name}</p>
                          <Badge variant="outline" className="font-mono text-xs">
                            {key.key_prefix}
                          </Badge>
                        </div>
                        <div className="flex items-center gap-4 text-xs text-chrome-400">
                          <span>Создан: {formatDate(key.created_at)}</span>
                          <span>•</span>
                          <span>
                            Последнее использование: {formatDate(key.last_used_at)}
                          </span>
                        </div>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleRevokeKey(key.id)}
                        className="text-red-500 hover:bg-red-500/10 hover:text-red-500"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </section>
        )}

        {/* Webhooks Section */}
        {activeTab === 'webhooks' && (
          <section>
            <h2 className="mb-4 flex items-center gap-2 text-2xl font-semibold text-white">
              <WebhookIcon className="h-6 w-6 text-plum" aria-hidden="true" />
              Developer / Webhooks
            </h2>
            <WebhookManagement
              webhooks={webhooks}
              loading={loading}
              onWebhookCreated={handleWebhookCreated}
              onWebhookDeleted={handleWebhookDeleted}
            />
          </section>
        )}
      </div>
    </DashboardLayout>
  );
}
