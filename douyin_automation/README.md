# 抖音带货自动化系统

全流程无人值守的抖音带货运营自动化工具，覆盖从爆款商品发现到视频发布的完整链路。

## 核心流程

```
爬虫（Crawler）
  → 商品分析（Product_Analyzer）
  → 素材采集（Material_Collector）
  → 文案分析（Content_Analyzer）
  → 内容生成（Content_Generator）
  → 发布（Publisher）
```

## 项目结构

```
douyin_automation/
├── src/
│   └── douyin_automation/
│       ├── crawler/        # 爬虫模块
│       ├── analyzer/       # 商品分析器
│       ├── collector/      # 素材采集器
│       ├── content/        # 文案分析 & 内容生成
│       ├── publisher/      # 发布器
│       ├── scheduler/      # 调度器
│       ├── web/            # Web 控制台（FastAPI）
│       ├── models/         # 核心数据模型
│       └── db/             # 数据库连接与初始化
├── tests/                  # 测试目录
├── pyproject.toml
├── requirements.txt
└── README.md
```

## 环境要求

- Python 3.11+
- Redis（任务队列）
- SQLite（开发）/ PostgreSQL（生产）

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

或使用 pip 可编辑安装（推荐开发时使用）：

```bash
pip install -e ".[dev]"
```

### 2. 安装 Playwright 浏览器

```bash
playwright install chromium
```

### 3. 配置环境变量

复制 `.env.example` 并填写配置：

```bash
cp .env.example .env
```

主要配置项：

```
REDIS_URL=redis://localhost:6379/0
DATABASE_URL=sqlite:///./douyin_automation.db
OPENAI_API_KEY=your_api_key_here
```

### 4. 启动 Redis

```bash
docker run -d -p 6379:6379 redis:7-alpine
```

### 5. 启动 Celery Worker

```bash
celery -A douyin_automation.scheduler worker --loglevel=info
```

### 6. 启动 Web 控制台

```bash
uvicorn douyin_automation.web:app --reload --port 8000
```

访问 http://localhost:8000 查看控制台。

## 运行测试

```bash
# 运行所有测试
pytest

# 运行属性测试（Hypothesis）
pytest tests/ -v -k "property"
```

## 技术栈

| 组件 | 技术 |
|------|------|
| 后端框架 | FastAPI |
| 任务队列 | Celery + Redis |
| 数据库 | SQLAlchemy（SQLite/PostgreSQL） |
| 爬虫 | httpx + Playwright |
| 视频合成 | FFmpeg + MoviePy |
| 属性测试 | Hypothesis |
