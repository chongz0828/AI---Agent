"""简历解析工具 (P1) - 模型强制输出JSON"""
import json
from typing import Dict, Any
from loguru import logger
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from backend.src.llm import llm_chat
from .rules import apply_rules
from .resume_schema import ResumeSchema

PARSER_SCENE = "parser"
_PARSE_CACHE: dict = {"text": "", "json": "", "metrics": {}, "data": None}

SYSTEM_TPL_TEXT = """提取简历字段为JSON。规则：
- 严格依原文，禁止增减修改
- 无内容填"信息不明确"，数组留空，布尔默认false
- 脱敏姓名、手机号、邮箱
- 仅输出JSON，不含说明文字

JSON格式：
{{
  "education": {{"degree":"","school":"","major":"","grad_year":""}},
  "work_years": {{"total":"","internship_count":0}},
  "work_experience": [{{"company":"","role":"","start":"","end":"","type":"全职/实习/兼职"}}],
  "skills": [],
  "projects": [{{"name":"","role":"","achievement":""}}],
  "stability": {{"avg_duration":"","has_gap":false}}
}}"""

HUMAN_TPL_TEXT = "简历原文内容：\n{resume_text}"

system_prompt = SystemMessagePromptTemplate.from_template(SYSTEM_TPL_TEXT)
human_prompt = HumanMessagePromptTemplate.from_template(HUMAN_TPL_TEXT)
chat_prompt = ChatPromptTemplate.from_messages([system_prompt, human_prompt])


def format_resume_for_human(data: Dict[str, Any]) -> str:
    lines = []
    edu = data.get("education", {})
    degree = edu.get("degree", "")
    school = edu.get("school", "")
    major = edu.get("major", "")
    grad_year = edu.get("grad_year", "")
    lines.append(f"学历：{degree} | {school} | {major} | {grad_year}")
    wy = data.get("work_years", {})
    total_year = wy.get("total", "")
    intern_cnt = wy.get("internship_count", 0)
    lines.append(f"工作年限：{total_year}（含实习 {intern_cnt} 段）")
    work_exp = data.get("work_experience", [])
    if work_exp:
        lines.append("工作/实习经历：")
        for we in work_exp:
            c = we.get("company", "") or "信息不明确"
            r = we.get("role", "") or ""
            st = we.get("start", "") or ""
            ed = we.get("end", "") or ""
            tp = we.get("type", "") or ""
            period = f"{st}-{ed}" if st or ed else ""
            parts = [p for p in [f"{c} {r}", period, tp] if p]
            if parts:
                lines.append("   " + " | ".join(parts))
    else:
        lines.append("工作/实习经历：无")
    skills = data.get("skills", [])
    valid_skills = [s for s in skills if s and s != "信息不明确"]
    skill_text = "、".join(valid_skills) if valid_skills else "无"
    lines.append(f"核心技能：{skill_text}")
    projects = data.get("projects", [])
    valid_projects = []
    for p in projects:
        p_name = p.get("name", "")
        p_achievement = p.get("achievement", "")
        if p_name and p_name != "信息不明确" and p_achievement and p_achievement != "信息不明确":
            valid_projects.append(p)
    if valid_projects:
        lines.append("项目经验：")
        for p in valid_projects:
            p_name = p.get("name", "")
            p_role = p.get("role", "")
            p_achievement = p.get("achievement", "")
            proj_parts = [p_name, p_role, p_achievement]
            lines.append("   " + " | ".join(proj_parts))
    stb = data.get("stability", {})
    avg_dur = stb.get("avg_duration", "")
    has_gap = stb.get("has_gap", False)
    gap_text = "存在职业断层" if has_gap else "无明显断层"
    lines.append(f"稳定性：平均在职{avg_dur}，{gap_text}")
    return "\n".join(lines)


def parse_resume(resume_text: str, output_for_user: bool = False) -> Dict[str, Any]:
    if not resume_text or not resume_text.strip():
        logger.warning("简历解析失败：输入为空")
        return {"error": "简历文本不能为空", "metrics": {}}
    global _PARSE_CACHE
    if _PARSE_CACHE["text"] == resume_text and _PARSE_CACHE["json"]:
        logger.info("简历解析命中缓存，跳过LLM调用")
        if output_for_user and _PARSE_CACHE.get("data"):
            return {"report": format_resume_for_human(_PARSE_CACHE["data"]), "metrics": _PARSE_CACHE.get("metrics", {}), "json": _PARSE_CACHE["json"]}
        return {"report": _PARSE_CACHE["json"], "metrics": _PARSE_CACHE.get("metrics", {}), "json": _PARSE_CACHE["json"]}
    messages = chat_prompt.format_messages(resume_text=resume_text)
    try:
        reply_text, metrics = llm_chat(messages, scene=PARSER_SCENE)
    except Exception as e:
        logger.error(f"简历解析LLM异常：{str(e)}")
        return {"error": f"模型调用失败：{str(e)}", "metrics": {}}
    if not reply_text or not reply_text.strip():
        logger.warning("简历解析返回空内容")
        return {"error": "模型返回空内容", "metrics": metrics}
    cleaned = reply_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()
    _PARSE_CACHE["text"] = resume_text
    _PARSE_CACHE["json"] = cleaned
    _PARSE_CACHE["metrics"] = metrics
    try:
        data = json.loads(cleaned)
        data = apply_rules(data)
        _PARSE_CACHE["data"] = data
        cleaned = json.dumps(data, ensure_ascii=False)
    except json.JSONDecodeError:
        _PARSE_CACHE["data"] = None
    if output_for_user:
        data = _PARSE_CACHE.get("data")
        if data:
            return {"report": format_resume_for_human(data), "metrics": metrics, "json": cleaned}
    logger.info("简历解析完成")
    return {"report": cleaned, "metrics": metrics, "json": cleaned}


@tool
def resume_parse_tool(resume_text: str, output_for_user: bool = False) -> str:
    """简历解析工具(P1)：从非结构化简历文本提取标准化JSON结构"""
    result = parse_resume(resume_text, output_for_user=output_for_user)
    if "error" in result:
        return f"简历解析失败：{result['error']}"
    return result["report"]



