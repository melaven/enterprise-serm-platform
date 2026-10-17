# Multi-stage Dockerfile for React frontend with Nginx

# ---- Stage 1: Build with Node.js and Vite ----
FROM node:20-alpine AS builder

WORKDIR /build

# Copy package files
COPY frontend/package*.json ./

# Install dependencies (including dev for build)
# Skip prepare scripts (husky) since we're building in Docker
RUN npm install --ignore-scripts

# Copy source code
COPY frontend/ ./

# Build the application
RUN npm run build

# ---- Stage 2: Serve with Nginx ----
FROM nginx:alpine

# Copy custom nginx config
COPY frontend/nginx.conf /etc/nginx/nginx.conf

# Copy built assets from builder stage
COPY --from=builder /build/dist /usr/share/nginx/html

# Expose port 80
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost/ || exit 1

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
