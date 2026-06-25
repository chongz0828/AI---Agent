"""招聘智能体Agent - 缓存版（Redis + 内存兜底）
架构：安全守卫 → LLM意图识别 → 注册中心分发（缓存复用长文本）
"""
import uuid, json
from typing import Optional
from loguru import logger
from .tools.guard import content_guard
from .tools.parser import resume_parse_tool
from .tools.matcher import resume_job_match
from .tools.risk import resume_risk_check
from .tools.offer import hr_text_generator
from .llm import check_token_threshold
from .agent_registry import IntentHandler, AgentContext
from .agent_intent import detect_intent, register_intent_descriptions
from .cache import cache_service

# 临时JD暂存（确认前存于此，确认后写入Redis）
_PENDING_JD: dict[str, str] = {}
_PENDING_CLEAR: set[str] = set()


def _is_resume_content(text: str) -> bool:
    return any(m in text for m in ["【教育背景】", "【工作经历】", "【实习", "【项目", "【技能", "姓名：", "年龄：", "毕业院校"])


def _strip_intent_keywords(text: str, intent_name: str) -> str:
    from .agent_intent import FALLBACK_INTENT_RULES as rules
    cleaned = text
    for kw in rules.get(intent_name, {}).get("keywords", []):
        cleaned = cleaned.replace(kw, "").strip()
    return cleaned


@IntentHandler.register("only_parse", "仅解析简历，提取结构化信息")
def handle_only_parse(ctx: AgentContext) -> str:
    resume_text = _strip_intent_keywords(ctx.user_input, "only_parse")
    if len(resume_text) < 20:
        return "请粘贴完整简历文字内容。"
    # 查缓存
    cached = cache_service.get(ctx.session_id, "resume")
    if cached and ctx.user_input in cached:
        logger.info("命中简历缓存，跳过LLM")
        return f"【简历结构化JSON】（缓存）\n{cached}"
    parse_res = resume_parse_tool.invoke({"resume_text": resume_text, "output_for_user": False})
    if parse_res.startswith("简历解析失败"):
        return parse_res
    cache_service.set(ctx.session_id, "resume", parse_res)
    human_res = resume_parse_tool.invoke({"resume_text": resume_text, "output_for_user": True})
    return f"【简历结构化JSON】\n{parse_res}\n\n【简历可读信息】\n{human_res}"


@IntentHandler.register("full_evaluate", "综合评估：人岗匹配打分 + 用工风控审查")
def handle_full_evaluate(ctx: AgentContext) -> str:
    resume_text = _strip_intent_keywords(ctx.user_input, "full_evaluate")
    # 读缓存JD
    jd = cache_service.get(ctx.session_id, "jd") or ""
    if not jd:
        return "请先设置并缓存岗位JD，再执行评估。"
    # 读缓存简历JSON / 现场解析
    resume_json = cache_service.get(ctx.session_id, "resume")
    if len(resume_text) > 20:
        parse_res = resume_parse_tool.invoke({"resume_text": resume_text, "output_for_user": False})
        if parse_res.startswith("简历解析失败"):
            return parse_res
        cache_service.set(ctx.session_id, "resume", parse_res)
        resume_json = parse_res
    elif not resume_json:
        return "暂无简历数据，请先发送简历完成解析。"
    match_res = resume_job_match.invoke({"resume_json": resume_json, "job_jd": jd})
    if match_res.startswith("人岗匹配失败"):
        return match_res
    risk_res = resume_risk_check.invoke({"resume_json": resume_json})
    if risk_res.startswith("风控审查失败"):
        return risk_res
    return f"===== 人岗匹配评估报告 =====\n{match_res}\n\n===== 用工风控审查报告 =====\n{risk_res}"


@IntentHandler.register("make_invite", "生成面试邀约文案")
def handle_make_invite(ctx: AgentContext) -> str:
    resume_json = cache_service.get(ctx.session_id, "resume")
    if not resume_json:
        return "请先解析简历，再生成邀约文案。"
    text_res = hr_text_generator.invoke({"resume_json": resume_json, "text_type": "面试邀约"})
    return f"【面试邀约文案】\n{text_res}"


@IntentHandler.register("make_reject", "生成拒绝/淘汰通知文案")
def handle_make_reject(ctx: AgentContext) -> str:
    resume_json = cache_service.get(ctx.session_id, "resume")
    if not resume_json:
        return "请先解析简历，再生成拒绝文案。"
    text_res = hr_text_generator.invoke({"resume_json": resume_json, "text_type": "拒绝文案"})
    return f"【拒绝文案】\n{text_res}"


@IntentHandler.register("clear_cache", "清空缓存和会话状态")
def handle_clear_cache(ctx: AgentContext) -> str:
    _PENDING_CLEAR.add(ctx.session_id)
    return "⚠️ 确定需要全部清除缓存？回复「是」确认 / 「否」取消"


def _init_registry():
    register_intent_descriptions(IntentHandler.get_descriptions())
    logger.info(f"【初始化】已同步 {len(IntentHandler.get_descriptions())} 个意图描述")


def run_agent(session_id: str, user_input: str) -> str:
    """入口：处理输入 + 保存对话历史"""
    raw_input = user_input.strip()
    result = _process_input(session_id, raw_input)

    # 保存到对话历史（最多保留20条=10轮）
    history = json.loads(cache_service.get(session_id, "history") or "[]")
    history.append({"role": "user", "content": raw_input})
    history.append({"role": "assistant", "content": result})
    cache_service.set(session_id, "history", json.dumps(history[-20:]))

    return result

def _process_input(session_id: str, user_input: str) -> str:
    raw_input = user_input.strip()
    # 1. 前置内容拦截
    guard_result = content_guard(raw_input)
    if not guard_result["allow_pass"]:
        return guard_result["reply"]
    # 2. JD 命令（CLI 用户设置JD）
    if raw_input.startswith("设置JD") or raw_input.startswith("JD:") or raw_input.startswith("jd:"):
        jd_text = raw_input.split(":", 1)[-1].strip() if ":" in raw_input else raw_input[4:].strip()
        if jd_text:
            _PENDING_JD[session_id] = jd_text
            return "已保存JD，回复「是」确认 / 「否」取消"
        return "格式：设置JD:<JD内容>"
    if raw_input in ["查看JD", "查看岗位JD"]:
        jd = cache_service.get(session_id, "jd") or "未设置JD"
        return f"当前缓存的JD：\n{jd}"

    # 3. 确认类指令处理（JD缓存 + 清空缓存）
    if raw_input in ["是", "是的", "好", "确认"]:
        if session_id in _PENDING_JD:
            cache_service.set(session_id, "jd", _PENDING_JD.pop(session_id))
            return "✅ JD已存入Redis缓存，重启程序数据不丢失"
        if session_id in _PENDING_CLEAR:
            _PENDING_CLEAR.discard(session_id)
            cache_service.delete(session_id)
            _PENDING_JD.pop(session_id, None)
            return "✅ 已清空所有缓存（简历、岗位JD、Token统计）"
    if raw_input in ["否", "不是", "不要", "取消"]:
        if session_id in _PENDING_JD:
            _PENDING_JD.pop(session_id)
            return "已取消JD缓存，后续发送简历仅执行解析。"
        if session_id in _PENDING_CLEAR:
            _PENDING_CLEAR.discard(session_id)
            return "已取消清除操作。"
    # 2.5 清除JD缓存
    if any(kw in raw_input for kw in ["清除JD", "清空JD", "删除JD"]):
        cache_service.delete(session_id, "jd")
        _PENDING_JD.pop(session_id, None)
        return "已清除JD缓存"
    # 3. 构建上下文
    ctx = AgentContext(session_id=session_id, user_input=raw_input,
        tools={"parser": resume_parse_tool, "matcher": resume_job_match,
               "risk": resume_risk_check, "offer": hr_text_generator})
    # 4. LLM意图识别
    intent = detect_intent(raw_input)
    # 5. 已知意图分发
    if intent != "unknown" and IntentHandler.has_intent(intent):
        result = IntentHandler.dispatch(intent, ctx)
        if result is not None:
            return result
    # 6. unknown -> 自动判断
    if _is_resume_content(raw_input) and len(raw_input) > 20:
        jd = cache_service.get(session_id, "jd")
        if not jd:
            jd = cache_service.get("default", "jd")
        if jd:
            logger.info("纯简历+缓存JD，自动解析并综合评估")
            parse_res = resume_parse_tool.invoke({"resume_text": raw_input, "output_for_user": False})
            if parse_res.startswith("简历解析失败"):
                return parse_res
            cache_service.set(session_id, "resume", parse_res)
            match_res = resume_job_match.invoke({"resume_json": parse_res, "job_jd": jd})
            if match_res.startswith("人岗匹配失败"):
                return match_res
            risk_res = resume_risk_check.invoke({"resume_json": parse_res})
            if risk_res.startswith("风控审查失败"):
                return risk_res
            return f"===== 人岗匹配评估报告 =====\n{match_res}\n\n===== 用工风控审查报告 =====\n{risk_res}"
        else:
            logger.info("纯简历，仅执行解析")
            parse_res = resume_parse_tool.invoke({"resume_text": raw_input, "output_for_user": False})
            if parse_res.startswith("简历解析失败"):
                return parse_res
            cache_service.set(session_id, "resume", parse_res)
            human_res = resume_parse_tool.invoke({"resume_text": raw_input, "output_for_user": True})
            return f"【简历结构化JSON】\n{parse_res}\n\n【简历可读信息】\n{human_res}"
    if _is_jd_content(raw_input) and len(raw_input) > 30:
        _PENDING_JD[session_id] = raw_input
        tip = "检测到岗位JD内容。"
        if cache_service.get(session_id, "jd"):
            tip += " 当前已有缓存JD，是否更新覆盖？"
        else:
            tip += " 是否缓存该JD用于后续简历评估？"
        return tip + "\n回复「是」保存 / 「否」取消"
    return "未识别指令。支持：简历解析、人岗匹配、风控、面试/拒绝文案、清空JD、清空缓存。"


def start_chat():
    _init_registry()
    session_id = uuid.uuid4().hex
    logger.info(f"会话ID: {session_id}")
    welcome = "============================================\n你好，我是 AI 招聘助手...\n============================================"
    print(welcome)
    while True:
        user_input = input("\n请输入内容/指令：").strip()
        if user_input.lower() == "quit":
            print("AI招聘助手已退出，再见")
            break
        result = run_agent(session_id, user_input)
        try:
            warnings = check_token_threshold()
            if warnings:
                result += "\n\n" + "\n".join(warnings)
        except Exception:
            pass
        print("\n【助手回复】\n" + result + "\n" + "-" * 80)


if __name__ == "__main__":
    start_chat()





