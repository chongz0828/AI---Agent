"""
大模型客户端封装模块（修正版）
功能：统一封装 DeepSeek-v4-flash 调用、自动重试、Token 统计、费用估算
兼容性：支持字典消息列表 和 LangChain 消息对象列表
"""

import time
import tiktoken
from typing import Optional, Dict, List, Tuple, Union, Any
from openai import OpenAI, APIError, APIConnectionError, RateLimitError
from loguru import logger

from .config import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    LLM_MODEL,
    REQUEST_TIMEOUT,
    MAX_RETRIES,
    RETRY_DELAY,
    MAX_TOTAL_TOKENS_PER_CONVERSATION,
    MAX_TOKENS_PER_REQUEST,
    COST_PER_1K_INPUT,
    COST_PER_1K_OUTPUT,
    LLM_TEMPERATURE_PARSER,
    LLM_TEMPERATURE_MATCHER,
    LLM_TEMPERATURE_RISK,
    LLM_TEMPERATURE_OFFER,
    LLM_TEMPERATURE_INTENT,
)

# ===================== 全局常量 & 映射表 =====================
TEMP_MAP = {
    "parser": LLM_TEMPERATURE_PARSER,
    "matcher": LLM_TEMPERATURE_MATCHER,
    "risk": LLM_TEMPERATURE_RISK,
    "offer": LLM_TEMPERATURE_OFFER,
    "intent": LLM_TEMPERATURE_INTENT,
    "guard": 0.1,
}

# ===================== Token 累计统计 & 阈值 =====================
_TOTAL_INPUT_TOKENS: int = 0
_TOTAL_OUTPUT_TOKENS: int = 0
WARN_PER_ROUND: int = 5000   # 单轮警告阈值
WARN_TOTAL: int = 20000       # 累计警告阈值

# Token 编码（DeepSeek 兼容 cl100k_base）
TOKEN_ENCODER = tiktoken.get_encoding("cl100k_base")

# ===================== 辅助函数：兼容多种消息格式 =====================
def _get_message_content(msg: Any) -> str:
    """从消息对象（字典或 LangChain 消息）中提取 content"""
    if isinstance(msg, dict):
        return msg.get("content", "")
    # LangChain 消息对象（如 SystemMessage, HumanMessage）有 content 属性
    return getattr(msg, "content", "")

def _get_message_role(msg: Any) -> str:
    """从消息对象中提取 role (user/system/assistant)"""
    if isinstance(msg, dict):
        role = msg.get("role", "")
        return role
    # LangChain 消息对象的 type 属性映射
    msg_type = getattr(msg, "type", "")
    if msg_type == "human":
        return "user"
    elif msg_type == "system":
        return "system"
    elif msg_type == "ai":
        return "assistant"
    return msg_type

def count_tokens(text: str) -> int:
    """精确计算文本 token 数"""
    if not isinstance(text, str):
        return 0
    return len(TOKEN_ENCODER.encode(text))

def count_messages_tokens(messages: List[Any]) -> int:
    """
    精确估算消息列表的总 token 数（支持字典或 LangChain 消息对象）
    参考 OpenAI 官方计费规则
    """
    total = 0
    for msg in messages:
        total += count_tokens(_get_message_content(msg))
        total += count_tokens(_get_message_role(msg))
        total += 4  # 每条消息固定开销
    total += 2  # 回复起始预留
    return total

def check_token_limit(messages: List[Any]) -> None:
    """前置拦截：估算输入 token 是否超过配置上限"""
    estimated = count_messages_tokens(messages)
    if estimated > MAX_TOTAL_TOKENS_PER_CONVERSATION:
        raise ValueError(
            f"输入 token 预估 {estimated} 超过限制 {MAX_TOTAL_TOKENS_PER_CONVERSATION}，请求被拒绝"
        )

def llm_chat(
    messages: List[Any],
    scene: str = "parser",
    max_tokens: Optional[int] = None,
) -> Tuple[str, Dict]:
    """
    调用 LLM 进行对话
    Args:
        messages: 消息列表，支持字典或 LangChain 消息对象
        scene: 业务场景，用于选择温度
        max_tokens: 最大生成 token 数
    Returns:
        (reply_text, metrics)
        metrics 包含: success, input_tokens, output_tokens, total_tokens,
                     cost, duration_ms, error
    """
    global _TOTAL_INPUT_TOKENS, _TOTAL_OUTPUT_TOKENS
    start_time = time.perf_counter()
    metrics = {
        "success": False,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "cost": 0.0,
        "duration_ms": 0,
        "error": None,
    }

    # 1. 前置限流检查
    try:
        check_token_limit(messages)
    except ValueError as e:
        metrics["error"] = str(e)
        logger.error(metrics["error"])
        return "", metrics

    # 2. 获取温度
    temperature = TEMP_MAP.get(scene, 0.3)
    max_tok = max_tokens if max_tokens is not None else MAX_TOKENS_PER_REQUEST

    # 3. 将消息转换为 OpenAI API 需要的字典格式（如果还不是字典）
    openai_messages = []
    for msg in messages:
        if isinstance(msg, dict):
            openai_messages.append(msg)
        else:
            # LangChain 消息对象转换为字典
            role = _get_message_role(msg)
            content = _get_message_content(msg)
            openai_messages.append({"role": role, "content": content})

    # 4. 初始化客户端（懒加载，避免启动时失败）
    try:
        client = OpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
            timeout=REQUEST_TIMEOUT,
        )
    except Exception as e:
        metrics["error"] = f"客户端初始化失败: {str(e)}"
        logger.error(metrics["error"])
        return "", metrics

    # 5. 重试循环
    last_exception = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=LLM_MODEL,
                messages=openai_messages,
                temperature=temperature,
                max_tokens=max_tok,
            )
            reply = response.choices[0].message.content
            input_tokens = response.usage.prompt_tokens
            output_tokens = response.usage.completion_tokens
            total_tokens = response.usage.total_tokens
            cost = (input_tokens / 1000) * COST_PER_1K_INPUT + (output_tokens / 1000) * COST_PER_1K_OUTPUT

            _TOTAL_INPUT_TOKENS += input_tokens
            _TOTAL_OUTPUT_TOKENS += output_tokens

            metrics.update({
                "success": True,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
                "cost": cost,
                "duration_ms": (time.perf_counter() - start_time) * 1000,
            })

            logger.info(
                f"【调用成功】场景:{scene} | 耗时:{metrics['duration_ms']:.1f}ms | "
                f"in:{input_tokens} out:{output_tokens} | 成本:${cost:.8f}"
            )
            return reply, metrics

        except RateLimitError as e:
            last_exception = e
            logger.warning(f"限流重试 ({attempt+1}/{MAX_RETRIES+1}): {str(e)}")
            time.sleep(RETRY_DELAY * (2 ** attempt))
        except APIConnectionError as e:
            last_exception = e
            logger.warning(f"网络重试 ({attempt+1}/{MAX_RETRIES+1}): {str(e)}")
            time.sleep(RETRY_DELAY)
        except APIError as e:
            metrics["error"] = f"API错误: {str(e)}"
            logger.error(metrics["error"])
            return "", metrics
        except Exception as e:
            metrics["error"] = f"未知错误: {str(e)}"
            logger.error(metrics["error"], exc_info=True)
            return "", metrics

    # 重试耗尽
    metrics["error"] = f"达到最大重试次数({MAX_RETRIES+1})，最后错误: {str(last_exception)}"
    logger.error(metrics["error"])
    return "", metrics

# ===================== 便捷函数（按场景预设） =====================
def parser_chat(messages: List[Dict[str, str]]) -> Tuple[str, Dict]:
    return llm_chat(messages, scene="parser")

def matcher_chat(messages: List[Dict[str, str]]) -> Tuple[str, Dict]:
    return llm_chat(messages, scene="matcher")

def risk_chat(messages: List[Dict[str, str]]) -> Tuple[str, Dict]:
    return llm_chat(messages, scene="risk")

def offer_chat(messages: List[Dict[str, str]]) -> Tuple[str, Dict]:
    return llm_chat(messages, scene="offer")

# ===================== Token统计接口 =====================
def get_token_stats() -> dict:
    """返回当前Token累计使用量"""
    total = _TOTAL_INPUT_TOKENS + _TOTAL_OUTPUT_TOKENS
    return {
        "input_tokens": _TOTAL_INPUT_TOKENS,
        "output_tokens": _TOTAL_OUTPUT_TOKENS,
        "total_tokens": total,
    }


def reset_token_stats():
    """重置Token累计统计"""
    global _TOTAL_INPUT_TOKENS, _TOTAL_OUTPUT_TOKENS
    _TOTAL_INPUT_TOKENS = 0
    _TOTAL_OUTPUT_TOKENS = 0


def check_token_threshold() -> list:
    """
    检查Token是否超过阈值，返回警告信息列表
    单轮阈值 WARN_PER_ROUND: 单次调用超过此值告警
    累计阈值 WARN_TOTAL: 累计超过此值告警
    """
    warnings = []
    total = _TOTAL_INPUT_TOKENS + _TOTAL_OUTPUT_TOKENS
    if total >= WARN_TOTAL:
        warnings.append(
            f"\u26a0\ufe0f Token累计使用量 {total} 已达阈值 {WARN_TOTAL}，"
            f"建议清空上下文、新建会话以降低消耗。"
        )
    return warnings


# ===================== 模块自测 =====================
def test_llm():
    print("=" * 80)
    print("【LLM 模块自测】")
    test_messages = [{"role": "user", "content": "你好，请简单介绍一下你自己，一句话即可。"}]
    reply, metrics = llm_chat(test_messages, scene="parser")
    if metrics["success"]:
        print(f"✅ 调用成功")
        print(f"回复: {reply}")
        print(f"耗时: {metrics['duration_ms']:.1f}ms")
        print(f"输入Token: {metrics['input_tokens']}")
        print(f"输出Token: {metrics['output_tokens']}")
        print(f"成本: ${metrics['cost']:.8f}")
    else:
        print(f"❌ 调用失败: {metrics['error']}")
    print("=" * 80)

if __name__ == "__main__":
    test_llm()
