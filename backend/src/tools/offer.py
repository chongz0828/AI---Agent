"""
文案生成工具 (P4)
功能：内置固定模板，生成面试邀约/简历未通过文案
特点：纯本地模板、不调用大模型，节省Token，输出固定无偏差
"""
import json
from typing import Dict, Any
from loguru import logger
from langchain_core.tools import tool

# ===================== 固定文案模板 =====================
TEMPLATE_MAP = {
    "面试邀约": "您好，您的简历已通过初步筛选，现正式邀请您参与面试，请留意后续沟通，祝您顺利！",
    "拒绝文案": "您好，感谢您投递本岗位。综合评估后暂无法安排面试，祝您未来求职一切顺利！"
}

# ===================== 核心文案函数 =====================
def get_fixed_text(resume_json: str, text_type: str) -> Dict[str, Any]:
    """
    读取固定模板返回文案
    :param resume_json: 简历JSON（仅做参数兼容）
    :param text_type: 文案类型：面试邀约 / 拒绝文案
    :return: 文案内容
    """
    # 基础非空校验
    if not resume_json or not resume_json.strip():
        logger.warning("文案生成：简历数据为空")
        return {"error": "简历结构化数据不能为空", "content": ""}
    
    text_type = text_type.strip()
    if text_type not in TEMPLATE_MAP:
        logger.warning(f"文案类型不合法：{text_type}")
        return {"error": "仅支持【面试邀约】和【拒绝文案】两种类型", "content": ""}

    # 校验JSON格式
    try:
        json.loads(resume_json)
    except json.JSONDecodeError:
        logger.error("简历JSON格式异常")
        return {"error": "简历结构化数据格式异常", "content": ""}

    logger.info(f"成功加载固定{text_type}模板")
    return {
        "error": "",
        "content": TEMPLATE_MAP[text_type]
    }

# ===================== LangChain 标准工具封装 =====================
@tool
def hr_text_generator(resume_json: str, text_type: str) -> str:
    """
    HR固定文案工具(P4)
    功能：输出预设面试邀约/拒绝文案，无大模型调用
    :param resume_json: 简历解析输出JSON（链路兼容）
    :param text_type: 文案类型，传入「面试邀约」或「拒绝文案」
    :return: 固定模板文案
    """
    result = get_fixed_text(resume_json, text_type)
    if result["error"]:
        return f"文案生成失败：{result['error']}"
    return result["content"]

# ===================== 自测 =====================
def test_offer():
    print("=" * 80)
    # 修复：补全JSON闭合符号、精简换行，保证合法格式
    test_resume_json = '''
{
  "education": {
    "degree": "硕士",
    "school": "北京大学",
    "major": "软件工程",
    "grad_year": "2019年7月"
  },
  "work_years": {
    "total": "5年7个月",
    "internship_count": 2
  },
  "skills": ["Python", "Java", "MySQL"],
  "projects": [],
  "stability": {"avg_duration": "2年9个月", "has_gap": false}
}
    '''

    print("【测试1：生成面试邀约文案】")
    res1 = hr_text_generator.invoke({
        "resume_json": test_resume_json,
        "text_type": "面试邀约"
    })
    print(res1)
    print("-" * 80)

    print("【测试2：生成拒绝文案】")
    res2 = hr_text_generator.invoke({
        "resume_json": test_resume_json,
        "text_type": "拒绝文案"
    })
    print(res2)
    print("=" * 80)

if __name__ == "__main__":
    test_offer()