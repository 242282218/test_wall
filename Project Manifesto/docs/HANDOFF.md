# Quark-Media-System Handoff

> 目的：让任何人在新会话/新电脑/新同事情况下，按本文档即可复现环境、理解进度、继续开发与对接。  
> 维护：每次迭代更新 Commit/Verified/Next steps/Backend gaps；tokens 快满必须更新；不写密钥、不贴大段代码。

---

## 1) 项目概览
- 项目：Quark-Media-System（元数据“虚实结合”云盘影音系统）
- 理念：存链不存文（虚拟收藏 + JIT 实体化 + WebDAV 统一消费）
- 参考（仅模式，不拷贝源码/依赖）：kerkerker / tmdb_wall / kerkerker-douban-service

---

## 2) 当前代码状态（必填）
- Repo Root：`C:\Users\24228\Desktop\qtmx\Quark-Media-System`
- Branch：`master`
- Commit：`a0059a8537785413252b987b652ad10eeeb6c4ec`
- Iteration：`8`
- Owner：`Codex`
- Updated：`2026-01-07 11:04`

---

## 3) 目录结构（两层）
```
Quark-Media-System/
  docs/
  references/
  frontend/
    public/
    src/
  services/
    core-backend/
    quarkdrive-webdav/
    workers/
  scripts/
  data/  # runtime data (gitignored)
```

---

## 4) 快速开始（可复现）

### 4.1 前端（frontend）
```bash
cd frontend
npm ci
npm run typecheck
npm run lint
npm run build
```

开发运行（推荐稳定端口）：

```bash
npm run dev:55210
# http://127.0.0.1:55210/
# http://127.0.0.1:55210/movie/872585
```

已知问题：

* 3000 端口在部分环境 EACCES，优先使用 55210。

### 4.2 后端（core-backend，如需联调）

* Path：`services/core-backend`
* Start：`<command>`
* Deps：`<db/redis/queue>`
* Base URL：`<http://127.0.0.1:xxxx>`

---

## 5) 环境变量（只写变量名与用途，不写值）

> `.env*` gitignore；仓库只保留 `.env.example`

### 5.1 前端

* `NEXT_PUBLIC_API_BASE`：后端 API Base；为空走 mock fallback
* `NEXT_PUBLIC_TMDB_KEY`：TMDB Key（如前端直连）
* `NEXT_PUBLIC_WEBDAV_BASE`：WebDAV Base（播放器/挂载用）
* `NEXT_PUBLIC_APP_NAME`：可选站点名

### 5.2 后端（如适用）

* `<VAR>`：<purpose>

---

## 6) 已实现功能（按模块）

### 6.1 前端骨架（MVP）

* [x] `/` 海报墙：Favorites + Trending 分区
* [x] `/movie/[tmdbId]` 详情：自动 search links + 列表
* [x] 资源状态：VIRTUAL / MATERIALIZED / PROVISIONING / FAILED
* [x] 按钮占位：Save (Virtual) / Watch Now (JIT)
* [x] API Client：统一封装 + mock fallback + types
* [x] JIT 任务轮询：`/tasks/{taskId}`（可用时）+ 状态映射

实现位置：

* Pages：`frontend/src/app/...`
* Components：`frontend/src/components/...`
* API：`frontend/src/lib/api/...`
* Hooks：`frontend/src/lib/hooks/...`

### 6.2 文档与规范

* [x] `docs/AGENT_RULES.md`
* [x] `docs/api-contract.md`
* [x] `docs/DEV_SETUP.md`
* [x] `docs/REFERENCE_NOTES.md`

---

## 7) Verified（确实跑过的）

* `npm ci`：n/a（本轮未运行）
* `npm run typecheck`：✅
* `npm run lint`：✅（零警告）
* `npm run build`：✅
* `npm run dev:55210`：✅

  * `/`：HTTP `200`
  * `/movie/872585`：HTTP `200`

---

## 8) API 对接结论（最重要）

> 以 `services/core-backend` 代码为准，其次以 `docs/api-contract.md`。

### 8.1 Backend confirmed（已确认）

* `GET /api/v1/home`：首页聚合（favorites/trending）
* `GET /api/v1/media/{tmdbId}`：详情聚合（resources）
* `POST /api/v1/media/{tmdbId}/links/virtual`：保存虚拟收藏
* `POST /api/v1/media/{tmdbId}/provision`：触发 JIT（返回 taskId）
* `GET /api/v1/tasks/{taskId}`：任务状态
* `POST /api/v1/share/parse`：解析分享链接；返回 `total_count` + `files[]`
* `GET /api/v1/resources/search?keyword=`：资源搜索；返回 `data[]/cloudLinks`
* `GET /api/v1/resources/channels`：频道列表
* `GET /api/v1/tasks/stats`：任务统计
* `GET/DELETE /api/v1/tasks/dead`：死信队列
* `POST /api/v1/tasks/dead/retry/{media_id}`：重试任务
* `POST /api/v1/tasks/cookie/update`、`GET /api/v1/tasks/cookie/validate`

### 8.2 Backend gaps（缺失/待确认）

* 当前契约无缺口；TMDB 元数据（poster/backdrop/genres/rating）需后续补齐或接入外部源

### 8.3 契约文件

* File：`docs/api-contract.md`
* Aligned at：`2026-01-07`
* Backend refs：`services/core-backend/app/api/routes.py`, `services/core-backend/app/schemas/media.py`, `services/core-backend/app/schemas/share.py`, `services/core-backend/app/schemas/resources.py`, `services/core-backend/app/models/media.py`, `services/core-backend/app/main.py`

### 8.4 Frontend wiring（API_BASE 有值时）

* 首页：`GET /api/v1/home` → HomeFeed
* 详情：`GET /api/v1/media/{tmdbId}` → TmdbDetail
* 收藏：`POST /api/v1/media/{tmdbId}/links/virtual` → VIRTUAL
* JIT：`POST /api/v1/media/{tmdbId}/provision`（linkId/shareUrl） → TaskRecord；轮询 `GET /api/v1/tasks/{taskId}`（4s）并映射 TaskStatus → ResourceStatus

---

## 9) 已知问题与技术债

* [x] 3000 EACCES（已用 55210 规避）
* [ ] npm deprecation/漏洞告警（待升级依赖）
* [ ] TMDB 元数据字段（poster/backdrop/genres/rating）当前为空
* [ ] 播放器/WebDAV 播放入口

---

## 10) 下一步（优先级 1-5）

1. 补齐 TMDB 元数据（poster/backdrop/genres/rating）来源与落库
2. 明确 linkId 与 share_fid/Token 的映射与持久化字段
3. 任务进度细化（progress/resultWebdavUrl）与 UI 展示
4. WebDAV 播放入口与错误恢复
5. 测试与可观测性

---

## 11) NEW CHAT STARTER（复制到新会话开头）

[NEW CHAT STARTER]

* Repo Root: `C:\Users\24228\Desktop\qtmx\Quark-Media-System`
* Branch: `master`
* Commit: `a0059a8537785413252b987b652ad10eeeb6c4ec`
* How to run: `cd frontend` -> `npm ci` / `npm run typecheck` / `npm run lint` / `npm run build` / `npm run dev:55210`
* Verified: typecheck/build/lint/dev ok (2026-01-07)
* API_BASE usage: set `NEXT_PUBLIC_API_BASE` to backend host; empty uses mock
* Backend confirmed: home, media/{tmdbId}, media/{tmdbId}/links/virtual, media/{tmdbId}/provision, tasks/{taskId}, share/parse, resources/search, resources/channels, tasks/*
* Backend gaps: TMDB metadata fields (poster/backdrop/genres/rating) still empty
* Next steps (1-5): enrich TMDB metadata, finalize linkId mapping, task progress UI
