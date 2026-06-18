"""Agent 注册中心 - 插件式意图处理器注册与分发"""
from typing import Callable, Optional
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class AgentContext:
    """Agent上下文，携带会话信息、用户输入与工具引用"""
    session_id: str = ""
    user_input: str = ""
    tools: dict = field(default_factory=dict)


class IntentHandlerRegistry:
    _registry: dict[str, dict] = {}

    @classmethod
    def register(cls, intent_name: str, description: str):
        def decorator(func: Callable[[AgentContext], str]):
            cls._registry[intent_name] = {"handler": func, "description": description}
            logger.info(f"【注册中心】已注册: {intent_name} -> {description}")
            return func
        return decorator

    @classmethod
    def dispatch(cls, intent: str, ctx: AgentContext) -> Optional[str]:
        entry = cls._registry.get(intent)
        if entry is None:
            return None
        logger.info(f"【注册中心】分发: {intent}")
        return entry["handler"](ctx)

    @classmethod
    def get_descriptions(cls) -> dict[str, str]:
        return {n: e["description"] for n, e in cls._registry.items()}

    @classmethod
    def has_intent(cls, intent: str) -> bool:
        return intent in cls._registry


IntentHandler = IntentHandlerRegistry
