"""简历校验模型 - 定义LLM输出必须包含的字段和格式"""
from pydantic import BaseModel, Field

class Education(BaseModel):
    degree: str = Field(default="信息不明确")
    school: str = Field(default="信息不明确")
    major: str = Field(default="信息不明确")
    grad_year: str = Field(default="信息不明确")

class WorkExperience(BaseModel):
    company: str = Field(default="信息不明确")
    role: str = Field(default="信息不明确")
    start: str = Field(default="信息不明确")
    end: str = Field(default="信息不明确")
    type: str = Field(default="全职")

class Project(BaseModel):
    name: str = Field(default="信息不明确")
    role: str = Field(default="信息不明确")
    achievement: str = Field(default="信息不明确")

class WorkYears(BaseModel):
    total: str = Field(default="信息不明确")
    internship_count: int = Field(default=0)

class Stability(BaseModel):
    avg_duration: str = Field(default="信息不明确")
    has_gap: bool = Field(default=False)

class ResumeSchema(BaseModel):
    education: Education
    work_years: WorkYears
    work_experience: list[WorkExperience] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    stability: Stability
