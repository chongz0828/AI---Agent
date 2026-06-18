# AI招聘助手 - 简历智能评估Agent
> 项目状态：**半成品可运行版本** | 仅本地交互式CLI可用，持续迭代中
> 技术底座：Python + LangChain + DeepSeek LLM

## 📌 项目简介
面向HR招聘场景的智能简历处理Agent，实现简历文本结构化解析、人岗匹配打分、用工风险筛查、HR固定文案生成。
当前仅支持**纯文本简历+岗位JD**交互，无网页前端、无持久缓存、无PDF解析，后续规划完整工程化升级。

## ✨ 当前已实现功能（可直接运行）
1. 内容守卫拦截：自动过滤闲聊、无关提问，节约LLM Token消耗
2. 简历结构化解析：提取学历/实习/项目/技能/工作稳定性，输出可读报告+标准JSON
3. 人岗多维度加权评估：学历/经验/技能/项目/稳定性五维打分，自动评级S/A/B/C
4. 用工风控审查：识别跳槽、职业断层、信息造假等高/中风险
5. 文案生成：内置模板输出面试邀约、拒绝通知（零LLM调用）
6. JD缓存交互：发送JD可选择缓存，后续粘贴简历自动全流程评估
7. 缓存清理指令：一键清空简历/JD/Token统计缓存
8. Token用量监控：累计超限主动弹窗警告，防止高额消耗

## 📂 真实项目目录结构
agent 开发 - langchain/
├── main.py # 项目启动入口，交互式对话主程序
├── requirements.txt # 项目全部 Python 依赖（含后续扩展包）
├── .gitignore # Git 上传忽略规则，过滤虚拟环境、密钥、缓存文件
├── README.md # 项目说明文档
├── .env # 本地密钥配置文件（不上传 Git）
├── .env.example # 环境变量模板（无密钥，开源提交）
├── backend/
│ ├── init.py
│ ├── app.py # 预留 FastAPI 入口（待开发）
│ ├── src/
│ │ ├── init.py
│ │ ├── agent.py # Agent 核心调度、意图识别、全局内存缓存
│ │ ├── config.py # 全局参数、模型配置、Token 阈值、超时重试
│ │ ├── llm.py # DeepSeek LLM 统一封装、Token 统计、异常重试
│ │ ├── utils.py # 通用工具函数
│ │ └── tools/ # 拆分工具模块
│ │ ├── init.py
│ │ ├── guard.py # 内容守卫拦截工具
│ │ ├── parser.py # 简历解析工具
│ │ ├── matcher.py # 人岗匹配评估工具
│ │ ├── risk.py # 用工风险筛查工具
│ │ └── offer.py # HR 固定文案生成工具
├── data/ # 预留简历存储目录（空）
├── frontend/ # 预留前端静态页面目录（待开发）
│ └── .gitkeep
└── test/ # 自测脚本目录
├── .gitkeep
└── test_agent_quality.py # Agent 功能质量自测脚本

## 🛠 技术栈（现有）
- 运行环境：Python 3.10+
- Agent框架：LangChain Tool
- LLM服务商：DeepSeek（兼容OpenAI标准接口）
- 日志：loguru
- Token计算：tiktoken
- 环境管理：python-dotenv

## 🚀 快速本地启动
### 1. 前置准备
1. 新建项目根目录 `.env` 文件，填入密钥
DEEPSEEK_API_KEY=你的deepseek密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-v4-flash
# Token成本配置
COST_PER_1K_INPUT=0.000014
COST_PER_1K_OUTPUT=0.000028
# Token限制
MAX_TOTAL_TOKENS_PER_CONVERSATION=16000
MAX_TOKENS_PER_REQUEST=4000
# 模型温度
LLM_TEMPERATURE_PARSER=0.1
LLM_TEMPERATURE_MATCHER=0.3
LLM_TEMPERATURE_RISK=0.2
LLM_TEMPERATURE_OFFER=0.5
# 超时重试
REQUEST_TIMEOUT=60
MAX_RETRIES=3
RETRY_DELAY=1.0

2. 安装依赖
powershell
# 创建虚拟环境
python -m venv .venv
# Windows激活
.venv\Scripts\Activate.ps1
# 安装全部依赖
pip install -r requirements.txt

3. 启动程序
python main.py
启动后自动打印欢迎话术，支持指令：
直接粘贴岗位 JD → 回复是缓存，否放弃
纯粘贴简历：已有缓存 JD 自动「解析 + 匹配 + 风控」
解析简历 + 简历文本：仅解析不评估
面试邀约 / 拒绝通知：生成对应文案
清空缓存：重置简历、JD、Token 统计
quit：退出程序

⚠️ 当前版本缺陷
仅 CLI 控制台交互，无 Web 前端页面
内存临时缓存，重启程序全部丢失，无 Redis 持久化
仅支持文字简历，不支持 PDF/Word 文件上传读取
意图识别仅关键词匹配，无语义意图 Agent
无接口服务，无法前后端分离调用
无单元测试、批量自测脚本、日志持久化
无用户会话隔离，全局单缓存

📅 后续迭代 Roadmap
短期新增功能
PDF 简历文本提取工具（PyPDF2），支持上传 PDF 解析
Redis 持久缓存：会话、JD、解析结果长期存储
Token 超限自动提示优化，新增手动重置统计

中期架构升级
重构 Agent 为 LangGraph 工作流，拆分状态节点、增加分支路由
FastAPI 接口封装，提供 POST HTTP 接口
简易静态前端页面（HTML/CSS/JS），对接后端接口
多会话隔离，支持多用户同时使用

长期工程化
完整单元测试用例
日志本地文件持久化
配置热加载、参数可视化调整
批量简历批量评估功能
导出评估报告 PDF

❓ 常见问题
Q：发送是/清空缓存被守卫拦截？
A：已更新 guard 白名单，重新拉取代码运行即可。
Q：解析简历大量 “信息不明确”？
A：优化简历原文完整度，或调整 parser 解析 Prompt。
Q：Token 消耗过高？
A：避免一次性粘贴全项目代码给模型，分单文件修改；及时清空缓存重置统计。
Q：启动报模块找不到？
A：必须用python main.py启动，自动注入项目根目录路径。