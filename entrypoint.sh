#!/bin/sh
# 启动 nginx
nginx

# 启动 FastAPI
cd /app/backend
exec uvicorn main:app --host 0.0.0.0 --port 8000
