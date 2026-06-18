"""人岗匹配评估工具 (P2) - 接收结构化简历JSON + 岗位JD，加权打分输出报告"""
import json
from typing import Dict, Any
from loguru import logger
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from backend.src.llm import llm_chat

MATCHER_SCENE = "matcher"

SYSTEM_TPL_TEXT = """按以下维度对人岗匹配打分(每项满分100)：
学历匹配度 10% | 经验年限 20% | 核心技能重合度 30% | 项目含金量 20% | 稳定性 20%

打分基于事实，减分注明原因，不确定时守低标注"待定"。

输出格式(仅文字，不含JSON)：
学历匹配(10%)：XX分｜加权得分：XX
经验年限(20%)：XX分｜加权得分：XX
核心技能(30%)：XX分｜加权得分：XX
项目含金量(20%)：XX分｜加权得分：XX
稳定性(20%)：XX分｜加权得分：XX
综合总分：XX 综合评级：S/A/B/C
优势项：[匹配亮点]
风险项：[扣分依据]
行动建议：[可执行建议]"""

HUMAN_TPL_TEXT = """【结构化候选人简历画像】
{resume_json}

【岗位JD内容】
{job_jd}"""

system_prompt = SystemMessagePromptTemplate.from_template(SYSTEM_TPL_TEXT)
human_prompt = HumanMessagePromptTemplate.from_template(HUMAN_TPL_TEXT)
chat_prompt = ChatPromptTemplate.from_messages([system_prompt, human_prompt])


def match_evaluate(resume_json: str, job_jd: str) -> Dict[str, Any]:
    if not resume_json or not resume_json.strip():
        logger.warning("人岗匹配失败：简历数据为空")
        return {"error": "简历结构化数据不能为空", "metrics": {}}
    if not job_jd or not job_jd.strip():
        logger.warning("人岗匹配失败：岗位JD为空")
        return {"error": "岗位JD内容不能为空", "metrics": {}}
    try:
        json.loads(resume_json)
    except json.JSONDecodeError:
        logger.error("简历JSON格式非法")
        return {"error": "简历结构化数据格式异常", "metrics": {}}
    messages = chat_prompt.format_messages(resume_json=resume_json, job_jd=job_jd)
    try:
        reply_text, metrics = llm_chat(messages, scene=MATCHER_SCENE)
    except Exception as e:
        logger.error(f"人岗匹配LLM异常：{str(e)}")
        return {"error": f"模型调用失败：{str(e)}", "metrics": {}}
    logger.info("人岗匹配评估完成")
    return {"report": reply_text.strip(), "metrics": metrics}


@tool
def resume_job_match(resume_json: str, job_jd: str) -> str:
    """人岗匹配评估(P2)：根据结构化简历与岗位JD，多维度加权打分并生成评估报告"""
    result = match_evaluate(resume_json, job_jd)
    if "error" in result:
        return f"人岗匹配失败：{result['error']}"
    return result["report"]

