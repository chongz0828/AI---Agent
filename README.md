# AI---Agent
面向HR招聘场景的智能简历处理LangChain Agent
> 项目状态：**可本地运行** | CLI + FastAPI 双模式，持续迭代开发
> 技术栈：Python + LangChain + DeepSeek LLM

## ✨ 当前已实现功能
1. 内容守卫拦截：业务关键词白名单(优先) + 闲聊词拦截 + LLM语义兜底
2. 简历结构化解析：提取学历/实习/项目/技能/工作稳定性，输出可读报告+标准JSON
3. 人岗多维度加权评估：学历/经验/技能/项目/稳定性五维打分，自动评级S/A/B/C
4. 用工风控审查：识别跳槽、职业断层、信息造假等风险
5. 文案生成：内置模板输出面试邀约、拒绝通知（零LLM调用）
6. LLM意图识别：大模型分析用户语义判断意图，关键词匹配兜底
7. 插件式注册中心：每个意图独立handler，新增功能只需注册一个函数
8. Redis/内存双缓存：JD和简历解析结果缓存复用，7天过期，Redis不可用时自动降级
9. 缓存指令增强：清空缓存需用户二次确认，防止误操作；支持单独清除JD缓存
10. 多轮对话记忆：自动保存对话历史到Redis，支持连续上下文
11. 评估报告结构化：匹配/风控报告JSON输出，原始数据存缓存可复用
12. 规则后处理引擎：时间标准化、实习分类、技能清洗、隐私掩码、稳定性重算
13. 解析器校验自愈：Pydantic校验LLM输出，缺字段自动重试补全
14. 文件解析：支持 PDF/DOCX/TXT 格式上传提取文字
15. FastAPI 接口：RESTful API 封装，支持聊天和文件上传
16. JD管理独立化：JD与简历分离管理，支持独立设置/清除/查看JD，不再自动识别JD
17. 极简前端：Vanilla JS 单页应用，聊天 + JD管理 + 文件上传三合一
18. Token用量监控：累计超限主动弹窗警告
## 📂 目录结构

agent 开发 - langchain/
├── main.py                # 启动入口
├── requirements.txt       # 依赖列表
├── .env.example           # 环境变量模板
├── backend/
│   ├── app.py             # 预留 FastAPI 入口
│   └── src/
│       ├── agent.py       # 核心编排：守卫 → LLM意图 → 注册中心分发
│       ├── agent_intent.py    # LLM意图分类器 + 关键词兜底
│       ├── agent_registry.py  # 插件式注册中心、AgentContext
│       ├── cache.py       # 缓存模块（Redis + 内存双引擎）
│       ├── config.py      # 全局配置
│       ├── llm.py         # DeepSeek LLM 封装、Token统计
│       ├── utils.py
│       └── tools/
│           ├── guard.py   # 内容守卫
│           ├── parser.py  # 简历解析
│           ├── matcher.py # 人岗匹配
│           ├── risk.py    # 风险审查
│           └── offer.py   # 文案生成
├── data/
├── frontend/
└── test/
    └── test_agent_quality.py

## 🚀 本地启动

### 1. 配置
复制 `.env.example` 为 `.env`，填入 DeepSeek 密钥：
DEEPSEEK_API_KEY=你的密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-v4-flash

### 2. 安装依赖
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

### 3. 启动
python main.py

### 支持指令
粘贴岗位 JD → 回复「是」缓存 /「否」放弃
纯粘贴简历 → 有缓存JD自动执行「解析+匹配+风控」
面试邀约 / 拒绝通知 → 生成 HR 标准文案
清空缓存 → 二次确认「是」后清除全部缓存
quit → 退出程序

## ⚠️ 已知缺陷
1. 仅 CLI 控制台，无 Web 前端
2. 仅支持纯文本简历，不支持 PDF/Word
3. 未封装 HTTP 接口
4. 缺少完整单元测试、日志持久化
5. LLM意图识别每次请求增加少量Token消耗（约200-300 tokens）

## 📅 Roadmap

短期
- PDF 简历文本提取（PyPDF2）
- Token 超限后自动触发缓存清理
- 完善缓存过期与会话隔离

中期
- LangGraph 状态机工作流
- FastAPI HTTP 接口
- Web 前端页面
- 多会话隔离

长期
- 单元测试覆盖
- 日志持久化
- 批量简历导入与评估
- 导出评估报告为 PDF

## ❓ 常见问题

Q：Redis 没装能运行吗？
A：能。系统自动检测，Redis 不可用时降级为内存缓存，功能完全一致。

Q：LLM意图识别太慢怎么办？
A：自动兜底到关键词匹配，不影响正常使用。

Q：启动提示模块找不到？
A：必须使用 python main.py 启动。

Q：文件上传支持什么格式？
A：PDF、DOCX、TXT。扫描件PDF暂不支持。

Q：FastAPI 怎么启动？
A：.venv\Scripts\python -m backend.app，默认端口8000。


