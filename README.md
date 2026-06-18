<<<<<<< HEAD
# AI---Agent
面向HR招聘场景的智能简历处理LangChain Agent
> 项目状态：**半成品可本地运行** | 仅CLI交互式控制台，持续迭代开发
> 技术栈：Python + LangChain + DeepSeek LLM

## ✨ 当前已实现功能（可直接运行）
1. 内容守卫拦截：自动过滤闲聊、无关提问，节约LLM Token消耗
2. 简历结构化解析：提取学历/实习/项目/技能/工作稳定性，输出可读报告+标准JSON
3. 人岗多维度加权评估：学历/经验/技能/项目/稳定性五维打分，自动评级S/A/B/C
4. 用工风控审查：识别跳槽、职业断层、信息造假等高/中风险
5. 文案生成：内置模板输出面试邀约、拒绝通知（零LLM调用）
6. JD缓存交互：发送JD可选择缓存，后续粘贴简历自动全流程评估
7. 缓存清理指令：一键清空简历/JD/Token统计缓存
8. Token用量监控：累计超限主动弹窗警告，防止高额API消耗

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

## 🚀 本地启动使用说明
### 1. 环境配置
复制 `.env.example` 新建根目录 `.env`，填入DeepSeek密钥：
DEEPSEEK_API_KEY=你的密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-v4-flash
MAX_TOTAL_TOKENS_PER_CONVERSATION=16000

### 2. 安装依赖
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

### 3. 启动程序
python main.py

支持交互指令：
粘贴岗位 JD → 回复是缓存，否放弃缓存
纯粘贴简历：已有缓存 JD 自动执行「解析 + 匹配 + 风控」
解析简历 + 简历文本：仅解析，不执行匹配评估
面试邀约 / 拒绝通知：自动生成 HR 标准文案
清空缓存：重置简历、JD、Token 全部统计数据
quit：退出控制台程序

# ⚠️ 当前版本已知缺陷
仅 CLI 控制台交互，无 Web 可视化前端页面
内存临时缓存，重启程序所有数据丢失，暂无 Redis 持久化存储
仅支持纯文本简历，暂不支持 PDF/Word 文件读取解析
意图识别仅依靠关键词匹配，无分层语义 Agent
未封装 HTTP 接口，无法前后端分离调用
无多用户会话隔离，全局单一缓存
缺少完整单元测试、日志本地持久化存储

# 📅 后续迭代 Roadmap
短期新增功能
PDF 简历文本提取模块（PyPDF2），支持本地 PDF 解析
Redis 持久缓存：会话、JD、简历解析结果永久存储
Token 超限提示优化，新增一键重置 Token 统计指令

中期架构升级
重构 LangChain 工具流程，迁移至 LangGraph 状态机工作流
FastAPI 封装后端 HTTP 接口，提供 POST 调用能力
开发简易 HTML 静态前端页面，对接后端接口
实现多会话隔离，支持多人同时独立使用

长期工程化完善
编写全套单元测试用例，完善 test 自测脚本
日志持久化写入本地文件，分级日志查看
配置热加载，修改参数无需重启项目
批量简历导入、批量自动评估功能
支持导出候选人评估报告为 PDF 文件

# ❓ 常见问题
Q：输入是/ 清空缓存被守卫拦截？
A：已更新 guard.py 关键词白名单，拉取最新代码重新运行即可。
Q：简历解析大量字段显示「信息不明确」？
A：粘贴完整规范简历原文，或调整 parser 内部提取 Prompt。
Q：API Token 消耗过快、扣费高？
A：不要一次性粘贴大量完整代码给模型，分单文件修改；定期执行清空缓存重置累计 Token。
Q：启动程序提示模块找不到？
A：必须使用python main.py启动，程序自动注入项目根目录路径。