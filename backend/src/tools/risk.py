"""
风控审查工具 (P3)
接收P1结构化简历画像，做多维度用工风险扫描、风险分级与核查建议
统一遵循项目Tool规范、日志、异常处理、LLM调用逻辑
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
RISK_SCENE = "risk"

# 风控审查 Prompt（完全使用你提供的规则+输出格式）
SYSTEM_TPL_TEXT = """# 角色与定位
你是【招聘风控审查员】，一名专注用工风险与合规的审查专家。你专门在候选人画像中寻找可能的风险信号，不关心候选人“有多好”，只关心“有什么问题”。

# 核心工作目标
对候选人画像进行风险扫描，输出风险预警清单与合规提示。

# 标准化工作流程
Step1：接收脱敏后的候选人画像。
Step2：按以下风险维度逐一扫描：
简历造假风险：时间线矛盾、技能夸大、学历存疑
稳定性风险：频繁跳槽、职业断层期
合规风险：竞业限制嫌疑、与前雇主法律纠纷迹象
敏感信息风险：候选人是否在简历中附带了不必要信息

# 执行约束
如果某项风险不存在，可标注“未发现明显信号”，但不得因此而给出任何正面评价。

# 统一输出格式
严格按照以下格式输出，禁止额外文字、评价：
风险预警清单（已脱敏）
风险等级：高 / 中 / 低
问题类型：[造假风险 / 稳定性风险 / 合规风险 / 敏感信息风险]
风险描述：[填写具体风险依据，无风险则填写：未发现明显信号]
建议核实方向：[面试中应重点追问的问题，无风险则填写：无需额外核实]"""

# 入参模板：接收结构化简历JSON
HUMAN_TPL_TEXT = """【脱敏候选人简历画像】
{resume_json}"""

# 组装Prompt
system_prompt = SystemMessagePromptTemplate.from_template(SYSTEM_TPL_TEXT)
human_prompt = HumanMessagePromptTemplate.from_template(HUMAN_TPL_TEXT)
chat_prompt = ChatPromptTemplate.from_messages([system_prompt, human_prompt])

# ===================== 核心风控函数 =====================
def risk_audit(resume_json: str) -> Dict[str, Any]:
    """
    简历风控审查核心逻辑
    :param resume_json: P1输出的结构化简历JSON字符串
    :return: 风控报告 + 调用指标
    """
    # 非空校验
    if not resume_json or not resume_json.strip():
        logger.warning("风控审查失败：简历数据为空")
        return {"error": "简历结构化数据不能为空", "metrics": {}}

    # 前置JSON格式校验
    try:
        json.loads(resume_json)
    except json.JSONDecodeError:
        logger.error("风控审查失败：简历JSON格式异常")
        return {"error": "简历结构化数据格式异常", "metrics": {}}

    # 组装消息列表
    messages = chat_prompt.format_messages(resume_json=resume_json)

    # 调用统一LLM接口
    try:
        reply_text, metrics = llm_chat(messages, scene=RISK_SCENE)
    except Exception as e:
        logger.error(f"风控审查LLM调用异常：{str(e)}")
        return {"error": f"模型调用失败：{str(e)}", "metrics": {}}

    logger.info("简历风控审查完成")
    return {
        "risk_report": reply_text.strip(),
        "metrics": metrics
    }

# ===================== LangChain 标准工具封装 =====================
@tool
def resume_risk_check(resume_json: str) -> str:
    """
    简历风控审查工具(P3)
    功能：对结构化简历做多维度用工风险扫描、风险分级并给出核实建议
    调用时机：完成人岗匹配后，需要做用工合规与风险审查时使用
    :param resume_json: 简历解析节点输出的标准JSON字符串
    :return: 标准化风控预警报告
    """
    result = risk_audit(resume_json)
    if "error" in result:
        return f"风控审查失败：{result['error']}"
    return result["risk_report"]

# ===================== 模块自测 =====================
def test_risk():
    """本地单独自测风控工具"""
    print("=" * 80)
    print("【风控审查工具 P3 自测】")

    # 沿用之前标准简历JSON（测试样本）
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

    # 调用工具
    risk_result = resume_risk_check.invoke({"resume_json": test_resume_json})
    print("🛡️ 风控审查报告：")
    print(risk_result)
    print("=" * 80)

if __name__ == "__main__":
    test_risk()