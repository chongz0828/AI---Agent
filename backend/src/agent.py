"""
招聘智能主Agent - 纯交互式聊天版本
修复：补全缺失函数、修正名称错误，调整意图优先级
"""
import json
from typing import Dict, Any, Optional
from loguru import logger
from .tools.guard import content_guard
from .tools.parser import resume_parse_tool
from .tools.matcher import resume_job_match
from .tools.risk import resume_risk_check
from .tools.offer import hr_text_generator
# 导入token相关方法
from .llm import get_token_stats, reset_token_stats, check_token_threshold

# ===================== 全局缓存 =====================
GLOBAL_RESUME_CACHE: Optional[str] = None
GLOBAL_JD_CACHE: Optional[str] = None
_TEMP_JD: Optional[str] = None

# ===================== 意图关键词配置（调整优先级：解析 > 评估 > 文案 > 清空） =====================
INTENT_RULES = {
    "only_parse": {
        "keywords": ["解析简历", "读取简历", "提取简历信息", "简历结构化", "查看简历", "分析简历", "看下简历", "解析"]
    },
    "full_evaluate": {
        "keywords": ["人岗匹配", "岗位评估", "简历打分", "综合评估", "匹配JD", "风险审查", "用工风险", "候选人评估", "合不合适", "评估"]
    },
    "make_invite": {
        "keywords": ["面试邀约", "邀约面试", "发面试通知", "约面试"]
    },
    "make_reject": {
        "keywords": ["拒绝文案", "不予录用", "淘汰通知", "不合适", "拒绝通知"]
    },
    "clear_cache": {
        "keywords": ["清空缓存", "清除缓存", "清空", "重置", "重置会话"]
    },
}

# ===================== 意图识别（固定匹配优先级） =====================
def detect_user_intent(user_input: str) -> str:
    if not user_input or not user_input.strip():
        return "unknown"
    input_text = user_input.strip().lower()
    # 优先级顺序：解析 > 评估 > 邀约 > 拒绝 > 清空
    intent_order = ["only_parse", "full_evaluate", "make_invite", "make_reject", "clear_cache"]
    for intent_key in intent_order:
        rule = INTENT_RULES[intent_key]
        for kw in rule["keywords"]:
            if kw in input_text:
                logger.info(f"识别意图：{intent_key}，匹配关键词：{kw}")
                return intent_key
    return "unknown"

# ===================== 内容类型判断函数 =====================
def is_jd_content(text: str) -> bool:
    """判断文本是否为岗位JD"""
    jd_markers = ["岗位职责", "任职要求", "岗位JD", "职位描述", "招聘要求", "JD描述", "jd"]
    return any(m in text for m in jd_markers)

def is_resume_content(text: str) -> bool:
    """判断文本是否为简历"""
    resume_markers = [
        "【教育背景】", "【工作经历】", "【实习",
        "【项目", "【技能", "姓名：", "年龄：", "毕业院校",
    ]
    return any(m in text for m in resume_markers)

# ===================== 核心执行逻辑 =====================
def run_agent(user_input: str, job_jd: str = "") -> str:
    global GLOBAL_RESUME_CACHE, GLOBAL_JD_CACHE, _TEMP_JD
    raw_input = user_input.strip()

    # 1. 前置内容拦截
    guard_result = content_guard(raw_input)
    if not guard_result["allow_pass"]:
        return guard_result["reply"]

    # 2. 处理 JD 是/否 确认
    if raw_input in ["是", "是的", "好", "确认"] and _TEMP_JD is not None:
        GLOBAL_JD_CACHE = _TEMP_JD
        _TEMP_JD = None
        logger.info("【JD缓存】已成功保存岗位JD")
        return "✅ 岗位JD已缓存成功。你可以直接粘贴简历，系统自动完成解析+人岗匹配+风控评估。"

    if raw_input in ["否", "不是", "不要", "取消"] and _TEMP_JD is not None:
        _TEMP_JD = None
        logger.info("【JD缓存】已取消保存")
        return "❌ 已取消JD缓存，后续发送简历仅执行解析。"

    # 3. 识别意图
    intent = detect_user_intent(raw_input)

    # 4. 清空缓存
    if intent == "clear_cache":
        GLOBAL_RESUME_CACHE = None
        GLOBAL_JD_CACHE = None
        _TEMP_JD = None
        reset_token_stats()
        logger.info("【清空缓存】简历、JD、Token统计已全部重置")
        return "✅ 已清空所有缓存（简历、岗位JD、Token统计）。"

    # 5. 无指令：纯简历文本（自动判断）
    if intent == "unknown" and is_resume_content(raw_input) and len(raw_input) > 20:
        # 有缓存JD：解析 + 综合评估
        if GLOBAL_JD_CACHE is not None:
            logger.info("【纯简历+缓存JD，自动解析并综合评估】")
            parse_res = resume_parse_tool.invoke({
                "resume_text": raw_input,
                "output_for_user": False
            })
            if parse_res.startswith("简历解析失败"):
                return parse_res
            GLOBAL_RESUME_CACHE = parse_res
            resume_json = parse_res

            match_res = resume_job_match.invoke({"resume_json": resume_json, "job_jd": GLOBAL_JD_CACHE})
            if match_res.startswith("人岗匹配失败"):
                return match_res
            risk_res = resume_risk_check.invoke({"resume_json": resume_json})
            if risk_res.startswith("风控审查失败"):
                return risk_res

            return f"===== 人岗匹配评估报告 =====\n{match_res}\n\n===== 用工风控审查报告 =====\n{risk_res}"
        # 无缓存JD：仅解析简历
        else:
            logger.info("【纯简历，仅执行解析】")
            parse_res = resume_parse_tool.invoke({
                "resume_text": raw_input,
                "output_for_user": False
            })
            if parse_res.startswith("简历解析失败"):
                return parse_res
            GLOBAL_RESUME_CACHE = parse_res
            human_res = resume_parse_tool.invoke({
                "resume_text": raw_input,
                "output_for_user": True
            })
            return f"【简历结构化JSON】\n{parse_res}\n\n【简历可读信息】\n{human_res}"

    # 6. 无指令：识别岗位JD
    if intent == "unknown" and is_jd_content(raw_input) and len(raw_input) > 30:
        _TEMP_JD = raw_input
        tip = "检测到岗位JD内容。"
        if GLOBAL_JD_CACHE is not None:
            tip += " 当前已有缓存JD，是否更新覆盖？"
        else:
            tip += " 是否缓存该JD用于后续简历评估？"
        return tip + "\n请回复 是 / 否"

    # 7. 仅解析简历（带解析指令）
    if intent == "only_parse":
        # 剔除指令关键词，保留纯简历内容
        resume_text = raw_input
        for kw in INTENT_RULES["only_parse"]["keywords"]:
            resume_text = resume_text.replace(kw, "").strip()
        if len(resume_text) < 20:
            return "请粘贴完整简历文字内容。"
        parse_res = resume_parse_tool.invoke({
            "resume_text": resume_text,
            "output_for_user": False
        })
        if parse_res.startswith("简历解析失败"):
            return parse_res
        GLOBAL_RESUME_CACHE = parse_res
        human_res = resume_parse_tool.invoke({
            "resume_text": resume_text,
            "output_for_user": True
        })
        return f"【简历结构化JSON】\n{parse_res}\n\n【简历可读信息】\n{human_res}"

    # 8. 综合评估（带评估指令）
    if intent == "full_evaluate":
        # 剔除指令关键词，提取简历
        resume_text = raw_input
        for kw in INTENT_RULES["full_evaluate"]["keywords"]:
            resume_text = resume_text.replace(kw, "").strip()

        # 优先使用已缓存JD
        use_jd = job_jd if job_jd.strip() else GLOBAL_JD_CACHE
        if not use_jd:
            return "请先设置并缓存岗位JD，再执行评估。"

        # 本次附带新简历，先解析
        if len(resume_text) > 20:
            parse_res = resume_parse_tool.invoke({
                "resume_text": resume_text,
                "output_for_user": False
            })
            if parse_res.startswith("简历解析失败"):
                return parse_res
            GLOBAL_RESUME_CACHE = parse_res
            resume_json = parse_res
        # 复用已有简历缓存
        elif GLOBAL_RESUME_CACHE is not None:
            resume_json = GLOBAL_RESUME_CACHE
        else:
            return "暂无简历数据，请先发送简历完成解析。"

        match_res = resume_job_match.invoke({"resume_json": resume_json, "job_jd": use_jd})
        if match_res.startswith("人岗匹配失败"):
            return match_res
        risk_res = resume_risk_check.invoke({"resume_json": resume_json})
        if risk_res.startswith("风控审查失败"):
            return risk_res

        return f"===== 人岗匹配评估报告 =====\n{match_res}\n\n===== 用工风控审查报告 =====\n{risk_res}"

    # 9. 生成面试邀约文案
    if intent == "make_invite":
        if GLOBAL_RESUME_CACHE is None:
            return "请先解析简历，再生成邀约文案。"
        text_res = hr_text_generator.invoke({"resume_json": GLOBAL_RESUME_CACHE, "text_type": "面试邀约"})
        return f"【面试邀约文案】\n{text_res}"

    # 10. 生成拒绝文案
    if intent == "make_reject":
        if GLOBAL_RESUME_CACHE is None:
            return "请先解析简历，再生成拒绝文案。"
        text_res = hr_text_generator.invoke({"resume_json": GLOBAL_RESUME_CACHE, "text_type": "拒绝文案"})
        return f"【拒绝文案】\n{text_res}"

    # 未知指令兜底
    return "未识别指令。支持：简历解析、人岗匹配、风控、面试/拒绝文案、清空缓存。"

# ===================== 交互式聊天主入口 =====================
def start_chat():
    welcome = """
============================================
你好，我是 AI 招聘助手，一个专注于招聘初筛与评估场景的智能辅助工具。
我可以帮你完成以下工作：
📄 简历解析：快速提取候选人简历中的关键信息并结构化
🎯 人岗匹配打分：根据岗位 JD，对候选人进行多维度量化评估
⚠️ 风险筛查：识别频繁跳槽、职业断层、简历造假等潜在风险
📝 文案生成：自动生成面试邀约、拒绝通知等标准化沟通文案

我所有的分析都是辅助性质，最终决策权始终在 HR 手中。
温馨提示：为避免 PDF 读取超时，建议优先发送文字版简历，或上传非扫描版 PDF。
输入 quit 可退出程序
============================================
📍 提示：首次使用请先发送岗位JD，系统会引导你缓存JD，之后粘贴简历自动评估。
"""
    print(welcome)
    while True:
        user_input = input("\n请输入内容/指令：")
        user_input = user_input.strip()
        if user_input.lower() == "quit":
            print("AI招聘助手已退出，再见！")
            break
        result = run_agent(user_input, job_jd=GLOBAL_JD_CACHE or "")
        # Token 超限警告
        try:
            warnings = check_token_threshold()
            if warnings:
                result += "\n\n⚠️ " + "\n⚠️ ".join(warnings)
        except Exception:
            pass
        print("\n【助手回复】")
        print(result)
        print("-" * 80)

# 程序入口
if __name__ == "__main__":
    start_chat()