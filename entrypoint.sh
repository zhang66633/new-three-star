#!/bin/sh
# 启动 nginx + FastAPI
# set -e：任一命令失败即退出容器，避免"nginx 挂了但 uvicorn 照常起"的静默降级
set -e

# 启动 nginx（daemon 化）
nginx

# 启动 FastAPI（exec 使 uvicorn 成为容器 PID 1，正确接收 SIGTERM 优雅停机）
cd /app/backend
exec uvicorn main:app --host 0.0.0.0 --port 8000
