#!/bin/sh
# 启动 nginx + FastAPI
# set -e：任一命令失败即退出容器，避免"nginx 挂了但 uvicorn 照常起"的静默降级
set -e

# nginx 前台模式（daemon off）后台运行——daemon 模式是脱离终端的后台进程，
# 容器 SIGTERM 只达 PID 1，nginx 会被 SIGKILL 硬切，在飞 SSE 长连接被粗暴掐断。
# 前台模式下 nginx master 收到 TERM 能优雅 drain 连接。
nginx -g 'daemon off;' &
NGINX_PID=$!

# FastAPI 后台运行（uvicorn）
cd /app/backend
uvicorn main:app --host 0.0.0.0 --port 8000 &
UVICORN_PID=$!

# 信号转发：docker stop → 本脚本（PID 1）收 SIGTERM → 转发给 nginx + uvicorn 优雅退出
trap 'kill -TERM $NGINX_PID $UVICORN_PID 2>/dev/null || true' TERM INT

# 等 uvicorn 退出（保留其退出码），再收尾 nginx
UVICORN_RC=0
wait $UVICORN_PID || UVICORN_RC=$?
kill -TERM $NGINX_PID 2>/dev/null || true
wait $NGINX_PID 2>/dev/null || true
exit $UVICORN_RC
