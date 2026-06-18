"""内容守卫节点 - 无关内容拦截器
策略：业务关键词白名单(优先) → 闲聊关键词拦截 → LLM语义兜底
LLM不可用时自动放行（不阻塞业务）
"""
from typing import Dict, Optional
from loguru import logger
from backend.src.llm import llm_chat

BUSINESS_KEYWORDS = {"简历", "面试", "求职", "岗位", "招聘", "薪资", "入职", "离职",
    "候选人", "测评", "评估", "邀约", "拒绝", "履历",
    "清空缓存", "清除缓存", "清空", "重置", "重置会话",
    "是", "是的", "好", "确认", "否", "不是", "不要", "取消",
    "存岗位JD", "岗位JD", "JD", "岗位职责", "任职要求", "职位描述",
    "教育背景", "工作经历", "毕业院校", "专业技能"}

IGNORE_KEYWORDS = {"天气", "聊天", "游戏", "美食", "电影", "八卦", "新闻", "搞笑",
    "唱歌", "旅游", "购物", "星座", "解梦", "吐槽", "闲聊", "吃饭", "睡觉"}

NO_REPLY_MSG = "您好，我仅负责简历评估、面试相关业务咨询，暂不解答其他问题哦。"
GUARD_PROMPT = "判断输入是否属于HR招聘业务。属于输出yes，否则no。输入：{user_content}"


def keyword_check(user_text: str) -> Optional[bool]:
    if not user_text or not user_text.strip():
        return False
    text = user_text.strip().lower()
    for word in BUSINESS_KEYWORDS:
        if word in text:
            return True
    for word in IGNORE_KEYWORDS:
        if word in text:
            return False
    if len(text) >= 120:
        return False
    return None


def content_guard(user_input: str) -> Dict[str, any]:
    user_input = user_input.strip()
    check_result = keyword_check(user_input)
    if check_result is True:
        return {"allow_pass": True, "reply": ""}
    if check_result is False:
        return {"allow_pass": False, "reply": NO_REPLY_MSG}
    logger.info("守卫进入LLM兜底")
    try:
        reply_text, _ = llm_chat(messages=[
            {"role": "user", "content": GUARD_PROMPT.format(user_content=user_input[:200])}
        ], scene="guard")
        if reply_text.strip().lower() == "yes":
            return {"allow_pass": True, "reply": ""}
        return {"allow_pass": False, "reply": NO_REPLY_MSG}
    except Exception as e:
        logger.info("守卫LLM不可用，放行：" + str(e)[:50])
        return {"allow_pass": True, "reply": ""}
