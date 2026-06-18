"""风控审查工具 (P3) - 接收结构化简历JSON，多维度用工风险扫描"""
import json
from typing import Dict, Any
from loguru import logger
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from backend.src.llm import llm_chat

RISK_SCENE = "risk"

SYSTEM_TPL_TEXT = """扫描简历风险，按维度输出预警清单：
1. 简历造假风险：时间线矛盾、技能夸大、学历存疑
2. 稳定性风险：频繁跳槽、职业断层期
3. 合规风险：竞业限制嫌疑、法律纠纷迹象
4. 敏感信息风险

规则：无风险标注"未发现明显信号"，不给出正面评价。

输出格式：
风险预警清单（已脱敏）
风险等级：高/中/低
问题类型：[造假/稳定性/合规/敏感信息]
风险描述：[具体依据，无则填"未发现明显信号"]
建议核实方向：[追问方向，无则填"无需额外核实"]"""

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
    logger.info("简历风控审查完成")
    return {"risk_report": reply_text.strip(), "metrics": metrics}


@tool
def resume_risk_check(resume_json: str) -> str:
    """简历风控审查(P3)：对结构化简历做多维度用工风险扫描、风险分级并给出核实建议"""
    result = risk_audit(resume_json)
    if "error" in result:
        return f"风控审查失败：{result['error']}"
    return result["risk_report"]

