"""
人岗匹配评估工具 (P2)
接收结构化简历JSON + 岗位JD，按维度加权打分、生成匹配报告
适配LangChain Tool，对接上层Agent与简历解析节点
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

# 项目绝对导入
from backend.src.llm import llm_chat

# ===================== 常量配置 =====================
MATCHER_SCENE = "matcher"

# 你提供的标准人岗匹配Prompt（原样沿用+微调格式适配模板）
SYSTEM_TPL_TEXT = """# 角色与定位
你是【人岗匹配评估专家】，一名拥有5年HRBP经验的招聘评估顾问。你的任务是将候选人与岗位要求进行系统性比对，输出量化评分与综合研判。

# 核心工作目标
依据脱敏后的“候选人画像”与岗位JD，进行多维度权重打分，输出《人岗匹配研判报告》。

# 标准化工作流程
Step1：接收来自P1的结构化候选人画像和岗位JD。
Step2：将JD拆解为硬性门槛、软性能力、核心考核业务能力。
Step3：逐项比对，进行多维度打分（满分100）：
学历匹配度（10%）
经验年限匹配（20%）
核心技能重合度（30%）
项目含金量（20%）
稳定性风险（20%）
Step4：给出综合评级（S/A/B/C），并附上优势项、风险项与行动建议。

# 执行约束
打分必须基于可比对的事实，不得编造依据。
所有减分项必须注明具体原因。
不确定时，结论守低不守高，标记“待定”。

# 统一输出格式
严格按照以下固定格式输出，不要额外补充文字：
学历匹配 (10%)：XX 分｜加权得分：XX
经验年限 (20%)：XX 分｜加权得分：XX
核心技能 (30%)：XX 分｜加权得分：XX
项目含金量 (20%)：XX 分｜加权得分：XX
稳定性 (20%)：XX 分｜加权得分：XX
综合总分：XX 综合评级：S/A/B/C
优势项：[客观列明匹配亮点]
风险项：[写明扣分具体依据]
行动建议：[简洁可执行建议]"""

# 入参模板：拼接 结构化简历 + 岗位JD
HUMAN_TPL_TEXT = """
【结构化候选人简历画像】
{resume_json}

【岗位JD内容】
{job_jd}
"""

# 组装LangChain Prompt
system_prompt = SystemMessagePromptTemplate.from_template(SYSTEM_TPL_TEXT)
human_prompt = HumanMessagePromptTemplate.from_template(HUMAN_TPL_TEXT)
chat_prompt = ChatPromptTemplate.from_messages([system_prompt, human_prompt])

# ===================== 核心匹配评估函数 =====================
def match_evaluate(resume_json: str, job_jd: str) -> Dict[str, Any]:
    """
    人岗匹配核心逻辑
    :param resume_json: P1输出的结构化简历JSON字符串
    :param job_jd: 岗位JD原文
    :return: 评估报告 + 调用指标
    """
    # 基础非空校验
    if not resume_json or not resume_json.strip():
        logger.warning("人岗匹配失败：简历数据为空")
        return {"error": "简历结构化数据不能为空", "metrics": {}}
    if not job_jd or not job_jd.strip():
        logger.warning("人岗匹配失败：岗位JD为空")
        return {"error": "岗位JD内容不能为空", "metrics": {}}

    try:
        # 简单校验是否为合法JSON（前置拦截脏数据）
        json.loads(resume_json)
    except json.JSONDecodeError:
        logger.error("简历JSON格式非法，无法进行匹配")
        return {"error": "简历结构化数据格式异常", "metrics": {}}

    # 组装消息列表
    messages = chat_prompt.format_messages(
        resume_json=resume_json,
        job_jd=job_jd
    )

    # 调用统一LLM接口，使用matcher场景温度
    try:
        reply_text, metrics = llm_chat(messages, scene=MATCHER_SCENE)
    except Exception as e:
        logger.error(f"人岗匹配LLM调用异常：{str(e)}")
        return {"error": f"模型调用失败：{str(e)}", "metrics": {}}

    logger.info("人岗匹配评估完成")
    return {
        "report": reply_text.strip(),
        "metrics": metrics
    }

# ===================== LangChain 标准工具封装 =====================
@tool
def resume_job_match(resume_json: str, job_jd: str) -> str:
    """
    人岗匹配评估工具(P2)
    功能：根据结构化简历与岗位JD，多维度加权打分并生成评估报告
    调用时机：已完成简历解析、存在岗位JD，需要做候选人匹配评估时使用
    :param resume_json: 简历解析节点输出的标准JSON字符串
    :param job_jd: 待匹配的岗位JD全文
    :return: 格式化人岗匹配评估报告
    """
    result = match_evaluate(resume_json, job_jd)
    if "error" in result:
        return f"人岗匹配失败：{result['error']}"
    return result["report"]

# ===================== 模块自测 =====================
def test_matcher():
    """本地自测：模拟简历JSON + 测试JD"""
    print("=" * 80)
    print("【人岗匹配工具 P2 自测】")

    # 模拟P1输出的标准简历JSON（沿用之前测试简历）
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
  "skills": [
    "Python", "Golang", "Java", "Django", "Gin", "SpringBoot",
    "Redis", "Kafka", "MySQL", "Elasticsearch", "微服务架构",
    "容器化部署", "性能优化"
  ],
  "projects": [
    {
      "name": "电商订单中台重构",
      "role": "核心开发",
      "achievement": "重构后接口响应速度提升45%，订单处理峰值提升至10万/秒"
    },
    {
      "name": "用户画像分析系统",
      "role": "项目负责人",
      "achievement": "完成千万级用户数据建模，降低用户标签计算耗时60%"
    }
  ],
  "stability": {
    "avg_duration": "2年9个月",
    "has_gap": false
  }
}
    '''

    # 模拟岗位JD
    test_jd = """
    后端开发工程师
    岗位职责：
    1. 负责公司电商平台、用户系统后端开发与维护；
    2. 参与中间件、微服务架构设计与性能调优。
    任职要求：
    1. 本科及以上学历，计算机相关专业；
    2. 3年及以上后端开发经验；
    3. 熟练使用Python/Java、MySQL、Redis、Kafka；
    4. 有大型电商、大数据项目经验优先；
    5. 职业稳定，无频繁跳槽。
    """

    # 调用工具
    match_result = resume_job_match.invoke({
        "resume_json": test_resume_json,
        "job_jd": test_jd
    })

    print("📋 人岗匹配评估报告：")
    print(match_result)
    print("=" * 80)

if __name__ == "__main__":
    test_matcher()