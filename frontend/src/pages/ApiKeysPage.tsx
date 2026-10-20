/**
 * API Keys Page
 * B2B interface for managing API keys
 *
 * Features:
 * - Generate new API keys
 * - Show full key ONLY ONCE in modal
 * - List existing keys with metadata
 * - Revoke keys
 * - Pro/Enterprise only feature
 */

import { useState, useEffect, useCallback } from 'react';
import { Key, Plus, Copy, Trash2, AlertTriangle, Check, RefreshCw } from 'lucide-react';
import { toast } from 'sonner';

import { DashboardLayout } from '@/features/dashboard/DashboardLayout';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useAppStore } from '@/store/useAppStore';
import {
  getAPIKeys,
  createAPIKey,
  revokeAPIKey,
  getQuotaStatus,
  type APIKey,
  type CreateAPIKeyResponse
} from '@/api/services';
import { ApiError } from '@/api/client';
import { cn } from '@/lib/utils';

// ============================================================================
// Types
// ============================================================================

interface NewKeyModalProps {
  open: boolean;
  onClose: () => void;
  generatedKey: CreateAPIKeyResponse | null;
  onCopyKey: () => void;
  keyCopied: boolean;
}

// ============================================================================
// Components
// ============================================================================

/**
 * Modal for showing newly generated key (ONLY ONCE)
 */
function NewKeyModal({ open, onClose, generatedKey, onCopyKey, keyCopied }: NewKeyModalProps) {
  if (!generatedKey) return null;

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl border-2 border-plum-700 bg-ink-900">
        {/* Header */}
        <div className="border-b-2 border-chrome-600 pb-4">
          <div className="flex items-center gap-3 mb-2">
            <div className="flex items-center justify-center h-10 w-10 rounded-sm bg-lime text-ink-950">
              <Key className="h-5 w-5" />
            </div>
            <DialogTitle className="text-xl font-bold text-white">
              API ключ создан
            </DialogTitle>
          </div>
          <DialogDescription className="text-chrome-400">
            Сохраните этот ключ в безопасном месте. Мы больше его не покажем.
          </DialogDescription>
        </div>

        {/* Warning Banner */}
        <div className="flex items-start gap-3 rounded-sm border-2 border-yellow-500 bg-yellow-500/10 p-4">
          <AlertTriangle className="h-5 w-5 text-yellow-500 shrink-0 mt-0.5" />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-yellow-500 mb-1">
              Важно: Сохраните ключ прямо сейчас
            </p>
            <p className="text-xs text-yellow-500/80">
              После закрытия этого окна вы не сможете снова увидеть полный ключ.
              Если вы потеряете его, придётся создать новый.
            </p>
          </div>
        </div>

        {/* Key Details */}
        <div className="space-y-4">
          <div>
            <Label className="text-xs text-chrome-400 uppercase tracking-wider">
              Название ключа
            </Label>
            <p className="mt-1 text-sm font-medium text-white">
              {generatedKey.name}
            </p>
          </div>

          <div>
            <Label className="text-xs text-chrome-400 uppercase tracking-wider mb-2 block">
              API ключ
            </Label>
            <div className="flex items-center gap-2">
              <div className="flex-1 min-w-0 rounded-sm border-2 border-chrome-600 bg-ink-950 p-3">
                <code className="text-sm font-mono text-lime break-all">
                  {generatedKey.key}
                </code>
              </div>
              <Button
                onClick={onCopyKey}
                variant="outline"
                size="sm"
                className={cn(
                  'shrink-0',
                  keyCopied && 'border-lime text-lime'
                )}
              >
                {keyCopied ? (
                  <>
                    <Check className="h-4 w-4 mr-2" />
                    Скопировано
                  </>
                ) : (
                  <>
                    <Copy className="h-4 w-4 mr-2" />
                    Копировать
                  </>
                )}
              </Button>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-3 border-t-2 border-chrome-600 pt-4">
          <Button
            onClick={onClose}
            variant="default"
            className="bg-lime text-ink-950 hover:bg-lime/90"
          >
            Готово, я сохранил ключ
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

/**
 * Modal for creating new API key (name input)
 */
function CreateKeyModal({
  open,
  onClose,
  onSubmit
}: {
  open: boolean;
  onClose: () => void;
  onSubmit: (name: string) => Promise<void>;
}) {
  const [name, setName] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      toast.error('Введите название ключа');
      return;
    }

    setLoading(true);
    try {
      await onSubmit(name.trim());
      setName('');
      onClose();
    } catch (error) {
      // Error handling in parent
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    if (!loading) {
      setName('');
      onClose();
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-md border-2 border-plum-700 bg-ink-900">
        <div className="border-b-2 border-chrome-600 pb-4">
          <DialogTitle className="text-xl font-bold text-white">
            Создать API ключ
          </DialogTitle>
          <DialogDescription className="text-chrome-400">
            Введите название для нового ключа
          </DialogDescription>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <Label htmlFor="key-name" className="text-sm text-white">
              Название ключа
            </Label>
            <Input
              id="key-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Production API Key"
              maxLength={100}
              disabled={loading}
              className="mt-2"
              autoFocus
            />
            <p className="mt-2 text-xs text-chrome-400">
              Используйте понятное название, например "Production Server" или "CI/CD Pipeline"
            </p>
          </div>

          <div className="flex justify-end gap-3 border-t-2 border-chrome-600 pt-4">
            <Button
              type="button"
              onClick={handleClose}
              variant="outline"
              disabled={loading}
            >
              Отмена
            </Button>
            <Button
              type="submit"
              disabled={loading}
              className="bg-lime text-ink-950 hover:bg-lime/90"
            >
              {loading ? (
                <>
                  <RefreshCw className="h-4 w-4 animate-spin mr-2" />
                  Создание...
                </>
              ) : (
                <>
                  <Plus className="h-4 w-4 mr-2" />
                  Создать ключ
                </>
              )}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

/**
 * Confirmation modal for revoking key
 */
function RevokeKeyModal({
  open,
  onClose,
  onConfirm,
  keyName,
  loading,
}: {
  open: boolean;
  onClose: () => void;
  onConfirm: () => Promise<void>;
  keyName: string;
  loading: boolean;
}) {
  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-md border-2 border-red-700 bg-ink-900">
        <div className="border-b-2 border-chrome-600 pb-4">
          <div className="flex items-center gap-3 mb-2">
            <div className="flex items-center justify-center h-10 w-10 rounded-sm bg-red-500/20 text-red-500">
              <AlertTriangle className="h-5 w-5" />
            </div>
            <DialogTitle className="text-xl font-bold text-white">
              Отозвать API ключ?
            </DialogTitle>
          </div>
          <DialogDescription className="text-chrome-400">
            Это действие необратимо
          </DialogDescription>
        </div>

        <div className="space-y-4">
          <p className="text-sm text-chrome-300">
            Вы уверены, что хотите отозвать ключ <span className="font-semibold text-white">"{keyName}"</span>?
          </p>

          <div className="flex items-start gap-3 rounded-sm border-2 border-red-500 bg-red-500/10 p-3">
            <AlertTriangle className="h-4 w-4 text-red-500 shrink-0 mt-0.5" />
            <p className="text-xs text-red-400">
              Все запросы с этим ключом немедленно перестанут работать.
              Убедитесь, что ключ больше не используется.
            </p>
          </div>
        </div>

        <div className="flex justify-end gap-3 border-t-2 border-chrome-600 pt-4">
          <Button
            onClick={onClose}
            variant="outline"
            disabled={loading}
          >
            Отмена
          </Button>
          <Button
            onClick={onConfirm}
            disabled={loading}
            className="bg-red-500 text-white hover:bg-red-600"
          >
            {loading ? (
              <>
                <RefreshCw className="h-4 w-4 animate-spin mr-2" />
                Отзыв...
              </>
            ) : (
              <>
                <Trash2 className="h-4 w-4 mr-2" />
                Отозвать ключ
              </>
            )}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ============================================================================
// Main Component
// ============================================================================

export function ApiKeysPage() {
  const { user, logout } = useAppStore();

  const [keys, setKeys] = useState<APIKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [newKeyModalOpen, setNewKeyModalOpen] = useState(false);
  const [revokeModalOpen, setRevokeModalOpen] = useState(false);

  const [generatedKey, setGeneratedKey] = useState<CreateAPIKeyResponse | null>(null);
  const [keyCopied, setKeyCopied] = useState(false);
  const [keyToRevoke, setKeyToRevoke] = useState<APIKey | null>(null);
  const [revokeLoading, setRevokeLoading] = useState(false);

  const [isPro, setIsPro] = useState(false);

  // Check if user has Pro/Enterprise plan
  useEffect(() => {
    async function checkPlan() {
      try {
        const quota = await getQuotaStatus();
        const isProPlan = quota.limits.max_reviews >= 10_000;
        setIsPro(isProPlan);
      } catch (error) {
        console.error('Failed to check plan:', error);
      }
    }

    void checkPlan();
  }, []);

  // Load API keys
  const loadKeys = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const data = await getAPIKeys();
      setKeys(data);
    } catch (err) {
      const errorMsg = err instanceof ApiError
        ? err.status === 0
          ? 'Нет подключения к серверу'
          : err.status >= 500
            ? 'Ошибка сервера'
            : err.message
        : 'Неизвестная ошибка';

      setError(errorMsg);
      toast.error('Не удалось загрузить API ключи', {
        description: errorMsg,
      });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadKeys();
  }, [loadKeys]);

  // Create new API key
  const handleCreateKey = async (name: string) => {
    try {
      const newKey = await createAPIKey({ name });
      setGeneratedKey(newKey);
      setNewKeyModalOpen(true);
      setKeyCopied(false);

      // Reload keys list
      await loadKeys();

      toast.success('API ключ создан', {
        description: 'Сохраните его в безопасном месте',
      });
    } catch (err) {
      const errorMsg = err instanceof ApiError ? err.message : 'Неизвестная ошибка';
      toast.error('Не удалось создать ключ', {
        description: errorMsg,
      });
      throw err;
    }
  };

  // Copy key to clipboard
  const handleCopyKey = async () => {
    if (!generatedKey) return;

    try {
      await navigator.clipboard.writeText(generatedKey.key);
      setKeyCopied(true);
      toast.success('Ключ скопирован в буфер обмена');

      // Reset copied state after 3 seconds
      setTimeout(() => setKeyCopied(false), 3000);
    } catch (error) {
      toast.error('Не удалось скопировать ключ');
    }
  };

  // Revoke API key
  const handleRevokeKey = async () => {
    if (!keyToRevoke) return;

    setRevokeLoading(true);

    try {
      await revokeAPIKey(keyToRevoke.id);

      // Remove from local state
      setKeys((prev) => prev.filter((k) => k.id !== keyToRevoke.id));

      toast.success('API ключ отозван', {
        description: `Ключ "${keyToRevoke.name}" больше не действителен`,
      });

      setRevokeModalOpen(false);
      setKeyToRevoke(null);
    } catch (err) {
      const errorMsg = err instanceof ApiError ? err.message : 'Неизвестная ошибка';
      toast.error('Не удалось отозвать ключ', {
        description: errorMsg,
      });
    } finally {
      setRevokeLoading(false);
    }
  };

  // Format date
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

  return (
    <DashboardLayout
      title="API Ключи"
      userEmail={user?.email}
      quota={null}
      online
      onLogout={logout}
    >
      <div className="max-w-5xl">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h1 className="text-3xl font-bold text-white mb-2">
                API Ключи
              </h1>
              <p className="text-chrome-400">
                Управляйте ключами для доступа к API Tenable SERM
              </p>
            </div>

            {isPro && (
              <Button
                onClick={() => setCreateModalOpen(true)}
                className="bg-lime text-ink-950 hover:bg-lime/90"
              >
                <Plus className="h-4 w-4 mr-2" />
                Создать ключ
              </Button>
            )}
          </div>

          {/* Pro Feature Banner */}
          {!isPro && (
            <div className="flex items-start gap-3 rounded-sm border-2 border-plum-700 bg-plum-900/20 p-4">
              <Key className="h-5 w-5 text-plum-300 shrink-0 mt-0.5" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-plum-300 mb-1">
                  API ключи доступны на тарифе Pro
                </p>
                <p className="text-xs text-plum-400/80 mb-3">
                  Обновите тариф для доступа к API интеграциям и автоматизации
                </p>
                <Button
                  onClick={() => window.location.href = '/billing'}
                  size="sm"
                  className="bg-lime text-ink-950 hover:bg-lime/90"
                >
                  Перейти на Pro
                </Button>
              </div>
            </div>
          )}
        </div>

        {/* API Keys List */}
        {isPro && (
          <div className="border-2 border-chrome-600 rounded-sm bg-ink-900">
            {/* Table Header */}
            <div className="border-b-2 border-chrome-600 p-6">
              <h2 className="text-lg font-semibold text-white">
                Активные ключи
              </h2>
              <p className="text-sm text-chrome-400 mt-1">
                {keys.length} {keys.length === 1 ? 'ключ' : keys.length < 5 ? 'ключа' : 'ключей'}
              </p>
            </div>

            {/* Keys List */}
            <div className="divide-y-2 divide-chrome-600">
              {loading ? (
                <div className="p-8 text-center">
                  <RefreshCw className="h-8 w-8 text-chrome-600 animate-spin mx-auto mb-3" />
                  <p className="text-sm text-chrome-400">Загрузка ключей...</p>
                </div>
              ) : error ? (
                <div className="p-8 text-center">
                  <AlertTriangle className="h-8 w-8 text-red-500 mx-auto mb-3" />
                  <p className="text-sm font-medium text-white mb-1">
                    Ошибка загрузки
                  </p>
                  <p className="text-xs text-chrome-400 mb-4">{error}</p>
                  <Button onClick={loadKeys} variant="outline" size="sm">
                    <RefreshCw className="h-4 w-4 mr-2" />
                    Повторить
                  </Button>
                </div>
              ) : keys.length === 0 ? (
                <div className="p-12 text-center">
                  <div className="inline-flex items-center justify-center h-16 w-16 rounded-sm bg-chrome-800 mb-4">
                    <Key className="h-8 w-8 text-chrome-600" strokeWidth={1.5} />
                  </div>
                  <p className="text-sm font-medium text-white mb-1">
                    API ключи не созданы
                  </p>
                  <p className="text-xs text-chrome-400 mb-4">
                    Создайте первый ключ для доступа к API
                  </p>
                  <Button
                    onClick={() => setCreateModalOpen(true)}
                    variant="outline"
                  >
                    <Plus className="h-4 w-4 mr-2" />
                    Создать ключ
                  </Button>
                </div>
              ) : (
                keys.map((key) => (
                  <div
                    key={key.id}
                    className="p-6 hover:bg-ink-950 transition-colors"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-3 mb-2">
                          <h3 className="text-sm font-semibold text-white truncate">
                            {key.name}
                          </h3>
                          <code className="px-2 py-1 text-xs font-mono bg-ink-950 text-lime border border-chrome-700 rounded-sm">
                            {key.key_prefix}
                          </code>
                        </div>

                        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-chrome-400">
                          <span>
                            Создан: {formatDate(key.created_at)}
                          </span>
                          <span className="text-chrome-600">•</span>
                          <span>
                            Последнее использование: {formatDate(key.last_used_at)}
                          </span>
                        </div>
                      </div>

                      <Button
                        onClick={() => {
                          setKeyToRevoke(key);
                          setRevokeModalOpen(true);
                        }}
                        variant="ghost"
                        size="sm"
                        className="shrink-0 text-red-400 hover:bg-red-500/10 hover:text-red-400"
                      >
                        <Trash2 className="h-4 w-4 mr-2" />
                        Отозвать
                      </Button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        )}

        {/* API Documentation Link */}
        {isPro && (
          <div className="mt-6 rounded-sm border-2 border-chrome-600 bg-ink-900 p-6">
            <h3 className="text-sm font-semibold text-white mb-2">
              Документация API
            </h3>
            <p className="text-xs text-chrome-400 mb-4">
              Узнайте, как использовать API ключи для интеграции с вашими приложениями
            </p>
            <Button
              onClick={() => window.open('/docs/api', '_blank')}
              variant="outline"
              size="sm"
            >
              Открыть документацию
            </Button>
          </div>
        )}
      </div>

      {/* Modals */}
      <CreateKeyModal
        open={createModalOpen}
        onClose={() => setCreateModalOpen(false)}
        onSubmit={handleCreateKey}
      />

      <NewKeyModal
        open={newKeyModalOpen}
        onClose={() => setNewKeyModalOpen(false)}
        generatedKey={generatedKey}
        onCopyKey={handleCopyKey}
        keyCopied={keyCopied}
      />

      <RevokeKeyModal
        open={revokeModalOpen}
        onClose={() => setRevokeModalOpen(false)}
        onConfirm={handleRevokeKey}
        keyName={keyToRevoke?.name ?? ''}
        loading={revokeLoading}
      />
    </DashboardLayout>
  );
}
