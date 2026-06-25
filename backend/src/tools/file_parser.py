"""文件解析工具 - 支持 PDF/DOCX/TXT 格式提取文字"""
import re
from pathlib import Path

def extract_text_from_file(file_path: str) -> str:
    """根据文件后缀选择合适的解析器"""
    ext = Path(file_path).suffix.lower()
    if ext == ".pdf":
        return _extract_pdf(file_path)
    elif ext == ".docx":
        return _extract_docx(file_path)
    elif ext == ".txt":
        return _extract_txt(file_path)
    else:
        return f"不支持的文件格式: {ext}"

def _extract_pdf(path: str) -> str:
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    except ImportError:
        return "需要安装 pdfplumber: pip install pdfplumber"
    except Exception as e:
        return f"PDF 解析失败: {str(e)}"

def _extract_docx(path: str) -> str:
    try:
        from docx import Document
        doc = Document(path)
        return "\n".join(p.text for p in doc.paragraphs)
    except ImportError:
        return "需要安装 python-docx: pip install python-docx"
    except Exception as e:
        return f"DOCX 解析失败: {str(e)}"

def _extract_txt(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()
