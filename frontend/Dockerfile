# ========================================
# Stage 1: Build
# ========================================
FROM node:20-alpine AS builder

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем package files для оптимизации кэширования Docker layers
COPY package.json package-lock.json ./

# Устанавливаем зависимости (npm ci быстрее и детерминированнее)
RUN npm ci --prefer-offline --no-audit

# Копируем исходный код
COPY . .

# Build production bundle
# Vite автоматически минифицирует и tree-shakes код
RUN npm run build

# ========================================
# Stage 2: Production Server
# ========================================
FROM nginx:1.25-alpine

# Metadata
LABEL maintainer="Tenable SERM Team"
LABEL description="Tenable SERM Frontend - Production Image"

# Устанавливаем curl для healthcheck
RUN apk add --no-cache curl

# Удаляем дефолтную конфигурацию nginx
RUN rm /etc/nginx/conf.d/default.conf

# Копируем нашу конфигурацию
COPY nginx.conf /etc/nginx/conf.d/

# Копируем собранный фронтенд из builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Создаём non-root пользователя для безопасности
RUN chown -R nginx:nginx /usr/share/nginx/html && \
    chmod -R 755 /usr/share/nginx/html

# Открываем порт 80
EXPOSE 80

# Healthcheck для Docker Swarm/Kubernetes
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost/ || exit 1

# Запускаем nginx в foreground (PID 1)
CMD ["nginx", "-g", "daemon off;"]
