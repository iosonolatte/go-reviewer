# 围棋复盘 AI

结合 KataGo 围棋引擎与大语言模型的智能复盘工具，让专业围棋复盘触手可及。

## 功能特性

- 🎯 **KataGo 引擎分析** - 最强开源围棋引擎，精准计算胜率和目差
- 🧠 **AI 智能解说** - 大语言模型将专业分析转化为通俗易懂的讲解
- 📈 **胜率曲线可视化** - 直观展示棋局走势
- 🎨 **精美棋盘界面** - 传统木纹风格，支持落子导航
- 📝 **落子历史时间线** - 快速跳转回顾任意手数

## 技术栈

- **前端**: React 18 + TypeScript + Vite + Tailwind CSS
- **后端**: Python + Flask
- **引擎**: KataGo (GTP 协议)
- **AI 解说**: OpenAI API (兼容 OpenAI 协议的服务)
- **图表**: Recharts

## 快速开始

### 前置准备

1. **下载 KataGo**
   - 从 [KataGo GitHub Releases](https://github.com/lightvector/KataGo/releases) 下载最新版本
   - 下载对应的权重文件（推荐 b18c384nbt 系列）
   - 解压后获取 `katago` 可执行文件、配置文件和权重文件

2. **获取 OpenAI API Key**
   - 访问 [OpenAI Platform](https://platform.openai.com/api-keys) 获取 API Key
   - 或使用其他兼容 OpenAI 协议的服务（如 OneAPI 等）

### 安装依赖

#### 前端

```bash
cd go-reviewer
npm install
```

#### 后端

```bash
cd backend
pip install -r requirements.txt
```

### 启动服务

#### 1. 启动后端服务

```bash
cd backend
python app.py
```

后端服务将在 `http://localhost:5000` 启动

#### 2. 启动前端开发服务器

```bash
cd go-reviewer
npm run dev
```

前端服务将在 `http://localhost:5173` 启动

### 配置系统

1. 打开浏览器访问 `http://localhost:5173`
2. 点击导航栏的「设置」
3. 填写 KataGo 相关配置：
   - KataGo 可执行文件路径
   - 配置文件路径（gtp_example.cfg）
   - 模型权重文件路径
   - 分析时间（建议 5-10 秒）
4. 填写大语言模型配置：
   - API Key
   - 模型名称（如 gpt-4, gpt-3.5-turbo）
   - API Base URL（可选，使用第三方服务时需要）

### 开始复盘

1. 点击首页的上传区域，上传 `.sgf` 格式的棋谱文件
2. 进入复盘页面后，使用导航按钮浏览棋局
3. 点击「KataGo 分析」获取当前局面的胜率和推荐走法
4. 点击「生成 AI 解说」获取通俗易懂的讲解

## 项目结构

```
go-reviewer/
├── frontend/
│   ├── src/
│   │   ├── components/          # 组件
│   │   │   ├── GoBoard.tsx      # 棋盘组件
│   │   │   ├── Navbar.tsx       # 导航栏
│   │   │   ├── WinRateChart.tsx # 胜率图表
│   │   │   ├── CommentaryPanel.tsx # 解说面板
│   │   │   └── MoveTimeline.tsx # 落子时间线
│   │   ├── pages/               # 页面
│   │   │   ├── Home.tsx         # 首页
│   │   │   ├── Review.tsx       # 复盘页
│   │   │   └── Settings.tsx     # 设置页
│   │   ├── store/               # 状态管理
│   │   │   └── gameStore.ts
│   │   ├── types/               # 类型定义
│   │   └── App.tsx
│   ├── package.json
│   └── vite.config.ts
├── backend/
│   ├── app.py                   # Flask 应用入口
│   ├── katago_gtp.py            # KataGo GTP 通信
│   ├── sgf_parser.py            # SGF 棋谱解析
│   ├── llm_client.py            # LLM 客户端
│   └── requirements.txt
└── .trae/documents/             # 项目文档
```

## API 接口

### 上传棋谱
```
POST /api/upload
Content-Type: multipart/form-data
Response: { gameId, moves, boardSize, ... }
```

### 分析局面
```
GET /api/analyze/:gameId/:moveNumber
Response: { winRate, scoreLead, recommendedMoves }
```

### 生成解说
```
GET /api/commentary/stream/:gameId/:moveNumber
Content-Type: text/event-stream
```

### 配置接口
```
POST /api/config/katago   # 配置 KataGo
POST /api/config/llm      # 配置 LLM
```

## 常见问题

### Q: KataGo 分析失败怎么办？
A: 检查以下几点：
1. KataGo 路径配置是否正确
2. 权重文件路径是否正确
3. KataGo 是否有执行权限
4. 后端服务是否正常运行

### Q: AI 解说生成失败怎么办？
A: 检查以下几点：
1. API Key 是否正确
2. 网络连接是否正常
3. API 配额是否充足
4. 模型名称是否正确

### Q: 支持哪些棋谱格式？
A: 目前仅支持 `.sgf` 格式的棋谱文件。

## 开发说明

### 前端开发
- 使用 Zustand 进行状态管理
- 组件遵循单一职责原则
- 使用 Tailwind CSS 进行样式开发

### 后端开发
- Flask 提供 RESTful API
- GTP 协议与 KataGo 通信
- SSE (Server-Sent Events) 实现流式解说生成

## License

MIT
