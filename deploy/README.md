# 生产部署手册（deploy/）

> 本文档记录线上基础设施拓扑与配置，供运维与恢复参考。

## 一、线上拓扑（腾讯云 110.42.210.117）

```
浏览器
  ├── 备案期：Cloudflare Pages（前端静态）──┐
  │          Cloudflare 命名隧道（API）────┤
  └── 生产期：sgweb.asia ── nginx-ssl ────┤
                                          ▼
                              game-server 容器（nginx + uvicorn）
                                 └─ named volume new-three-data（worlds.db 存档）
```

| 组件 | 位置 | 说明 |
|------|------|------|
| game-server 容器 | /opt/new-three/ | 应用本体，compose 项目名 new-three，端口仅 127.0.0.1:8080 |
| nginx-ssl 容器 | /data/nginx/ | 生产期对外 80/443（sgweb.asia）；备案期关闭（return 444） |
| cloudflared（命名隧道） | systemd: cloudflared | 备案期 API 通道，回源 127.0.0.1:8080 |
| cloudflared（快速隧道） | — | 已废弃，勿用（trycloudflare 不稳定） |

## 二、目录内文件

| 文件 | 用途 |
|------|------|
| docker-compose.server.yml | 服务器适配版 compose（容器名 game-server / 127.0.0.1:8080 / webnet 网络）。⚠️ 与仓库根目录 docker-compose.yml（通用模板 80:80）不同，部署后必须用本文件覆盖服务器上的 compose |
| cloudflared.named-tunnel.yml | 命名隧道配置（备案期 ingress 仅隧道专属主机名） |
| nginx.closed.conf | 备案期关闭配置（80/443 全 444）；原配置备份在服务器 /data/nginx/conf/nginx.conf.bak.20260816 |
| cf-quick.service.bak | 快速隧道 systemd 单元（已废弃，留存备查） |

## 三、部署流程（腾讯云）

```bash
# 1. 本地打包（排除密钥/缓存）
tar -czf pkg.tar.gz --exclude=backend/.env --exclude='*__pycache__*' \
  --exclude='*.db' --exclude=frontend/node_modules --exclude=frontend/dist \
  Dockerfile docker-compose.yml entrypoint.sh nginx.conf .dockerignore backend frontend docs

# 2. 上传 + 备份 + 解压
scp pkg.tar.gz ubuntu@110.42.210.117:/tmp/
ssh ubuntu@110.42.210.117 "sudo cp -a /opt/new-three /opt/new-three.bak.\$(date +%Y%m%d-%H%M) && sudo tar -xzf /tmp/pkg.tar.gz -C /opt/new-three"

# 3. 覆盖服务器适配 compose 并重建
scp deploy/docker-compose.server.yml ubuntu@110.42.210.117:/tmp/ && \
ssh ubuntu@110.42.210.117 "sudo cp /tmp/docker-compose.server.yml /opt/new-three/docker-compose.yml && cd /opt/new-three && sudo docker compose up -d --build"
```

## 四、备案期状态（当前）

- sgweb.asia：全关（DNS 解析到源站即 444；CF 侧隧道 ingress 不服务该域名）
- 游戏访问：Cloudflare Pages（前端）+ 命名隧道（API）
- 恢复生产：备案通过后——① 还原 nginx.conf.bak；② 隧道 ingress 恢复 sgweb.asia 规则并 route dns；③ 重启 nginx-ssl