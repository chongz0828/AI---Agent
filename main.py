import sys
import os

# 自动把项目根目录加入模块路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

# 启动交互式聊天
from backend.src.agent import start_chat

if __name__ == "__main__":
    start_chat()