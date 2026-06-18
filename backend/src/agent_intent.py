"""
LLM 意图识别节点
功能：使用大模型分析用户输入，智能判断意图；LLM 不可用时自动回退到关键词匹配
"""
import json
from typing import Optional
from loguru import logger
from .llm import llm_chat

# ===================== 意图注册中心（运行时引用，避免循环导入） =====================
# agent_registry 会在初始化时调用 register_intent_descriptions() 推送描述进来
_INTENT_DESCRIPTIONS: dict[str, str] = {}

def register_intent_descriptions(descriptions: dict[str, str]):
    """由 agent_registry 在注册所有 handler 后调用，将意图描述推送给分类器"""
    global _INTENT_DESCRIPTIONS
    _INTENT_DESCRIPTIONS = descriptions

# ===================== LLM 意图分类 =====================
INTENT_CLASSIFICATION_SYSTEM_PROMPT = """你是 AI 招聘助手的意图识别模块。你的任务是分析用户输入，判断用户想做什么操作。

可选意图列表（含描述）：
{intent_descriptions}

判断规则：
1. 如果用户输入中包含简历正文（姓名、教育背景、工作经历等结构化信息），优先识别为具体意图而不是 "unknown"
2. 如果用户同时表达了意图词 + 粘贴了简历内容，识别为用户表达的意图
3. 如果用户只粘贴了简历/JD 内容且没有明确指令，识别为 "unknown"（由下游逻辑自动处理）
4. 如果用户输入与招聘业务完全无关，识别为 "unknown"

请严格按照以下 JSON 格式输出（只输出 JSON，不要有其他内容）：
{{"intent": "intent_name", "reason": "简短判断原因（中文，10字以内）"}}

用户输入：{user_input}"""


def classify_intent_with_llm(user_input: str) -> Optional[str]:
    """使用 LLM 判断用户意图，返回意图名称；失败时返回 None"""
    if not _INTENT_DESCRIPTIONS:
        logger.warning("【意图分类】意图描述尚未注册，跳过 LLM 分类")
        return None

    desc_text = "\n".join(
        f"- {name}: {desc}" for name, desc in _INTENT_DESCRIPTIONS.items()
    )
    prompt = INTENT_CLASSIFICATION_SYSTEM_PROMPT.format(
        intent_descriptions=desc_text,
        user_input=user_input,
    )
    messages = [{"role": "user", "content": prompt}]

    try:
        reply_text, metrics = llm_chat(messages=messages, scene="intent")
        if not metrics["success"] or not reply_text.strip():
            logger.warning(f"【意图分类】LLM 调用失败: {metrics.get('error')}")
            return None

        # 解析 JSON 响应
        cleaned = reply_text.strip()
        # 兼容可能包裹在 ```json ... ``` 中的情况
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
            cleaned = cleaned.strip()

        result = json.loads(cleaned)
        intent = result.get("intent", "").strip()
        reason = result.get("reason", "")
        logger.info(f"【意图分类】LLM 结果: intent={intent}, reason={reason}")

        # 验证意图是否在已知列表中
        if intent in _INTENT_DESCRIPTIONS:
            return intent
        logger.info(f"【意图分类】LLM 返回了未知意图: {intent}，将走 fallback 逻辑")
        return None

    except json.JSONDecodeError as e:
        logger.warning(f"【意图分类】JSON 解析失败: {e}, 原始响应: {reply_text}")
        return None
    except Exception as e:
        logger.error(f"【意图分类】异常: {e}")
        return None


# ===================== 关键词兜底 =====================
FALLBACK_INTENT_RULES = {
    "only_parse": {
        "keywords": ["解析简历", "读取简历", "提取简历信息", "简历结构化", "查看简历", "分析简历", "看下简历", "解析"]
    },
    "full_evaluate": {
        "keywords": ["人岗匹配", "岗位评估", "简历打分", "综合评估", "匹配JD", "风险评估", "用工风险", "候选人评估", "合不合适", "评估"]
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

_INTENT_ORDER = ["only_parse", "full_evaluate", "make_invite", "make_reject", "clear_cache"]


def classify_intent_with_keyword(user_input: str) -> str:
    """关键词兜底：当 LLM 不可用时使用"""
    if not user_input or not user_input.strip():
        return "unknown"
    input_text = user_input.strip().lower()
    for intent_key in _INTENT_ORDER:
        rule = FALLBACK_INTENT_RULES[intent_key]
        for kw in rule["keywords"]:
            if kw in input_text:
                logger.info(f"【关键词兜底】识别意图: {intent_key}，匹配关键词: {kw}")
                return intent_key
    return "unknown"


# ===================== 统一入口 =====================
def detect_intent(user_input: str) -> str:
    """
    统一意图识别入口
    策略：优先用 LLM → LLM 失败时用关键词兜底
    """
    # 空输入直接返回 unknown
    if not user_input or not user_input.strip():
        return "unknown"

    # 先尝试 LLM
    intent = classify_intent_with_llm(user_input)
    if intent is not None:
        return intent

    # LLM 失败，关键词兜底
    logger.info("【意图分类】LLM 分类失败或返回未知意图，使用关键词兜底")
    return classify_intent_with_keyword(user_input)
