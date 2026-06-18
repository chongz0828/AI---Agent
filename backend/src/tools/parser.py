"""
简历解析工具 (P1)
最终版：模型强制输出JSON，代码区分「机器JSON / 人类可读文本」
LangChain PromptTemplate + 标准Tool
全链路结构化，适配下游人岗匹配Agent
"""
import json
from typing import Dict, Any

from loguru import logger
from langchain_core.tools import tool
from langchain_core.prompts import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate
)
# ----------------------------------------------------------------

from backend.src.llm import llm_chat

# ===================== 常量配置 =====================
PARSER_SCENE = "parser"

# ==== 解析结果缓存（避免重复LLM调用） ====
_PARSE_CACHE: dict = {"text": "", "json": "", "metrics": {}, "data": None}

SYSTEM_TPL_TEXT = """# 角色与定位
你是【简历解析引擎】，一名专业的信息提取与结构化处理专家。你的唯一任务是把非结构化的简历文本，转换为标准化JSON数据，只做信息提取，不做任何判断或评估。

# 强制一致性规则（必须严格遵守）
1. 严格依照简历原文提取内容，**禁止擅自删减、修改、新增任何技能、项目、工作信息**；
2. 所有字段必须完整输出，原文有内容就如实填写，无内容/无法识别统一填写："信息不明确"；
3. 项目、技能列表数量必须和原文一一对应，不得合并、丢失条目。

# 提取维度说明
1. education：最高学历、毕业院校/学校名称、专业、毕业时间。院校名称可能以"XX大学""XX学院"等形式出现，不限于"毕业院校"标签；全文无院校再填"信息不明确"
2. work_years：total=总工作时长（含全职+实习+兼职累计时长）；internship_count=实习总条数
3. skills：提取全部有效技能，以数组形式输出
4. projects：逐个提取项目名称、角色、成果，一条项目对应一条数组元素
5. work_experience：逐个提取工作/实习经历(公司名/单位名、岗位、起止时间)
6. stability：avg_duration=单段工作(含实习)平均时长；has_gap=是否存在职业断层(间隔>3月为true)
# 计算示例
# 示例1：工作经历为2020年7月-至今、2018年7月-2020年6月 → 总时长=6年（2020-2026）+2年=8年；段数=2；平均时长=4年
# 示例2：工作经历为2021年3月-2023年5月 → 总时长=2年2个月；段数=1；平均时长=2年2个月
# 示例3：两段工作间隔为2020年6月-2020年9月（间隔3个月）→ has_gap=false；间隔>3个月→has_gap=true

# 执行约束
1. 严格脱敏：隐去姓名、手机号、邮箱等所有隐私信息。
2. 信息模糊、缺失无法确认时，统一填写："信息不明确"。
3. 禁止主观评价、禁止自行补充猜测内容。
4. 数组无内容留空数组，布尔类型默认false。
5. 最终**只返回纯JSON字符串**，不要任何多余文字、解释、标题、换行说明。

# 固定JSON输出格式
{{
    "education": {{"degree": "", "school": "", "major": "", "grad_year": ""}},
    "work_years": {{"total": "", "internship_count": 0}},
    "work_experience": [{{"company": "", "role": "", "start": "", "end": "", "type": "全职/实习/兼职"}}],
    "skills": [],
    "projects": [{{"name": "", "role": "", "achievement": ""}}],
    "stability": {{"avg_duration": "", "has_gap": false}}
}}"""

HUMAN_TPL_TEXT = "简历原文内容：\n{resume_text}"


system_prompt = SystemMessagePromptTemplate.from_template(SYSTEM_TPL_TEXT)
human_prompt = HumanMessagePromptTemplate.from_template(HUMAN_TPL_TEXT)
chat_prompt = ChatPromptTemplate.from_messages([system_prompt, human_prompt])
# -------------------------------------------------------------------------

# ===================== 格式化函数：JSON → 人类可读文本（仅给用户展示） =====================
def format_resume_for_human(data: Dict[str, Any]) -> str:
    """将解析后的JSON数据转为友好文本，增加无效数据过滤，保证和原始JSON一致"""
    lines = []
    # 学历
    edu = data.get("education", {})
    degree = edu.get("degree", "")
    school = edu.get("school", "")
    major = edu.get("major", "")
    grad_year = edu.get("grad_year", "")
    lines.append(f"📚 学历：{degree} | {school} | {major} | {grad_year}")

    # 工作年限
    wy = data.get("work_years", {})
    total_year = wy.get("total", "")
    intern_cnt = wy.get("internship_count", 0)
    lines.append(f"💼 工作年限：{total_year}（含实习 {intern_cnt} 段）")

    # 工作/实习经历明细
    work_exp = data.get("work_experience", [])
    if work_exp:
        lines.append("👥 工作/实习经历：")
        for we in work_exp:
            c = we.get("company", "") or "信息不明确"
            r = we.get("role", "") or ""
            st = we.get("start", "") or ""
            ed = we.get("end", "") or ""
            tp = we.get("type", "") or ""
            period = f"{st}-{ed}" if st or ed else ""
            parts = [p for p in [f"{c} {r}", period, tp] if p]
            if parts:
                lines.append("   • " + " | ".join(parts))
    else:
        lines.append("👥 工作/实习经历：无")

    # 核心技能（过滤空值）
    skills = data.get("skills", [])
    valid_skills = [s for s in skills if s and s != "信息不明确"]
    skill_text = "、".join(valid_skills) if valid_skills else "无"
    lines.append(f"🔧 核心技能：{skill_text}")

    # 项目经验：过滤 名称/成果 为无效的项目
    projects = data.get("projects", [])
    valid_projects = []
    for p in projects:
        p_name = p.get("name", "")
        p_role = p.get("role", "")
        p_ach = p.get("achievement", "")
        # 名称有效才判定为真实项目
        if p_name and p_name != "信息不明确":
            valid_projects.append({
                "name": p_name,
                "role": p_role,
                "achievement": p_ach
            })

    if valid_projects:
        lines.append("📁 项目经验：")
        for item in valid_projects:
            lines.append(f"   • {item['name']}（{item['role']}）：{item['achievement']}")
    else:
        lines.append("📁 项目经验：无")

    # 稳定性
    stab = data.get("stability", {})
    avg_dur = stab.get("avg_duration", "")
    has_gap = "有" if stab.get("has_gap", False) else "无"
    lines.append(f"📊 稳定性：平均每段 {avg_dur} | 职业断层：{has_gap}")

    return "\n".join(lines)
# ===================== 核心解析函数 =====================
def parse_resume(resume_text: str, human_readable: bool = False) -> Dict[str, Any]:
    """
    解析简历
    :param resume_text: 原始简历文本
    :param human_readable: False=返回JSON(下游Agent用) / True=返回可读文本(用户查看)
    :return: 结果字典 + 调用指标
    """
    global _PARSE_CACHE
    raw_text = resume_text.strip()
    if not raw_text or len(raw_text) < 20:
        logger.warning("简历文本过短或为空，拒绝解析")
        return {"error": "简历内容不足，请提供更完整的简历信息", "metrics": {}}

    # ---------- 缓存命中：相同文本跳过LLM ----------
    if _PARSE_CACHE["text"] == raw_text and _PARSE_CACHE["data"] is not None:
        logger.info("简历解析命中缓存，跳过LLM调用")
        if human_readable:
            return {"text": format_resume_for_human(_PARSE_CACHE["data"]), "metrics": _PARSE_CACHE["metrics"]}
        else:
            return {"json": _PARSE_CACHE["json"], "metrics": _PARSE_CACHE["metrics"]}
    # --------------------------------------------

    # ---------- 使用 format_messages 直接获得消息列表 ----------
    messages = chat_prompt.format_messages(resume_text=raw_text)
    # ------------------------------------------------------------
    reply_text, metrics = llm_chat(messages, scene=PARSER_SCENE)

    if not metrics.get("success", False):
        err_msg = metrics.get("error", "未知模型错误")
        logger.error(f"LLM 调用失败: {err_msg}")
        return {"error": f"模型调用失败: {err_msg}", "metrics": metrics}

    # 容错截取JSON，兼容模型少量多余前后字符
    try:
        start_idx = reply_text.find('{')
        end_idx = reply_text.rfind('}')
        if start_idx == -1 or end_idx == -1:
            raise ValueError("未检测到合法JSON结构")

        json_str = reply_text[start_idx: end_idx + 1]
        data = json.loads(json_str)
        logger.info(
            f"简历解析成功 | 耗时 {metrics['duration_ms']:.1f}ms | 成本 ${metrics['cost']:.8f}"
        )

        # ---------- 写入缓存 ----------
        pretty_json = json.dumps(data, ensure_ascii=False, indent=2)
        _PARSE_CACHE["text"] = raw_text
        _PARSE_CACHE["json"] = pretty_json
        _PARSE_CACHE["data"] = data
        _PARSE_CACHE["metrics"] = metrics
        # -----------------------------

        if human_readable:
            # 转成人类可读文本
            text_content = format_resume_for_human(data)
            return {"text": text_content, "metrics": metrics}
        else:
            # 返回JSON，供给下游Agent
            return {"json": pretty_json, "metrics": metrics}

    except json.JSONDecodeError as e:
        logger.error(f"JSON解析失败: {str(e)} | 原始返回: {reply_text[:300]}")
        return {"error": "模型返回格式异常，JSON解析失败", "metrics": metrics}
    except ValueError as e:
        logger.error(f"内容截取失败: {str(e)} | 原始返回: {reply_text[:300]}")
        return {"error": str(e), "metrics": metrics}
    except Exception as e:
        logger.error(f"简历解析未知异常: {str(e)}", exc_info=True)
        return {"error": f"解析失败: {str(e)}", "metrics": metrics}
    

# ===================== LangChain 标准工具 =====================
@tool
def resume_parse_tool(resume_text: str, output_for_user: bool = False) -> str:
    """
    简历解析工具(P1)
    :param resume_text: 原始简历全文
    :param output_for_user:
        False(默认)：输出标准JSON，给人岗匹配等下游Agent使用（推荐）
        True：输出格式化可读文本，直接展示给终端用户
    """
    result = parse_resume(resume_text, human_readable=output_for_user)
    if "error" in result:
        return f"简历解析失败：{result['error']}"
    elif "text" in result:
        return result["text"]
    else:
        return result["json"]

# ===================== 自测 =====================
def test_parser():
    # 优化后的测试简历：字段结构化、信息明确、边界清晰
    sample_resume = """
    隐私信息：姓名（脱敏）、电话（脱敏）、邮箱（脱敏）

    【教育背景】
    最高学历：硕士
    毕业院校：北京大学
    所学专业：软件工程
    毕业时间：2019年7月

    【全职工作经历】
    第一段：2019年8月 - 2022年11月 | 北京XX科技有限公司 | 后端开发工程师
    工作内容：负责电商平台后端架构维护，参与订单系统迭代
    第二段：2022年12月 - 2025年4月 | 上海XX数据有限公司 | 高级后端工程师
    工作内容：主导用户画像系统开发，优化数据查询效率

    【实习经历】
    第一段：2018年7月 - 2018年9月 | 深圳XX互联网公司 | 开发实习生
    第二段：2019年3月 - 2019年6月 | 杭州XX科技公司 | 后端实习生

    【核心技能】
    编程语言：Python、Golang、Java
    技术框架：Django、Gin、SpringBoot
    中间件：Redis、Kafka、MySQL、Elasticsearch
    其他：微服务架构、容器化部署、性能优化

    【项目经验】
    项目1：电商订单中台重构
    担任角色：核心开发
    项目成果：重构后接口响应速度提升45%，订单处理峰值提升至10万/秒
    项目2：用户画像分析系统
    担任角色：项目负责人
    项目成果：完成千万级用户数据建模，降低用户标签计算耗时60%

    【补充说明】
    两段全职工作无职业断层，实习仅2段，无其他工作经历
    """

    print("=" * 80)
    print("【测试1：输出JSON（下游Agent专用）】")
    res_json = parse_resume(sample_resume, human_readable=False)
    if "error" in res_json:
        print(f"❌ {res_json['error']}")
    else:
        print("✅ JSON结果：\n", res_json["json"])
        print(f"耗时: {res_json['metrics']['duration_ms']:.1f}ms")

    print("\n" + "=" * 80)
    print("【测试2：输出可读文本（用户查看）】")
    res_text = parse_resume(sample_resume, human_readable=True)
    if "error" in res_text:
        print(f"❌ {res_text['error']}")
    else:
        print("✅ 可读文本：\n", res_text["text"])

    print("\n" + "=" * 80)
    print("【测试3：LangChain Tool 调用 - JSON模式】")
    tool_json = resume_parse_tool.invoke({"resume_text": sample_resume, "output_for_user": False})
    print(tool_json[:800] + "...")

if __name__ == "__main__":
    test_parser()