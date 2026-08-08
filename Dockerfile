# ── Stage 1：构建前端 ──
FROM node:20-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ── Stage 2：后端 + nginx ──
FROM python:3.12-slim
WORKDIR /app

# 后端依赖
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn

# 后端代码（.dockerignore 已排除 .env/db/索引）
COPY backend/ ./backend/

# 前端产物（从 Stage 1 复制，无需本地预构建）
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

# nginx（使用阿里云apt镜像加速）
RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources && \
    apt-get update && apt-get install -y nginx --no-install-recommends && rm -rf /var/lib/apt/lists/*
COPY nginx.conf /etc/nginx/conf.d/default.conf
RUN rm -f /etc/nginx/sites-enabled/default

# 启动脚本
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 80
ENTRYPOINT ["/entrypoint.sh"]
