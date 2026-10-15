#!/bin/bash
# Генерация самоподписанных SSL сертификатов для тестирования
# В продакшене используйте сертификаты от Let's Encrypt или другого CA

set -e

SSL_DIR="./nginx/ssl"
CERT_FILE="$SSL_DIR/cert.pem"
KEY_FILE="$SSL_DIR/key.pem"

# Создаем директорию для SSL
mkdir -p "$SSL_DIR"

echo "🔐 Генерация самоподписанного SSL сертификата..."

# Генерируем сертификат (действителен 365 дней)
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout "$KEY_FILE" \
  -out "$CERT_FILE" \
  -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"

echo "✅ SSL сертификаты сгенерированы:"
echo "   - $CERT_FILE"
echo "   - $KEY_FILE"
echo ""
echo "⚠️  ВНИМАНИЕ: Это самоподписанные сертификаты для тестирования!"
echo "   Для продакшена используйте Let's Encrypt или другой CA."
echo ""
echo "📝 После генерации:"
echo "   1. Раскомментируйте HTTPS server block в nginx/nginx.conf"
echo "   2. Перезапустите docker-compose: docker-compose -f docker-compose.prod.yml restart nginx"
