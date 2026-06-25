"""FastAPI 应用 - AI 招聘助手后端接口"""
import json
import uuid
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# 项目模块
from backend.src.agent import run_agent, _init_registry
from backend.src.tools.parser import resume_parse_tool
from backend.src.tools.file_parser import extract_text_from_file
from backend.src.cache import cache_service

_init_registry()

app = FastAPI(title="AI 招聘助手", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class ChatRequest(BaseModel):
    session_id: str = ""
    input: str


class ChatResponse(BaseModel):
    reply: str
    session_id: str


@app.get("/")
async def root():
    return {"status": "ok", "title": "AI 招聘助手 API"}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    sid = req.session_id or uuid.uuid4().hex
    reply = run_agent(sid, req.input)
    return ChatResponse(reply=reply, session_id=sid)


@app.post("/api/upload")
async def upload(file: UploadFile, session_id: str = Form("")):
    sid = session_id or uuid.uuid4().hex
    path = f"/tmp/{uuid.uuid4().hex}_{file.filename}"
    content = await file.read()
    with open(path, "wb") as f:
        f.write(content)
    text = extract_text_from_file(path)
    reply = run_agent(sid, text)
    return {"reply": reply, "session_id": sid, "filename": file.filename}


@app.post("/api/parse")
async def parse(file: UploadFile):
    path = f"/tmp/{uuid.uuid4().hex}_{file.filename}"
    content = await file.read()
    with open(path, "wb") as f:
        f.write(content)
    text = extract_text_from_file(path)
    result = resume_parse_tool.invoke({"resume_text": text, "output_for_user": False})
    if result.startswith("简历解析失败"):
        return {"error": result}
    return json.loads(result)


if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    print(f"启动 API: http://127.0.0.1:{port}")
    print(f"接口文档: http://127.0.0.1:{port}/docs")
    uvicorn.run("backend.app:app", host="0.0.0.0", port=port, reload=True)
