# Phase 5: 首次公网部署 - 进度总结

*完成日期: 2026-06-22*
*对应 commit: (本阶段为部署工作,代码未 commit,见下)*
*对应文档: [deploy-guide.md](../deploy-guide.md) — 部署运维指南*

---

## 目标

把 Phase 1-4 已完成的 MVP 部署到公网,让真实用户能访问,**首次验证"用户愿不愿意为这个付钱"的真实场景**。

子目标:
1. 选一个能"30 分钟内让 URL 跑起来"的部署方案(MVP 阶段不追求完美)
2. 完全不破坏用户已有的 `godp.me` 主站(同台服务器已在跑 `hello-ssl.conf`)
3. 留出清晰的运维入口给下一个人接手
4. 把"代码 ready for production 的修复"和"上线"分开(用户决定暂不修代码)

---

## 已完成

- ✅ **服务器选定**:阿里云 ECS `PP_CloudServer`(`120.55.14.190`,CentOS 7 2核2G)
- ✅ **域名策略**:用子域名 `avatar.godp.me`(不动主域 `godp.me` 的现有配置)
- ✅ **DNS**:用户控制台加 A 记录 `avatar.godp.me → 120.55.14.190`
- ✅ **HTTPS**:Let's Encrypt 证书(`certonly --webroot` 模式,90 天自动续)
- ✅ **Python 3.11.10**:源码编译 + 链接到新编译的 OpenSSL 1.1.1w,`_ssl` 模块完整
- ✅ **OpenSSL 1.1.1w**:源码编译到 `/usr/local/openssl`(CentOS 7 自带 OpenSSL 1.0.2 太旧)
- ✅ **venv**:`/opt/avatar/CC-AvatarGenerator/.venv`,所有依赖装齐
- ✅ **systemd service**:`/etc/systemd/system/avatar.service`,2 worker,绑 `127.0.0.1:8000`
- ✅ **nginx server block**:`/etc/nginx/conf.d/avatar.conf`,独立配置,完全不碰 `hello-ssl.conf`
- ✅ **代码部署**:rsync 推 3.6MB 代码(排除 `.venv` / `.git` / `test/` / 部分 `docs/`)
- ✅ **端到端验证**:用 PIL 生成的测试照片调用 `POST /generate`,32.6 秒返回 1024×1024 PNG
- ✅ **运维文档**:`docs/deploy-guide.md`(228 行),覆盖运维速查 / 问题排查 / 重建指南
- ✅ **进度记录**:本文件

---

## 关键决策与理由

| # | 决策 | 理由 |
|---|---|---|
| 1 | **用子域名 `avatar.godp.me`** | 服务器已有 `godp.me` 主站(`hello-ssl.conf` 在跑);子域名零冲突,SSL 独立,失败不影响主站 |
| 2 | **腾讯云/阿里云轻量服务器** | 国内用户访问 MiniMax/PackyAPI 稳定;PaaS(FC)冷启动对 LLM 长调用不友好 |
| 3 | **源码编译 OpenSSL 1.1.1 + Python 3.11** | CentOS 7 自带 OpenSSL 1.0.2 太旧;prebuilt Python(GLIBC 2.28 要求)/miniconda latest / IUS repo 全部不可用;源码编译是唯一稳的路 |
| 4 | **systemd + uvicorn 2 worker** | FastAPI 官方推荐 uvicorn;systemd 是 CentOS 7 标配,自启 + 崩溃重启开箱即用 |
| 5 | **nginx 反代 + 单独 server block** | 复用现有 nginx,只新增 `avatar.conf`;不动 `nginx.conf` 和 `hello-ssl.conf`;SSL 终止在 nginx,后端绑 127.0.0.1 不直接暴露 |
| 6 | **代码更新用 rsync 而非 git clone** | 服务器不需要 github ssh key;rsync 增量快;本地代码就是 source of truth |
| 7 | **`SHOW_MODEL_SELECT=false` 单模型部署** | 用户改默认模型为 `GPT-Image-2` 后,隐藏模型选择区,业务流程不出现"模型"这种技术概念 |
| 8 | **`/models.default` 字段保留 image-01**(已知行为) | 这是 Phase 4 架构:`get_visible_default()` 返回第一个 visible 模型;`SHOW_MODEL_SELECT=false` 时该字段前端不展示,仅作调试入口;不影响功能 |
| 9 | **代码修复 vs 部署分离** | 用户明确决定"上线前的修复(CORS/限流/healthz 等)先记录,暂不修";MVP 阶段快速上线 > 完美 |
| 10 | **端到端测试用 PIL 生成占位照片** | 避免把用户真实照片传到服务器;占位图能验证整条链路(预处理 → provider → 质量门 → 响应) |

---

## 踩过的坑

### 坑 1:`/etc/nginx/conf.d/hello-ssl.conf` 已占 godp.me:80/443

- **现象**:SSH 上去发现 80/443 已有 nginx 在跑,`server_name godp.me`
- **根因**:这台服务器用户已部署过 `hello-ssl.conf`(serve `/var/www/godp/live/` 静态站 + 端口 8080 上一个 node app)
- **修复**:用子域名 `avatar.godp.me` + 独立 server block,完全不碰 `hello-ssl.conf`

### 坑 2:`dig +short avatar.godp.me` 返回 `198.18.0.X`(RFC 6890 保留地址)

- **现象**:用户说"已加 A 记录",但 dig 返回保留地址段
- **根因**:本地 DNS 服务商可能加了 wildcard `*.godp.me → 198.18.0.X` 测试占位;或 A 记录值填错
- **修复**:不需要管本地 dig 结果——**真正重要的是 Let's Encrypt 服务器能不能解析**(certbot 用 `certbot.com` 的 DNS 视角)。最终 certbot 通过了,说明实际 DNS 是对的

### 坑 3:certbot 第一次尝试带 `www.avatar.godp.me` 失败

- **现象**:`certbot certonly -d avatar.godp.me -d www.avatar.godp.me` 报 `NXDOMAIN for www.avatar.godp.me`
- **根因**:用户只加了 `avatar.godp.me` 的 A 记录,没加 `www.avatar.godp.me`
- **修复**:**只签 `avatar.godp.me` 一个域名**(`certbot certonly -d avatar.godp.me`),暂时不带 www。后续如要带 www,再加 A 记录再签

### 坑 4:Python 3.11 编译后 `import _ssl` 报 `ModuleNotFoundError`

- **现象**:第一个 Python 3.11 编译完成,virtualenv 建好,pip 装依赖成功,但 `import ssl` 失败,说找不到 `_ssl` 模块
- **根因**:**CentOS 7 自带 OpenSSL 1.0.2**,Python 3.11 编译时检测到 openssl-devel 但版本太旧,自动跳过 `_ssl` 模块
- **修复**:**先编译 OpenSSL 1.1.1w 到 `/usr/local/openssl`**,再重编 Python 时加 `--with-openssl=/usr/local/openssl --with-openssl-rpath=auto`,验证 `import ssl; print(ssl.OPENSSL_VERSION)` 输出 `OpenSSL 1.1.1w`

### 坑 5:Miniconda 最新版要求 GLIBC ≥ 2.28

- **现象**:退而求其次试 Miniconda,installer 报错 `Installer requires GLIBC >= 2.28, but system has 2.17`
- **根因**:Miniconda 自带的 Python 用 conda-forge 编译,链接到新版 glibc
- **修复**:放弃 Miniconda 路线,坚持源码编译

### 坑 6:GitHub releases tarball 下载超时

- **现象**:`curl -L https://github.com/openssl/openssl/releases/download/.../openssl-1.1.1w.tar.gz` 在 90 秒超时内只下 2.2MB / 9MB
- **根因**:GitHub releases 在国内访问限速严重
- **修复**:**改用 `git clone --depth 1 --branch OpenSSL_1_1_1w`**(git smart HTTP 反而快,8 秒下完整 1.1.1w 源码)

### 坑 7:CentOS 7 systemd 不支持 `StandardOutput=append:` 语法

- **现象**:systemd service 文件写了 `StandardOutput=append:/opt/.../logs/avatar.stdout.log`,`systemctl status` 显示文件不存在
- **根因**:`StandardOutput=append:` 是 systemd v230+ 的特性,CentOS 7 自带 systemd 219 不支持
- **修复**:**全部日志走 `journalctl -u avatar.service`**,删除 service 文件里的 `StandardOutput=append:` 行;CentOS 7 部署通用做法

### 坑 8:Python venv 创建失败(用旧 `python3.11` 路径)

- **现象**:第一次编译的 Python(没 `_ssl` 模块),venv 创建成功,但装依赖后跑不起来
- **根因**:venv 指向的 `python3.11` 是第一次编译的版本,`_ssl` 模块空缺
- **修复**:删掉 venv 重来:`rm -rf .venv && /usr/local/bin/python3.11 -m venv .venv`(用重编后的 Python 3.11)

---

## 未完成 / 留给下一阶段

### 已记录但未修(用户决定上线后再处理)

- [ ] **收紧 CORS**:`app.py:21` 当前 `allow_origins=["*"]`,改为只允许 `https://avatar.godp.me`,防止恶意网站跨域调用消耗 API 配额
- [ ] **添加 `/healthz` 健康检查端点**:为后续接 UptimeRobot / 负载均衡探活做准备
- [ ] **IP 限流**:用 `slowapi`,每 IP 1 分钟 5 次,防止恶意高频调用
- [ ] **全局异常处理**:`HTTPException(detail=str(e))` 当前把内部异常返给前端,可能泄漏细节;加 FastAPI exception_handler
- [ ] **`/privacy` 隐私声明页面**:明确说明"照片立即处理,不持久化"

### 监控 / 运维改进

- [ ] **接 UptimeRobot**(免费),挂了发邮件
- [ ] **接 Sentry / GlitchTip**,捕获 uvicorn 异常 stacktrace
- [ ] **日志聚合**(journalctl → ELK / Loki),按 request_id 跨服务查询
- [ ] **LLM 调用成本监控**:PackyAPI / MiniMax 按量付费,需要 dashboard 防账单失控

### 代码改进

- [ ] **`/models.default` 字段行为**:`SHOW_MODEL_SELECT=false` 时返回 ACTIVE_MODEL 而非第一个 visible(架构改进,非 bug)
- [ ] **质量门升级**:当前 `services/quality_checker.py` 只是 PIL decode 校验;Phase 4 遗留任务,post-MVP 接入 CV 边缘密度/色彩分布
- [ ] **异步任务队列**:当前 `POST /generate` 是同步阻塞;LLM 调用 30s-3min,长连接用 nginx `proxy_read_timeout 180s` 顶着;量大后改 job_id + 轮询

---

## 下个 session 接手时

1. **先读 [`deploy-guide.md`](../deploy-guide.md)** — 这是新接手的"主说明书",覆盖运维速查 / 问题排查 / 重建指南
2. **重点看 §4(运维速查)和 §6(常见问题)**:90% 的日常操作在那里
3. **重点看 `app.py` 当前 CORS 配置**(`allow_origins=["*"]`)— 上线后第一件该修的
4. **重点看 `config.py:ACTIVE_MODEL`**:当前是 `GPT-Image-2`(`PACKYAPI_TOKEN_SORA`),切模型改这里
5. **注意**:CentOS 7 systemd 不支持 `StandardOutput=append:`,日志走 `journalctl`
6. **注意**:CentOS 7 EOL 但还能跑(阿里云镜像源活着),重编 OpenSSL + Python 是必须操作,不要试图装 prebuilt

---

## 业务 vs 开发的"模型选择"双模(Phase 4 遗产)

```
┌────────────────────────────────────────────┐
│  普通用户(业务流) ← 当前 SHOW_MODEL_SELECT=false │
│  → /models 返回 {enabled:false, models:[]}  │
│  → 前端无下拉框                             │
│  → 业务流程不出现任何模型信息                │
│  → 统一用 ACTIVE_MODEL                      │
└────────────────────────────────────────────┘
```

详见 [`architecture.md` 的"功能开关"段](../architecture.md#9) 和 [`phase-4-ui-logs-summary.md`](phase-4-ui-logs-summary.md)。

---

## 部署时间线(实际)

```
T+0:00    接用户指令"把项目发布到网络"
T+0:05    摸清服务器状态(CentOS 7 / Python 3.6.8 / nginx 1.20.1 / 有 godp.me 主站)
T+0:10    决定子域名方案 + 建任务清单
T+0:15    yum 装编译依赖 + certbot + 创建部署目录
T+0:20    清华源下载 Python 3.11.10 源码 + 后台编译
T+0:35    systemd service + nginx avatar.conf 写完
T+0:40    Python 编译完成 → 创建 venv → 装依赖(发现 _ssl 缺失)
T+0:45    签 SSL 证书(avatar.godp.me,只签一个域名)
T+0:50    试 miniconda → GLIBC 不兼容
T+1:00    试 python-build-standalone → 404
T+1:05    git clone OpenSSL 1.1.1w → 后台编译(5 分钟)
T+1:10    OpenSSL 完成 → 重编 Python with --with-openssl(8 分钟)
T+1:20    重编完成 → 重建 venv → 装依赖 → 验证 _ssl OK
T+1:25    启动 systemd + nginx reload + 端到端测试
T+1:30    ✅ 端到端验证成功(32.6 秒返回 1024×1024 PNG)
T+1:35    写文档(deploy-guide.md + phase-5 summary)
```

总耗时约 1.5 小时,其中:
- 编译占 30 分钟(OpenSSL 5min + Python 8-12min + 几次重试浪费的)
- 部署 / 验证 / 文档占 1 小时

---

## 关联

- **本阶段未 commit**(部署工作产物在服务器 `/opt/avatar/` 和 `/etc/`,本机代码未变);如需回滚,服务器 `systemctl stop avatar` + `rm /etc/nginx/conf.d/avatar.conf` 即可
- **涉及新增文档**:
  - [`deploy-guide.md`](../deploy-guide.md) — 部署运维指南(228 行)
  - [`README.md`](README.md) — 索引更新(添加 Phase 5)
- **涉及配置**(服务器端):
  - `/etc/systemd/system/avatar.service`
  - `/etc/nginx/conf.d/avatar.conf`
  - `/etc/letsencrypt/live/avatar.godp.me/`
  - `/opt/avatar/CC-AvatarGenerator/.venv/`
  - `/usr/local/bin/python3.11` + `/usr/local/openssl/`
- **未触动**(故意保留):
  - `/etc/nginx/conf.d/hello-ssl.conf` (godp.me 主站)
  - `/opt/hello-app/` (用户现有 node 应用)
  - 项目代码(本机 + 服务器完全一致,仅 rsync 推一次)

---

## 统计

- **服务器文件新增**:~250 行(systemd + nginx config + certbot 配置 + 编译脚本)
- **本机文档新增**:
  - `docs/deploy-guide.md` (228 行)
  - `docs/progress/phase-5-deploy-summary.md` (本文件,约 220 行)
  - `docs/progress/README.md` (索引更新)
- **服务器编译产物**:
  - OpenSSL 1.1.1w → `/usr/local/openssl/` (bin/lib/include,约 50MB)
  - Python 3.11.10 → `/usr/local/bin/python3.11` + lib (~150MB)
  - Python venv → `/opt/avatar/CC-AvatarGenerator/.venv/` (~150MB)
- **端到端测试结果**:32.6 秒 / 1024×1024 PNG / 709KB
- **时间**:约 1.5 小时(含 3 次失败的方案尝试)

---

## 反思(本阶段写给未来的自己)

**1. CentOS 7 + Python 3.11 是个"小冰山"**。你以为只是装个 Python,实际上是 OpenSSL 版本不兼容 + GLIBC 版本不够 + systemd 版本太老三个连环坑。下次如果遇到 CentOS 7 部署现代 Python 的需求,**直接用 docker** 或 pyenv(不,pyenv 也是源码编译……)。

**2. 国内访问 GitHub releases 是真的慢**。`curl tar.gz` 经常超时,但 `git clone --depth 1` 用 git smart HTTP 反而稳。可能 git 用了不同的 CDN 路径。下次国内下载大文件**优先 git clone**,fallback curl。

**3. certbot 的 NXDOMAIN 错误信息很有信息量**。它会**精确告诉你哪个域名失败**,让你知道该去 DNS 控制台补哪条记录。

**4. systemd 版本差异是隐形坑**。CentOS 7 systemd 219 不支持很多 systemd 230+ 的特性(如 `StandardOutput=append:`)。在写 unit 文件时,**先查 systemd 版本**(`systemctl --version`),不要假定语法通用。

**5. 用户说"已加 A 记录"不一定是字面意思**。他说加了,但本地 dig 可能因为 wildcard 或 DNS 缓存看不到。**真正重要的是 certbot 的视角**——它能验证就行。

**6. 子域名是同台多服务的最优解**。这次 godp.me 已被占,如果我直接覆盖,要么破坏用户现有网站,要么搞复杂的 location 嵌套。**直接用子域名,新建独立 server block**,零冲突,可逆。

**7. 部署文档比部署脚本更重要**。脚本能跑过就算交付了,但文档要回答"半年后你怎么知道下一步该怎么操作"。`deploy-guide.md` 的 §4(运维速查)和 §6(问题排查)是高频查阅区域,要写得详细、可执行、能复制粘贴。

**8. "代码 ready for production 的修复"和"上线"分开是对的**。MVP 阶段,CORS/限流/健康检查这些是"应该有"但不是"必须有"。先上线,有用户了再补,比"完美部署,零用户"好。
