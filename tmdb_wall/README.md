# TMDB 海报墙（Python 版）

一个基于 **FastAPI + Jinja2** 的 TMDB 电影海报墙，重写自原始 React 项目 [`SKempin/reactjs-tmdb-app`](https://github.com/SKempin/reactjs-tmdb-app)，外观遵循 Netflix 风格规范。

## 快速开始
1. 创建虚拟环境并安装依赖：
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
   pip install -r requirements.txt
   ```
2. 配置环境变量（复制 `env.example` 为 `.env`，填入 TMDB API Key）：
   ```
   TMDB_API_KEY=你的TMDB密钥
   ```
3. 运行开发服务（推荐脚本，自动记录日志到 `logs/`）：
   ```bash
   # Windows
   start_server.bat

   # Linux/Mac
   ./start_server.sh
   ```
   或直接运行：
   ```bash
   uvicorn app.main:app --reload --port 7777
   ```
4. 打开浏览器访问：`http://localhost:7777`

## 测试
```bash
pytest
```

## Docker 部署
### 直接运行（镜像已在本地）
```bash
docker run -d --name tmdb-wall \
  -p 7777:7777 \
  -e TMDB_API_KEY=你的TMDB密钥 \
  tmdb-wall
```

### 本地构建镜像
```bash
docker build -t tmdb-wall .
docker run -d --name tmdb-wall \
  -p 7777:7777 \
  -e TMDB_API_KEY=你的TMDB密钥 \
  tmdb-wall
```

### docker-compose
```bash
docker compose up -d   # docker-compose.yml 已包含端口映射和环境变量占位
```

## 功能
- 首页：趋势、本周热播、口碑 Top、正在上映分区化网格
- 搜索：输入关键词后服务器端渲染结果列表
- 详情页：基础信息、类型、评分、年份
- **夸克搜索（新增）**：在详情页搜索夸克网盘资源，智能匹配和评分
- 设计：Netflix 黑底、2:3 海报、悬浮放大阴影、底部渐变文字区、响应式 12/8/4 列网格

## 目录
```
.
├─ app/
│  ├─ main.py        # FastAPI 入口与路由
│  ├─ config.py      # 配置与环境变量
│  └─ tmdb.py        # TMDB API 客户端封装
├─ templates/        # Jinja2 模板
├─ static/css/       # 样式表
├─ requirements.txt
└─ .env.example
```

## 依赖
- FastAPI, Uvicorn
- Jinja2
- httpx
- pydantic, python-dotenv

## 说明
- 默认语言使用 `zh-CN`，如需切换可调整 `app/tmdb.py` 中的 `DEFAULT_LANG`。
- 未设置 CDN 资源，样式均为本地 CSS，便于离线开发。
- **夸克搜索功能**：在电影/电视剧详情页可以搜索夸克网盘资源，支持智能匹配和评分。

## 夸克搜索功能

### 快速开始
```bash
# 启动服务（包含夸克搜索）
start_server.bat  # Windows
# 或
./start_server.sh  # Linux/Mac
```
日志会保存到 `logs/`，可用 `APP_HOST`/`APP_PORT` 覆盖监听地址和端口。

### 使用方法
1. 访问 `http://localhost:7777`
2. 浏览任意电影或电视剧详情页
3. 滚动到底部找到"夸克网盘资源"部分
4. 点击"搜索资源"按钮
5. 查看搜索结果和评分

详细使用说明请参考：[USAGE_GUIDE.md](USAGE_GUIDE.md)

### 集成状态
- ✅ 代码集成完成
- ✅ API 接口正常
- ✅ 前端功能完整
- ✅ 测试验证通过

详细集成报告请参考：[INTEGRATION_COMPLETE.md](INTEGRATION_COMPLETE.md)


