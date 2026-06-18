"""
内容守卫节点 - 无关内容拦截器
功能：前置校验用户输入，过滤闲聊、无关提问、违规内容
逻辑：关键词极速拦截(优先) → LLM语义判断(兜底)
无关内容直接返回固定话术，不调用模型，节约Token；业务内容正常放行
"""
from typing import Dict, Optional
from loguru import logger
# 导入模型调用能力
from backend.src.llm import llm_chat

# ===================== 1. 规则配置（增强白名单） =====================
# 业务关键词：扩充缓存、确认类指令，彻底解决 是/否/清空缓存 被拦截
BUSINESS_KEYWORDS = {
    "简历", "面试", "求职", "岗位", "招聘", "薪资", "入职", "离职",
    "候选人", "测评", "评估", "邀约", "拒绝", "履历",
    # 缓存/会话运维指令
    "清空缓存", "清除缓存", "清空", "重置", "重置会话",
    # JD确认指令
    "是", "是的", "好", "确认", "否", "不是", "不要", "取消",
    # JD相关
    "存岗位JD", "岗位JD", "JD"
}

# 无关/闲聊关键词
IGNORE_KEYWORDS = {
    "天气", "聊天", "游戏", "美食", "电影", "八卦", "新闻", "搞笑",
    "唱歌", "旅游", "购物", "星座", "解梦", "吐槽", "闲聊"
}

# 无关内容统一回复话术
NO_REPLY_MSG = "您好，我仅负责简历评估、面试相关业务咨询，暂不解答其他问题哦。"

# 守卫专用提示词（优化语义判断范围）
GUARD_PROMPT = """
请判断用户输入是否属于【简历、招聘、面试、岗位JD、缓存操作、是/否确认】相关业务。
仅输出结果，规则如下：
1. 业务相关 → 输出：yes
2. 无关内容/闲聊/系统命令 → 输出：no
用户提问：{user_content}
"""

# ===================== 2. 关键词基础校验 =====================
def keyword_check(user_text: str) -> Optional[bool]:
    """
    :return: True(业务相关) / False(无关内容) / None(关键词无法判断)
    """
    if not user_text or not user_text.strip():
        return False
    text = user_text.strip().lower()

    # 优先拦截闲聊
    for word in IGNORE_KEYWORDS:
        if word in text:
            return False

    # 业务白名单（含确认、缓存、JD指令）
    for word in BUSINESS_KEYWORDS:
        if word in text:
            return True

    # 关键词无法区分，进入LLM兜底
    return None

# ===================== 3. 核心入口函数 =====================
def content_guard(user_input: str) -> Dict[str, any]:
    user_input = user_input.strip()
    logger.info(f"【守卫节点】收到用户输入：{user_input}")

    # 第一步：关键词极速校验
    check_result = keyword_check(user_input)
    if check_result is False:
        logger.info("【守卫节点】识别为无关内容，拦截请求")
        return {
            "allow_pass": False,
            "reply": NO_REPLY_MSG
        }
    if check_result is True:
        logger.info("【守卫节点】识别为业务内容，正常放行")
        return {
            "allow_pass": True,
            "reply": ""
        }

    # 关键词无法区分 → LLM兜底
    logger.info("【守卫节点】关键词无法识别，启用模型语义判断")
    prompt = GUARD_PROMPT.format(user_content=user_input)
    messages = [{"role": "user", "content": prompt}]
    try:
        reply_text, _ = llm_chat(messages=messages, scene="guard")
        model_resp = reply_text.strip().lower()
        if model_resp == "yes":
            logger.info("【守卫节点】模型判定为业务内容，放行")
            return {"allow_pass": True, "reply": ""}
        else:
            logger.info("【守卫节点】模型判定为无关内容，拦截")
            return {"allow_pass": False, "reply": NO_REPLY_MSG}
    except Exception as e:
        logger.error(f"【守卫节点】模型判断异常：{str(e)}")
        return {"allow_pass": False, "reply": "服务异常，暂无法处理您的请求"}

# ===================== 4. 自测函数 =====================
def test_guard():
    print("=" * 80)
    print("【守卫节点自测】")
    test_list = [
        "今天天气怎么样",
        "解析简历",
        "是",
        "否",
        "清空缓存",
        "重置会话",
        "存岗位JD"
    ]
    for txt in test_list:
        res = content_guard(txt)
        print(f"输入：{txt} | 放行：{res['allow_pass']} | 回复：{res['reply']}")
    print("=" * 80)

if __name__ == "__main__":
    test_guard()