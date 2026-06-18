"""缓存模块 - Redis 双引擎（Redis + 内存兜底）
key: session:{session_id}:jd      岗位JD原文
key: session:{session_id}:resume  简历结构化JSON
key: session:{session_id}:tokens  Token统计
过期：7天，Redis不可用时自动降级为内存字典
"""
from typing import Optional
from loguru import logger
from .config import REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_PASSWORD, CACHE_EXPIRE_SECONDS

HAS_REDIS = False
try:
    import redis as redis_py
    HAS_REDIS = True
except ImportError:
    logger.warning("redis-py 未安装，使用内存缓存")


class CacheService:
    """缓存服务 - 懒加载模式：首次读写时再尝试连Redis"""

    def __init__(self):
        self._client: Optional[redis_py.Redis] = None  # type: ignore
        self._local: dict[str, str] = {}
        self._expire = CACHE_EXPIRE_SECONDS
        self._connected = False  # True=已连上, False=未尝试/已失败

    def _ensure_client(self):
        """首次调用时尝试连Redis，连不上就静默降级"""
        if self._connected or not HAS_REDIS:
            return
        try:
            c = redis_py.Redis(
                host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB,
                password=REDIS_PASSWORD or None,
                decode_responses=True,
                socket_connect_timeout=2,
            )
            c.ping()
            self._client = c
            self._connected = True
            logger.info(f"Redis {REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}")
        except Exception as e:
            self._connected = True  # 标记已尝试过，下次不再试
            self._client = None
            logger.warning(f"Redis 不可用 ({e})，使用内存缓存")

    def _key(self, sid: str, kt: str) -> str:
        return f"session:{sid}:{kt}"

    def get(self, sid: str, kt: str) -> Optional[str]:
        self._ensure_client()
        k = self._key(sid, kt)
        if self._client:
            try:
                return self._client.get(k)
            except:
                return self._local.get(k)
        return self._local.get(k)

    def set(self, sid: str, kt: str, v: str):
        self._ensure_client()
        k = self._key(sid, kt)
        if self._client:
            try:
                self._client.setex(k, self._expire, v)
                return
            except:
                pass
        self._local[k] = v

    def delete(self, sid: str, kt: Optional[str] = None):
        self._ensure_client()
        prefix = f"session:{sid}:"
        if kt:
            k = self._key(sid, kt)
            if self._client:
                try:
                    self._client.delete(k)
                    return
                except:
                    pass
            self._local.pop(k, None)
        else:
            if self._client:
                try:
                    for k in self._client.scan_iter(f"{prefix}*"):
                        self._client.delete(k)
                    return
                except:
                    pass
            self._local = {k: v for k, v in self._local.items() if not k.startswith(prefix)}


cache_service = CacheService()
get_cache = lambda: cache_service
