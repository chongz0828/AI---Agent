"""规则后处理引擎 — 对LLM解析结果做二次清洗

三大功能：
1. 标准化：时间格式统一、字段去重、联系方式掩码
2. 纠错：实习/全职自动区分、证书剔除、时间逻辑修正
3. 计算：在职时长、稳定性评估
"""
import re
import json
from typing import Any


def apply_rules(data: dict) -> dict:
    """入口：传入解析后的字典，返回清洗后的字典"""
    data = _fix_dates(data)
    data = _classify_work_type(data)
    data = _calculate_durations(data)
    data = _clean_skills(data)
    data = _standardize_education(data)
    data = _mask_private_info(data)
    data = _recalc_stability(data)
    return data


# ─── 1. 时间标准化 ───

def _normalize_date(text: str) -> str:
    """把各种日期格式转成 YYYY-MM，无法识别的原样返回"""
    if not text or text == "信息不明确":
        return text
    text = text.strip().replace(" ", "").replace("年", "-").replace("月", "").replace(".", "-").replace("/", "-").replace("至今", "至今")
    # 匹配 YYYY-MM 或 YYYY
    m = re.match(r"(\d{4})-?(\d{1,2})?$", text)
    if m:
        y, mo = m.group(1), m.group(2) or "01"
        return f"{y}-{int(mo):02d}"
    return text


def _fix_dates(data: dict) -> dict:
    """遍历所有时间字段，统一格式；修复结束早于开始的问题"""
    for exp in data.get("work_experience", []):
        exp["start"] = _normalize_date(exp.get("start", ""))
        exp["end"] = _normalize_date(exp.get("end", ""))
        # 如果结束早于开始，交换
        if exp["start"] != "至今" and exp["end"] != "至今" and exp["start"] > exp["end"]:
            exp["start"], exp["end"] = exp["end"], exp["start"]
    edu = data.get("education", {})
    if isinstance(edu, dict):
        edu["grad_year"] = _normalize_date(edu.get("grad_year", ""))
    return data


# ─── 2. 区分实习/全职 ───

_INTERN_KEYWORDS = ["实习", "intern", "实训", "见习"]


def _classify_work_type(data: dict) -> dict:
    """根据公司名/岗位名判断是否为实习"""
    for exp in data.get("work_experience", []):
        company = (exp.get("company", "") or "").lower()
        role = (exp.get("role", "") or "").lower()
        if any(kw in company or kw in role for kw in _INTERN_KEYWORDS):
            exp["type"] = "实习"
    return data


# ─── 3. 技能清理 ───

_CERT_KEYWORDS = [
    "cet", "英语四级", "英语六级", "四级", "六级", "tem", "pmp",
    "计算机二级", "计算机三级", "普通话", "驾驶证", "会计证",
    "教师资格", "acp", "cfa", "cpa", "软考",
]


def _clean_skills(data: dict) -> dict:
    """去掉证书类、重复的技能"""
    seen = set()
    clean = []
    for s in data.get("skills", []):
        s = s.strip()
        if not s or s == "信息不明确":
            continue
        low = s.lower()
        # 跳过证书关键词
        if any(kw in low for kw in _CERT_KEYWORDS):
            continue
        # 跳过纯数字（如 "2020"）
        if re.match(r"^\d+$", s):
            continue
        # 去重
        if s not in seen:
            seen.add(s)
            clean.append(s)
    data["skills"] = clean
    return data


# ─── 4. 学历标准化 ───

_DEGREE_MAP = {
    "硕士": "硕士", "硕士研究生": "硕士", "专硕": "硕士", "学硕": "硕士",
    "博士": "博士", "博士研究生": "博士",
    "本科": "本科", "学士": "本科", "大学本科": "本科",
    "大专": "大专", "专科": "大专", "大学专科": "大专",
    "高中": "高中", "中专": "中专",
}


def _standardize_education(data: dict) -> dict:
    edu = data.get("education", {})
    if isinstance(edu, dict):
        deg = edu.get("degree", "")
        if deg in _DEGREE_MAP:
            edu["degree"] = _DEGREE_MAP[deg]
    return data


# ─── 5. 隐私掩码 ───

def _mask_private_info(data: dict) -> dict:
    """对可能残留的姓名/手机/邮箱做掩码"""
    for exp in data.get("work_experience", []):
        for field in ["company", "role"]:
            val = exp.get(field, "")
            # 掩码手机号
            val = re.sub(r"1[3-9]\d{9}", lambda m: m.group()[:3] + "****" + m.group()[-4:], val)
            # 掩码邮箱
            val = re.sub(r"\b[\w.-]+@[\w.-]+\.\w+\b", lambda m: m.group()[:2] + "***@" + m.group().split("@")[1], val)
            exp[field] = val
    return data


# ─── 6. 在职时长与稳定性 ───

def _calculate_durations(data: dict) -> dict:
    """计算每段经历的月数"""
    for exp in data.get("work_experience", []):
        s, e = exp.get("start", ""), exp.get("end", "")
        months = 0
        if s and e and s != "信息不明确" and e != "信息不明确":
            try:
                sy, sm = int(s[:4]), int(s[5:7]) if len(s) > 4 else 1
                ey, em = int(e[:4]), int(e[5:7]) if len(e) > 4 else 1
                months = (ey - sy) * 12 + (em - sm)
            except:
                pass
        exp["duration_months"] = months
    return data


def _recalc_stability(data: dict) -> dict:
    """重新计算稳定性字段"""
    exps = [e for e in data.get("work_experience", []) if e.get("duration_months", 0) > 0]
    if not exps:
        return data
    total_months = sum(e["duration_months"] for e in exps)
    avg = total_months / len(exps)
    years = int(avg // 12)
    months = int(avg % 12)
    data["stability"] = {
        "avg_duration": f"{years}年{months}个月" if years else f"{months}个月",
        "has_gap": total_months < 6,  # 总时长<6个月视为有断层问题
    }
    return data
