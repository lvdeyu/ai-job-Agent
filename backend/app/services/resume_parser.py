from __future__ import annotations

import re
import zipfile
from html import unescape
from pathlib import Path
from xml.etree import ElementTree

from pypdf import PdfReader

SUPPORTED_RESUME_EXTENSIONS = {".md", ".docx", ".pdf"}


def extract_resume_text(path: Path, file_ext: str) -> str:
    if file_ext == ".md":
        return path.read_text(encoding="utf-8", errors="ignore").strip()
    if file_ext == ".docx":
        return _extract_docx_text(path).strip()
    if file_ext == ".pdf":
        return _extract_pdf_text(path).strip()
    raise ValueError("仅支持 .docx、.md、.pdf 简历文件。")


def _extract_docx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as docx:
        xml = docx.read("word/document.xml")
    root = ElementTree.fromstring(xml)
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs: list[str] = []
    for paragraph in root.findall(".//w:p", namespace):
        texts = [node.text or "" for node in paragraph.findall(".//w:t", namespace)]
        line = "".join(texts).strip()
        if line:
            paragraphs.append(line)
    return "\n".join(paragraphs)


def _extract_pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages)


def compact_text(text: str) -> str:
    text = unescape(text)
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
