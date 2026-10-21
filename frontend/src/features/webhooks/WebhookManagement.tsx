/**
 * Webhook Management Components
 * Table, modal, and secret key display for webhook configuration
 */

import { useState } from 'react';
import { Copy, Trash2, Plus, Webhook as WebhookIcon, CheckCircle2, AlertCircle } from 'lucide-react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import type { Webhook, CreateWebhookRequest, CreateWebhookResponse } from '@/api/services';
import * as api from '@/api/services';

interface WebhookManagementProps {
  webhooks: Webhook[];
  loading: boolean;
  onWebhookCreated: (webhook: Webhook) => void;
  onWebhookDeleted: (webhookId: string) => void;
}

export function WebhookManagement({ webhooks, loading, onWebhookCreated, onWebhookDeleted }: WebhookManagementProps) {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [url, setUrl] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const [newWebhookSecret, setNewWebhookSecret] = useState<string | null>(null);
  const [hasCopiedSecret, setHasCopiedSecret] = useState(false);

  const handleCreateWebhook = async () => {
    if (!url.trim()) {
      toast.error('URL обязателен');
      return;
    }

    try {
      setIsCreating(true);
      const request: CreateWebhookRequest = {
        url: url.trim(),
        events: ['review.created', 'review.analyzed', 'threat.critical'],
      };
      const response: CreateWebhookResponse = await api.createWebhook(request);

      setNewWebhookSecret(response.secret_key);
      setHasCopiedSecret(false);
      toast.success('Вебхук создан', {
        description: 'Сохраните секретный ключ - мы больше его не покажем',
      });

      // Add to list
      onWebhookCreated({
        id: response.id,
        url: response.url,
        secret_key_prefix: response.secret_key_prefix,
        events: response.events,
        active: response.active,
        created_at: response.created_at,
        last_triggered_at: null,
      });

      setUrl('');
    } catch (error) {
      toast.error('Не удалось создать вебхук', {
        description: error instanceof Error ? error.message : 'Попробуйте снова',
      });
    } finally {
      setIsCreating(false);
    }
  };

  const handleDeleteWebhook = async (webhookId: string) => {
    try {
      await api.deleteWebhook(webhookId);
      onWebhookDeleted(webhookId);
      toast.success('Вебхук удален');
    } catch (error) {
      toast.error('Не удалось удалить вебхук');
    }
  };

  const handleCopySecret = async () => {
    if (newWebhookSecret) {
      try {
        await navigator.clipboard.writeText(newWebhookSecret);
        setHasCopiedSecret(true);
        toast.success('Секретный ключ скопирован');
      } catch (error) {
        toast.error('Не удалось скопировать ключ');
      }
    }
  };

  const handleCloseSecretModal = () => {
    setNewWebhookSecret(null);
    setHasCopiedSecret(false);
    setIsModalOpen(false);
  };

  const formatDate = (dateString: string): string => {
    return new Date(dateString).toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <>
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Управление вебхуками</CardTitle>
              <CardDescription>
                Настройте интеграцию с внешними системами через вебхуки
              </CardDescription>
            </div>
            <Button
              onClick={() => setIsModalOpen(true)}
              size="sm"
              className="bg-plum text-white hover:bg-plum-700"
            >
              <Plus className="h-4 w-4 mr-2" />
              Add Endpoint
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {loading && webhooks.length === 0 ? (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-16 w-full" />
              ))}
            </div>
          ) : webhooks.length === 0 ? (
            <div className="rounded-sm border-2 border-gray-700 bg-gray-900/50 p-8 text-center">
              <WebhookIcon className="mx-auto mb-3 h-10 w-10 text-gray-600" strokeWidth={1.25} />
              <p className="text-sm font-medium text-white">Вебхуки не настроены</p>
              <p className="mt-1 text-xs text-gray-400">
                Создайте первый вебхук для интеграции с внешними системами
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {webhooks.map((webhook) => (
                <div
                  key={webhook.id}
                  className="flex items-center justify-between rounded-sm border-2 border-gray-700 bg-gray-900/50 p-4"
                >
                  <div className="flex-1 space-y-2">
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-medium text-white">{webhook.url}</p>
                      <Badge variant={webhook.active ? 'success' : 'secondary'}>
                        {webhook.active ? 'Активен' : 'Отключен'}
                      </Badge>
                    </div>
                    <div className="flex items-center gap-4 text-xs text-gray-400">
                      <span>Создан: {formatDate(webhook.created_at)}</span>
                      <span>•</span>
                      <span>
                        Последний запуск: {webhook.last_triggered_at ? formatDate(webhook.last_triggered_at) : 'Никогда'}
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {webhook.events.map((event) => (
                        <Badge key={event} variant="outline" className="text-xs font-mono">
                          {event}
                        </Badge>
                      ))}
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleDeleteWebhook(webhook.id)}
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

      {/* Create Webhook Modal */}
      <Dialog open={isModalOpen && !newWebhookSecret} onOpenChange={setIsModalOpen}>
        <DialogContent className="bg-gray-900 border-gray-700">
          <DialogHeader>
            <DialogTitle className="text-white">Добавить вебхук</DialogTitle>
            <DialogDescription className="text-gray-400">
              Введите URL endpoint для получения событий
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="webhook-url" className="text-white">
                URL Endpoint
              </Label>
              <Input
                id="webhook-url"
                type="url"
                placeholder="https://your-domain.com/webhook"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                className="bg-gray-800 border-gray-700 text-white"
                disabled={isCreating}
              />
            </div>
            <div className="rounded-sm border-2 border-gray-700 bg-gray-800 p-3">
              <p className="text-xs text-gray-400 mb-2">События:</p>
              <div className="flex flex-wrap gap-1">
                <Badge variant="outline" className="text-xs">review.created</Badge>
                <Badge variant="outline" className="text-xs">review.analyzed</Badge>
                <Badge variant="outline" className="text-xs">threat.critical</Badge>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setIsModalOpen(false)}
              disabled={isCreating}
              className="border-gray-700 text-white hover:bg-gray-800"
            >
              Отмена
            </Button>
            <Button
              onClick={handleCreateWebhook}
              disabled={isCreating || !url.trim()}
              className="bg-plum text-white hover:bg-plum-700"
            >
              {isCreating ? 'Создание...' : 'Создать'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Secret Key Display Modal (ONE TIME ONLY) */}
      <Dialog open={!!newWebhookSecret} onOpenChange={handleCloseSecretModal}>
        <DialogContent className="bg-gray-900 border-gray-700">
          <DialogHeader>
            <DialogTitle className="text-white flex items-center gap-2">
              <CheckCircle2 className="h-5 w-5 text-green-500" />
              Вебхук создан
            </DialogTitle>
            <DialogDescription className="text-gray-400">
              Сохраните этот секретный ключ - мы больше его не покажем
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="rounded-sm border-2 border-red-500/50 bg-red-500/10 p-4">
              <div className="flex items-start gap-2 mb-3">
                <AlertCircle className="h-5 w-5 text-red-500 shrink-0 mt-0.5" />
                <p className="text-sm text-red-400 font-medium">
                  Важно: Сохраните этот ключ сейчас
                </p>
              </div>
              <p className="text-xs text-red-300">
                Этот секретный ключ будет показан только один раз. Вы не сможете увидеть его снова.
              </p>
            </div>
            <div className="space-y-2">
              <Label className="text-white">Секретный ключ</Label>
              <div className="flex gap-2">
                <Input
                  value={newWebhookSecret || ''}
                  readOnly
                  className="bg-gray-800 border-gray-700 text-white font-mono text-sm"
                />
                <Button
                  onClick={handleCopySecret}
                  variant="outline"
                  className="border-gray-700 text-white hover:bg-gray-800 shrink-0"
                >
                  {hasCopiedSecret ? (
                    <CheckCircle2 className="h-4 w-4 text-green-500" />
                  ) : (
                    <Copy className="h-4 w-4" />
                  )}
                </Button>
              </div>
            </div>
            <div className="rounded-sm border-2 border-gray-700 bg-gray-800 p-3">
              <p className="text-xs text-gray-400">
                Используйте этот ключ для верификации вебхуков в вашем приложении.
                Ключ передается в заголовке <code className="bg-gray-700 px-1 rounded">X-Webhook-Secret</code>.
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button
              onClick={handleCloseSecretModal}
              disabled={!hasCopiedSecret}
              variant="accent"
            >
              Понял, сохранил
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
