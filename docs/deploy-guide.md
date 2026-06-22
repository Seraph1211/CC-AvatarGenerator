# 部署运维指南

*最近更新: 2026-06-22*
*对应进度: [Phase 5 - 首次公网部署](progress/phase-5-deploy-summary.md)*

本文档覆盖 CC-AvatarGenerator 的部署架构、运维速查、问题排查、重建指南。新接手的人按本文档应能在 1-2 小时内完成日常运维任务。

---

## 1. 部署概览

### 1.1 服务清单

| 域名 | 用途 | 后端 | 备注 |
|---|---|---|---|
| `godp.me` | 用户已有静态站 | node 8080 | `/etc/nginx/conf.d/hello-ssl.conf`,**不在本文档范围,不要动** |
| `avatar.godp.me` | **本项目** | uvicorn 8000 | `/etc/nginx/conf.d/avatar.conf`,独立 server block |

### 1.2 服务器

- **厂商**:阿里云 ECS(`iZbp1dpmrg52avfzildwmzZ`)
- **系统**:CentOS 7(`CentOS Linux 7 (Core)`,已 EOL 但还能跑)
- **配置**:2 核 2G,40G SSD,3.6G 内存
- **SSH 别名**:`PP_CloudServer`(`~/.ssh/config` 已配,用 `~/.ssh/id_rsa`)
- **IP**:120.55.14.190

### 1.3 域名 & DNS

- **主域**:`godp.me`(用户所有,已有网站在用)
- **子域**:`avatar.godp.me` ← 本项目
  - DNS 控制台添加一条 A 记录:`avatar.godp.me → 120.55.14.190`
  - TTL 600s
- 备用:`www.avatar.godp.me` 当前未加 A 记录(只签了 avatar 一个域名)

### 1.4 LLM API

- **当前主模型**:`GPT-Image-2` (PackyAPI 平台)
- **token**:`PACKYAPI_TOKEN_SORA`(PackyAPI 平台 GPT-Image-2 专用,与普通 `PACKYAPI_TOKEN` 不同)
- **.env 配置**:
  - `ACTIVE_MODEL=GPT-Image-2`
  - `SHOW_MODEL_SELECT=false`(隐藏模型选择区,统一用 ACTIVE_MODEL)
- **备选**:MiniMax `image-01`(`MINIMAX_API_KEY`)、`Gemini-3.1-Flash-Image-Preview`(PackyAPI 普通 token)等
- 详见 [`config.py`](../config.py) 的 `MODELS` 字典

---

## 2. 部署结构

```
/opt/avatar/CC-AvatarGenerator/         ← 项目根
  ├── .env                                ← API key(chmod 600, owner=root)
  ├── .venv/                              ← Python 3.11.10 虚拟环境
  ├── app.py, config.py, services/, static/, prompts/, references/, utils/
  └── logs/                               ← 历史日志(systemd journal 为主,这里保留过渡)

/etc/systemd/system/avatar.service       ← systemd unit,User=root
/etc/nginx/conf.d/avatar.conf            ← avatar.godp.me 的 server block
/etc/nginx/conf.d/hello-ssl.conf         ← godp.me 主站(**不要动**)
/etc/letsencrypt/live/avatar.godp.me/    ← SSL 证书
/var/www/letsencrypt/                    ← certbot webroot(http-01 验证用)
/usr/local/bin/python3.11                ← 编译安装的 Python 3.11.10
/usr/local/openssl/                      ← 编译安装的 OpenSSL 1.1.1w(Python _ssl 依赖)
/tmp/Python-3.11.10/, /tmp/openssl-1.1.1w/  ← 编译源码(可清理)
```

---

## 3. 关键配置文件

### 3.1 systemd service

`/etc/systemd/system/avatar.service`:

```ini
[Unit]
Description=CC-AvatarGenerator (FastAPI)
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/avatar/CC-AvatarGenerator
Environment="PATH=/opt/avatar/CC-AvatarGenerator/.venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/opt/avatar/CC-AvatarGenerator/.venv/bin/uvicorn app:app --host 127.0.0.1 --port 8000 --workers 2 --log-level info
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

> **CentOS 7 systemd 警告**:CentOS 7 自带的 systemd 不支持 `StandardOutput=append:` 这种 v230+ 的语法。所有日志走 `journalctl -u avatar.service`,不要往 `logs/avatar.stdout.log` 找。

### 3.2 nginx server block

`/etc/nginx/conf.d/avatar.conf`:

```nginx
# CC-AvatarGenerator(avatar.godp.me)
# 完全独立 server block,不干扰 godp.me 主站

server {
    listen 80;
    server_name avatar.godp.me www.avatar.godp.me;

    # Let's Encrypt http-01 验证需要这个 location
    location ^~ /.well-known/acme-challenge/ {
        root /var/www/letsencrypt;
        default_type "text/plain";
    }

    # 其他 80 请求 301 到 https
    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl http2;
    server_name avatar.godp.me www.avatar.godp.me;

    ssl_certificate     /etc/letsencrypt/live/avatar.godp.me/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/avatar.godp.me/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;
    ssl_session_cache   shared:SSL:10m;
    ssl_session_timeout 10m;

    client_max_body_size 12M;  # 略大于后端 10MB 上限

    # FastAPI 反代(uvicorn 绑 127.0.0.1:8000)
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        # LLM 调用可能 1-3 分钟
        proxy_read_timeout 180s;
        proxy_send_timeout 180s;
    }
}
```

---

## 4. 运维速查

### 4.1 服务管理

```bash
# 状态
ssh PP_CloudServer 'systemctl status avatar'

# 重启(代码更新后)
ssh PP_CloudServer 'systemctl restart avatar'

# 停止 / 启动
ssh PP_CloudServer 'systemctl stop avatar'
ssh PP_CloudServer 'systemctl start avatar'

# 禁用自启 / 启用自启
ssh PP_CloudServer 'systemctl disable avatar'
ssh PP_CloudServer 'systemctl enable avatar'
```

### 4.2 日志

```bash
# 实时跟踪
ssh PP_CloudServer 'journalctl -u avatar.service -f'

# 最近 100 行
ssh PP_CloudServer 'journalctl -u avatar.service -n 100 --no-pager'

# 最近 1 小时
ssh PP_CloudServer 'journalctl -u avatar.service --since "1 hour ago"'

# 按 request_id 过滤(request_id 是 8 位 hex,例如 [2697283a])
ssh PP_CloudServer 'journalctl -u avatar.service --since "1 hour ago" | grep "\[2697283a\]"'

# 看错误
ssh PP_CloudServer 'journalctl -u avatar.service --since "1 hour ago" | grep -iE "(error|exception|traceback)"'
```

### 4.3 代码更新

```bash
# 本地修改代码后,推送到服务器
rsync -avz --exclude='.venv' --exclude='__pycache__' --exclude='*.pyc' --exclude='.git' \
  --exclude='test/' --exclude='docs/cc-connect/' --exclude='docs/claude-code/' --exclude='docs/progress/' \
  ./ PP_CloudServer:/opt/avatar/CC-AvatarGenerator/

# 重启服务
ssh PP_CloudServer 'systemctl restart avatar'

# 验证
ssh PP_CloudServer 'curl -sI http://127.0.0.1:8000/'
```

### 4.4 .env 修改

```bash
ssh PP_CloudServer 'vim /opt/avatar/CC-AvatarGenerator/.env'
ssh PP_CloudServer 'chmod 600 /opt/avatar/CC-AvatarGenerator/.env'  # 必须,否则 systemd 拒绝读
ssh PP_CloudServer 'systemctl restart avatar'
```

### 4.5 依赖更新(改 requirements.txt 后)

```bash
# 1. 本地改 requirements.txt
# 2. rsync 推上去(见 4.3)
# 3. 服务器装新依赖
ssh PP_CloudServer 'cd /opt/avatar/CC-AvatarGenerator && .venv/bin/pip install -r requirements.txt'
ssh PP_CloudServer 'systemctl restart avatar'
```

### 4.6 SSL 证书

```bash
# 测试续期(不真续)
ssh PP_CloudServer 'certbot renew --dry-run'

# 实际续期
ssh PP_CloudServer 'certbot renew'

# 查看有效期
ssh PP_CloudServer 'openssl x509 -enddate -noout -in /etc/letsencrypt/live/avatar.godp.me/cert.pem'

# certbot 自动续期 cron 已配(/etc/cron.d/certbot,每天 0 点跑两次)
```

### 4.7 nginx

```bash
# 测试配置
ssh PP_CloudServer 'nginx -t'

# 重载(配置修改后)
ssh PP_CloudServer 'systemctl reload nginx'

# 错误日志
ssh PP_CloudServer 'tail -50 /var/log/nginx/error.log'

# 访问日志
ssh PP_CloudServer 'tail -50 /var/log/nginx/access.log'
```

### 4.8 磁盘 / 内存

```bash
ssh PP_CloudServer 'df -h /'
ssh PP_CloudServer 'free -h'
ssh PP_CloudServer 'du -sh /opt/avatar/CC-AvatarGenerator/{logs,.venv,references}'
```

---

## 5. 健康检查清单

### 5.1 后端存活

```bash
# 8000 端口监听
ssh PP_CloudServer 'ss -tlnp | grep 8000'  # 应有 uvicorn

# GET / 返回 405(只允许 POST)
ssh PP_CloudServer 'curl -sI http://127.0.0.1:8000/'  # 405 + allow: GET

# /models 端点
ssh PP_CloudServer 'curl -s http://127.0.0.1:8000/models'
# 期望: {"default":"image-01","enabled":false,"models":[]}
# 注:SHOW_MODEL_SELECT=false 时 models 空;default 字段为第一个 visible 模型(架构已知行为,详见 phase-5 总结)
```

### 5.2 公网访问

```bash
# HTTP 强制 HTTPS
curl -sI http://avatar.godp.me/         # 301 → https://avatar.godp.me/

# HTTPS GET(应返回 index.html)
curl -sI https://avatar.godp.me/        # 200 + Content-Type: text/html

# /models 端点
curl -s https://avatar.godp.me/models   # 完整 JSON
```

### 5.3 端到端生成测试

```bash
ssh PP_CloudServer 'cd /opt/avatar/CC-AvatarGenerator && .venv/bin/python <<EOF
import httpx, base64, time
from PIL import Image, ImageDraw

# 1. 准备测试照片
img = Image.new("RGB", (512, 512), (240, 230, 220))
draw = ImageDraw.Draw(img)
draw.ellipse((150, 100, 360, 310), fill=(255, 220, 180), outline=(80, 60, 40), width=3)
draw.ellipse((200, 180, 230, 210), fill=(50, 40, 30))
draw.ellipse((280, 180, 310, 210), fill=(50, 40, 30))
draw.arc((220, 230, 290, 280), start=0, end=180, fill=(80, 60, 40), width=3)
img.save("/tmp/test_face.jpg", "JPEG", quality=85)

# 2. 调 /generate
start = time.time()
with open("/tmp/test_face.jpg", "rb") as f:
    r = httpx.post("http://127.0.0.1:8000/generate",
                   files={"file": ("t.jpg", f, "image/jpeg")},
                   data={"model": ""}, timeout=120.0)
print(f"HTTP {r.status_code}, {time.time()-start:.1f}s")
if r.status_code == 200:
    body = r.json()
    print(f"model_used={body[\"model_used\"]}, platform={body[\"platform\"]}, "
          f"latency_ms={body[\"latency_ms\"]}")
    img_bytes = base64.b64decode(body["image_base64"])
    with open("/tmp/avatar_output.png", "wb") as out:
        out.write(img_bytes)
    out_img = Image.open("/tmp/avatar_output.png")
    print(f"output: {out_img.size} {out_img.mode}, {len(img_bytes)} bytes")
EOF'
```

期望输出:
```
HTTP 200, 32.x 秒
model_used=GPT-Image-2, platform=PackyAPI, latency_ms=32340
output: (1024, 1024) RGB, 700000+ bytes
```

---

## 6. 常见问题排查

### 6.1 服务起不来

```bash
ssh PP_CloudServer 'systemctl status avatar'
ssh PP_CloudServer 'journalctl -u avatar.service -n 100 --no-pager'
```

常见原因:
- `.env` 权限错(必须 `chmod 600`,owner=root)
- `.venv/bin/python` 不存在 → 重建 venv(参考 §9)
- `/usr/local/bin/python3.11` 丢失 → 重新编译(参考 §9)

### 6.2 `_ssl` 模块报错

```
ModuleNotFoundError: No module named '_ssl'
```

原因:Python 3.11 没链接到 OpenSSL 1.1.1+。

修复:参考 §9 步骤 2-3,先编译 OpenSSL 1.1.1w 到 `/usr/local/openssl`,再重编 Python 时加 `--with-openssl=/usr/local/openssl --with-openssl-rpath=auto`。

### 6.3 GLIBC 版本错误

```
/lib64/libc.so.6: version 'GLIBC_2.28' not found
```

原因:用了新版 prebuilt Python(conda latest / python-build-standalone),但 CentOS 7 glibc 是 2.17。

解决:**用源码编译方式装 Python**(参考 §9),不要用 prebuilt 二进制。详见 [phase-5 踩坑](progress/phase-5-deploy-summary.md#踩过的坑)。

### 6.4 DNS 没生效

```bash
dig +short avatar.godp.me
# 期望: 120.55.14.190
# 如果是 198.18.0.X(RFC 6890 保留地址):DNS 控制台配错了,wildcard 或 IP 写错
# 如果什么都没有:DNS 还没生效,等 TTL(最多 10 分钟)
```

### 6.5 certbot 续期失败

```bash
ssh PP_CloudServer 'certbot renew --dry-run'
```

可能原因:
- 80 端口被占用 → `systemctl status nginx`
- webroot 路径不存在 → `ls /var/www/letsencrypt/.well-known/acme-challenge/`
- DNS 变更 → 检查 A 记录

### 6.6 LLM 调用超时 / 失败

看 journal:
```bash
ssh PP_CloudServer 'journalctl -u avatar.service --since "1 hour ago" | grep -iE "(timeout|error|exception|provider.done)"'
```

可能:
- PackyAPI 平台临时故障 → 切到 `image-01`(MiniMax)做兜底
- 网络问题 → 服务器到 PackyAPI 的连通性 `curl -sI https://www.packyapi.com`
- API token 过期 → 检查 PackyAPI 控制台

### 6.7 502 Bad Gateway

nginx 拿不到 uvicorn:
```bash
ssh PP_CloudServer 'systemctl status avatar'  # 确认 uvicorn 跑了
ssh PP_CloudServer 'ss -tlnp | grep 8000'    # 8000 端口监听?
ssh PP_CloudServer 'tail -20 /var/log/nginx/error.log'
```

### 6.8 404

- 检查 `server_name avatar.godp.me` 在 nginx conf 是否正确
- 检查请求的 Host header 是否真是 `avatar.godp.me`(curl 加 `-H "Host: avatar.godp.me"`)

---

## 7. 监控 & 告警(post-MVP)

当前阶段**未配置**监控,靠人工 `journalctl -u avatar.service` + `journalctl -xe`。

**建议接入**(流量起来后再做):

- **UptimeRobot**(免费):每 5 分钟 GET `https://avatar.godp.me/`,挂了发邮件
- **Sentry / GlitchTip**:捕获 uvicorn 异常 stacktrace
- **journalctl → ELK / Loki**:日志聚合,按 request_id 查询

---

## 8. 已知待修问题(用户决定暂缓)

| # | 任务 | 优先级 | 触发时机 |
|---|---|---|---|
| 1 | 收紧 CORS `allow_origins=["*"]` → `["https://avatar.godp.me"]` | 中 | 接到"被恶意调用"投诉时 |
| 2 | 添加 `/healthz` 健康检查端点 | 低 | 接 UptimeRobot 时 |
| 3 | IP 限流(slowapi)每分钟 5 次 | 中 | 流量起来后(>100 次/天) |
| 4 | 全局异常处理,500 不暴露 stacktrace | 中 | 用户报告"看到内部错误"时 |
| 5 | `/privacy` 隐私声明页面 | 低 | 用户问隐私 / 合规审查时 |

详见 [`progress/phase-5-deploy-summary.md` 的"未完成"段](progress/phase-5-deploy-summary.md#未完成--留给下一阶段)。

---

## 9. 重建指南(从零部署到当前状态)

如果服务器重装,按以下步骤恢复:

### 9.1 装编译依赖 + certbot

```bash
ssh PP_CloudServer
yum install -y gcc openssl-devel bzip2-devel libffi-devel zlib-devel \
               make wget tar ca-certificates certbot
```

### 9.2 编译 OpenSSL 1.1.1w

```bash
# git clone 最快(清华源 / GitHub releases 限速严重,git clone 反而稳)
cd /tmp
git clone --depth 1 --branch OpenSSL_1_1_1w \
  https://github.com/openssl/openssl.git openssl-1.1.1w
cd openssl-1.1.1w
./config --prefix=/usr/local/openssl shared zlib
make -j 2
make install
ldconfig
/usr/local/openssl/bin/openssl version  # 期望: OpenSSL 1.1.1w
```

### 9.3 编译 Python 3.11.10

```bash
cd /tmp
curl -L -o Python-3.11.10.tgz \
  https://mirrors.tuna.tsinghua.edu.cn/python/3.11.10/Python-3.11.10.tgz
tar xzf Python-3.11.10.tgz
cd Python-3.11.10
./configure --prefix=/usr/local \
            --with-openssl=/usr/local/openssl \
            --with-openssl-rpath=auto \
            --with-ensurepip=upgrade
make -j 2
make altinstall
/usr/local/bin/python3.11 -c "import ssl, _ssl; print(ssl.OPENSSL_VERSION)"
# 期望: OpenSSL 1.1.1w ... 且 _ssl 不报错
```

### 9.4 部署项目代码

```bash
# 在本地项目目录执行:
rsync -avz --exclude='.venv' --exclude='__pycache__' --exclude='*.pyc' \
  --exclude='.git' --exclude='test/' \
  --exclude='docs/cc-connect/' --exclude='docs/claude-code/' --exclude='docs/progress/' \
  ./ PP_CloudServer:/opt/avatar/CC-AvatarGenerator/

# 服务器上修权限
ssh PP_CloudServer 'chown -R root:root /opt/avatar/CC-AvatarGenerator/ && \
                    chmod 600 /opt/avatar/CC-AvatarGenerator/.env'
```

### 9.5 建 venv + 装依赖

```bash
ssh PP_CloudServer <<'EOF'
cd /opt/avatar/CC-AvatarGenerator
/usr/local/bin/python3.11 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
.venv/bin/python -c "import fastapi, uvicorn, httpx, openai, multipart, PIL, dotenv, ssl, _ssl; print('ALL OK')"
EOF
```

### 9.6 写 systemd service

参考 §3.1,写入 `/etc/systemd/system/avatar.service`。

### 9.7 写 nginx config + 签证书

参考 §3.2,写入 `/etc/nginx/conf.d/avatar.conf`,然后:

```bash
ssh PP_CloudServer <<'EOF'
mkdir -p /var/www/letsencrypt
nginx -t && systemctl reload nginx
# 假设 DNS 已加 A 记录
certbot certonly --webroot -w /var/www/letsencrypt -d avatar.godp.me \
  --non-interactive --agree-tos --register-unsafely-without-email
nginx -t && systemctl reload nginx
EOF
```

### 9.8 启动 + 验证

```bash
ssh PP_CloudServer <<'EOF'
systemctl daemon-reload
systemctl enable --now avatar
systemctl status avatar
EOF
curl -sI https://avatar.godp.me/   # 期望 200
```

### 9.9 关键陷阱(踩过的坑)

- ❌ **不要用 `python-build-standalone`**(要求 GLIBC 2.28)
- ❌ **不要用最新 miniconda**(要求 GLIBC 2.28)
- ❌ **不要用 IUS / EPEL repo**(EOL,无 Python 3.11 包)
- ✅ **必须先编译 OpenSSL 1.1.1**,再编译 Python 链接过去,否则 `_ssl` 缺失
- ✅ **`git clone` 比 `curl tar.gz` 稳**(国内访问 GitHub releases 经常超时)

---

## 10. 参考 & 关联

- [progress/phase-5-deploy-summary.md](progress/phase-5-deploy-summary.md) — 部署过程详细总结
- [architecture.md](architecture.md) — 系统架构(请求链路、provider 抽象)
- [design-decisions.md](design-decisions.md) — 关键设计决策
- [mvp-plan.md](mvp-plan.md) — MVP 目标 / 范围
- [CLAUDE.md](../CLAUDE.md) — 项目根 CLAUDE.md
