"""风控审查工具 (P3) - 接收结构化简历JSON，多维度用工风险扫描"""
import json
from typing import Dict, Any
from loguru import logger
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from backend.src.llm import llm_chat

RISK_SCENE = "risk"

SYSTEM_TPL_TEXT = """扫描简历风险并输出JSON。规则：无风险标注"未发现明显信号"，不给出正面评价。

输出JSON格式（仅输出JSON，不含说明文字）：
{{
  "level": "高/中/低",
  "items": [
    {{
      "type": "造假风险/稳定性风险/合规风险/敏感信息",
      "description": "具体依据",
      "suggestion": "核实方向"
    }}
  ]
}}"""

HUMAN_TPL_TEXT = """【脱敏候选人简历画像】
{resume_json}"""

system_prompt = SystemMessagePromptTemplate.from_template(SYSTEM_TPL_TEXT)
human_prompt = HumanMessagePromptTemplate.from_template(HUMAN_TPL_TEXT)
chat_prompt = ChatPromptTemplate.from_messages([system_prompt, human_prompt])


def risk_audit(resume_json: str) -> Dict[str, Any]:
    if not resume_json or not resume_json.strip():
        logger.warning("风控审查失败：简历数据为空")
        return {"error": "简历结构化数据不能为空", "metrics": {}}
    try:
        json.loads(resume_json)
    except json.JSONDecodeError:
        logger.error("风控审查失败：简历JSON格式异常")
        return {"error": "简历结构化数据格式异常", "metrics": {}}
    messages = chat_prompt.format_messages(resume_json=resume_json)
    try:
        reply_text, metrics = llm_chat(messages, scene=RISK_SCENE)
    except Exception as e:
        logger.error(f"风控审查LLM异常：{str(e)}")
        return {"error": f"模型调用失败：{str(e)}", "metrics": {}}
    raw = reply_text.strip()
    try:
        data = json.loads(raw)
        formatted = format_risk_report(data)
    except (json.JSONDecodeError, Exception):
        logger.warning("风控结果JSON解析失败，使用原始文本")
        data = {"raw_text": raw}
        formatted = raw
    logger.info("简历风控审查完成")
    return {"report": formatted, "raw": data, "metrics": metrics}




def format_risk_report(data: dict) -> str:
    """将结构化风险数据转为可读文本"""
    lines = [f"风险等级：{data.get('level', '未评估')}"]
    for item in data.get("items", []):
        lines.append(f"问题类型：{item.get('type', '未知')}")
        lines.append(f"风险描述：{item.get('description', '未发现明显信号')}")
        lines.append(f"建议核实：{item.get('suggestion', '无需额外核实')}")
        lines.append("---")
    if not data.get("items"):
        lines.append("未发现明显风险信号")
    return chr(10).join(lines)


@tool
def resume_risk_check(resume_json: str) -> str:
    """简历风控审查(P3)：对结构化简历做多维度用工风险扫描、风险分级并给出核实建议"""
    result = risk_audit(resume_json)
    if "error" in result:
        return f"风控审查失败：{result['error']}"
    return result["report"]


