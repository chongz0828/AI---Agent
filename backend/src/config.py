"""
AI-HR-assistant 全局配置中心
负责加载 .env 环境变量，统一管理 API Key、模型参数、成本控制等
"""

import os
from dotenv import load_dotenv  # 从 .env 文件加载环境变量
from pathlib import Path
import sys

# 找到项目根目录（假设当前文件在 backend/src/ 下，向上两级到根目录）
ROOT_DIR = Path(__file__).parent.parent.parent
ENV_PATH = ROOT_DIR / ".env"

# ========== 1. 加载 .env 文件 ==========
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)
else:
    print(f"⚠️ 警告: 未找到 .env 文件，请确保在项目根目录创建 {ENV_PATH}", file=sys.stderr)



# ========== 2. DeepSeek API 核心配置 ==========
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-v4-flash")

if not DEEPSEEK_API_KEY or not DEEPSEEK_API_KEY.strip():
        raise ValueError("LLM_API_KEY 未配置，请检查根目录 .env 文件中的 DeepSeek 密钥")


# ========== 3. 成本控制参数 ==========
COST_PER_1K_INPUT = float(os.getenv("COST_PER_1K_INPUT", 0.000014))
COST_PER_1K_OUTPUT = float(os.getenv("COST_PER_1K_OUTPUT", 0.000028))


# ========== 4. Token 限制 ==========
MAX_TOTAL_TOKENS_PER_CONVERSATION = int(
    os.getenv("MAX_TOTAL_TOKENS_PER_CONVERSATION", 16000)
)
MAX_TOKENS_PER_REQUEST = int(os.getenv("MAX_TOKENS_PER_REQUEST", 4000))


# ========== 5. 超时与重试 ==========
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", 60))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", 3))
RETRY_DELAY = float(os.getenv("RETRY_DELAY", 1.0))


# ========== 6. 模型温度（按模块差异化） ==========
LLM_TEMPERATURE_PARSER = float(os.getenv("LLM_TEMPERATURE_PARSER", 0.1))
LLM_TEMPERATURE_MATCHER = float(os.getenv("LLM_TEMPERATURE_MATCHER", 0.3))
LLM_TEMPERATURE_RISK = float(os.getenv("LLM_TEMPERATURE_RISK", 0.2))
LLM_TEMPERATURE_OFFER = float(os.getenv("LLM_TEMPERATURE_OFFER", 0.5))


# ========== 7. 启动时打印关键配置（确认加载正确） ==========
def test_config():
    """验证配置是否正确加载"""
    print("✅ 配置加载完成")
    print(f"   模型: {LLM_MODEL}")
    print(f"   输入成本: ${COST_PER_1K_INPUT}/1K tokens")
    print(f"   单轮最大 Token: {MAX_TOTAL_TOKENS_PER_CONVERSATION}")
    print(f"   请求超时: {REQUEST_TIMEOUT}s, 最大重试: {MAX_RETRIES}次")
if __name__ == "__main__":
    test_config()