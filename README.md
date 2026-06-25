# AI 招聘助手

基于 LangChain + DeepSeek 的简历自动评估系统，支持简历解析、人岗匹配、风险审查全流程闭环。提供 CLI 命令行和 FastAPI Web 接口双模式。

---

## 功能概览

| 模块 | 功能 |
|------|------|
| 内容守卫 | 业务关键词白名单 + 闲聊拦截 + LLM 语义兜底 |
| 简历解析 | 提取学历/实习/项目/技能/稳定性，输出结构化 JSON |
| 人岗匹配 | 五维加权打分（学历/经验/技能/项目/稳定性），自动评级 S/A/B/C |
| 风险审查 | 识别跳槽频繁、职业断层、信息造假等风险 |
| 文案生成 | 面试邀约/拒绝通知固定模板（零 LLM 调用） |
| LLM 意图识别 | 大模型语义判断 + 关键词兜底双引擎 |
| 规则后处理 | 时间标准化、技能清洗、隐私掩码、稳定性重算 |
| 评估报告结构化 | 匹配/风控报告 JSON 输出，可缓存复用 |
| 多轮对话记忆 | 自动保存对话历史，支持连续上下文 |
| 解析校验自愈 | Pydantic 校验 + 缺字段自动重试 |
| JD 管理独立化 | JD 与简历分离管理，不再自动识别 |
| 文件解析 | 支持 PDF / DOCX / TXT 格式上传 |
| FastAPI 接口 | RESTful API，支持聊天/上传/解析 |
| Web 前端 | Vanilla JS 单页应用，聊天+JD管理+文件上传 |

---

## 快速开始

### 环境配置
```bash
# 1. 复制环境变量模板
cp .env.example .env

# 2. 填入 DeepSeek API Key
# DEEPSEEK_API_KEY=your_key_here
# DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
# LLM_MODEL=deepseek-v4-flash
```

### 安装
```bash
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 启动 CLI 模式
```bash
python main.py
```

### 启动 Web 模式
```bash
.venv\Scripts\python -m backend.app 8000
```
浏览器打开 `http://127.0.0.1:8000`

---

## CLI 使用

| 指令 | 说明 |
|------|------|
| 粘贴简历文本 | 自动解析，有 JD 则自动全量评估 |
| 设置JD:<JD内容> | 设置岗位 JD，回复「是」确认 |
| 查看JD | 查看当前缓存的 JD |
| 清空JD | 清除 JD 缓存 |
| 面试邀约 / 拒绝通知 | 生成 HR 标准文案 |
| 清空缓存 | 二次确认后清除全部缓存 |
| quit | 退出程序 |

---

## API 文档

启动 Web 模式后访问 `http://127.0.0.1:8000/docs` 查看 Swagger 文档。

### 核心接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/chat | 聊天对话 |
| POST | /api/upload | 上传简历文件 (PDF/DOCX/TXT) |
| POST | /api/parse | 直接解析文件返回结构化 JSON |
| GET | /api/jd/{session_id} | 读取缓存的 JD |
| POST | /api/jd/save | 保存/更新 JD |
| POST | /api/jd/clear | 清空 JD |
| POST | /api/cache/clear | 清空全部缓存 |

### 接口示例

```bash
# 聊天
curl -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"input":"解析这份简历..."}'

# 上传文件
curl -X POST http://127.0.0.1:8000/api/upload \
  -F "file=@resume.pdf"
```

---

## 项目结构

```
.
├── main.py                 # CLI 入口
├── requirements.txt        # 依赖
├── .env.example            # 环境变量模板
├── frontend/
│   └── index.html          # Web 前端（自包含单页）
└── backend/
    ├── app.py              # FastAPI 应用
    └── src/
        ├── agent.py        # 核心编排
        ├── agent_intent.py # LLM 意图分类器
        ├── agent_registry.py # 插件式注册中心
        ├── cache.py        # Redis/内存双缓存
        ├── config.py       # 全局配置
        ├── llm.py          # DeepSeek 封装
        └── tools/
            ├── guard.py       # 内容守卫
            ├── parser.py      # 简历解析
            ├── matcher.py     # 人岗匹配
            ├── risk.py        # 风险审查
            ├── offer.py       # 文案生成
            ├── rules.py       # 规则后处理引擎
            ├── resume_schema.py # Pydantic 校验模型
            └── file_parser.py # 文件格式解析
```

---

## 已知限制

- 扫描件 PDF（图片式）暂不支持，需 OCR 前置处理
- 评估准确率受 LLM 输出稳定性影响，极端情况会回退纯文本
- 内存缓存模式下重启 API 会导致缓存丢失（建议安装 Redis）
- LLM 意图识别每次请求增加约 200-300 tokens 消耗

---

## 技术栈

- **语言框架**: Python 3.11, LangChain, FastAPI
- **大模型**: DeepSeek (OpenAI 兼容接口)
- **数据校验**: Pydantic v2
- **缓存**: Redis / 内存字典双引擎
- **前端**: Vanilla JS (Vue 3 运行时内嵌)
- **文件解析**: pdfplumber, python-docx
