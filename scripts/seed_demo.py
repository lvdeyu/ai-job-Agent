"""Seed a demo user, resume, and pooled job for V0.5 local demo."""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import Job, ResumeFile, ResumeVersion, User
from app.services.interview import seed_question_bank_if_needed

DEMO_EMAIL = "demo@ai-job-agent.local"
DEMO_PASSWORD = "demo123456"

DEMO_RESUME_TEXT = """\
张三
求职方向：Agent 开发实习生

技能：Python、FastAPI、LangGraph、RAG、pgvector、SQL、Redis、Docker

项目：ai-job-AGENT 求职工作台
负责模块：模拟面试 Agent 链路
- 使用 LangGraph 编排面试状态机，支持中断恢复。
- 通过 pgvector 检索题库，按 JD 和简历生成面试问题。
- 实现确定性评分与证据引用，避免模型随意打分。

项目：简历匹配评测服务
负责模块：JD 结构化与七维评分
- 解析 JD 技能要求并对比简历命中情况。
- 实现 Deal-breaker 封顶、语言闸门和信息不足中性分。
"""

DEMO_JOB = {
    "title": "AI Agent 开发实习生",
    "company": "Demo 智能科技",
    "location": "杭州",
    "salary": "200-300元/天",
    "experience": "经验不限",
    "education": "本科",
    "tags": "Python,FastAPI,LangGraph,Agent,RAG",
    "description": "负责 Python、FastAPI、LangGraph 和 AI Agent 工具开发；"
    "参与模拟面试 Agent、RAG 检索和工具调用相关工作。",
    "job_url": "https://www.zhipin.com/job_detail/demo-agent.html",
}


def main() -> None:
    with SessionLocal() as db:
        seed_question_bank_if_needed(db)

        user = db.scalar(select(User).where(User.email == DEMO_EMAIL))
        if user is None:
            user = User(email=DEMO_EMAIL, password_hash=hash_password(DEMO_PASSWORD))
            db.add(user)
            db.flush()
            print(f"created user {DEMO_EMAIL}")
        else:
            print(f"reuse user {DEMO_EMAIL}")

        resume_file = db.scalar(
            select(ResumeFile).where(
                ResumeFile.user_id == user.id,
                ResumeFile.original_filename == "demo-resume.md",
            )
        )
        if resume_file is None:
            resume_file = ResumeFile(
                user_id=user.id,
                original_filename="demo-resume.md",
                file_ext=".md",
                storage_path="demo://demo-resume.md",
                content_type="text/markdown",
                file_size=len(DEMO_RESUME_TEXT),
                is_default=True,
            )
            db.add(resume_file)
            db.flush()
            db.add(
                ResumeVersion(
                    user_id=user.id,
                    resume_file_id=resume_file.id,
                    version_no=1,
                    title="demo-resume v1",
                    extracted_text=DEMO_RESUME_TEXT,
                )
            )
            print("created demo resume")
        else:
            print("reuse demo resume")

        job = db.scalar(
            select(Job).where(
                Job.user_id == user.id,
                Job.source == "demo",
                Job.title == DEMO_JOB["title"],
            )
        )
        if job is None:
            job = Job(
                user_id=user.id,
                source="demo",
                source_fingerprint=f"demo:{user.id}:{DEMO_JOB['title']}",
                title=DEMO_JOB["title"],
                company=DEMO_JOB["company"],
                location=DEMO_JOB["location"],
                salary=DEMO_JOB["salary"],
                experience=DEMO_JOB["experience"],
                education=DEMO_JOB["education"],
                tags=DEMO_JOB["tags"],
                description=DEMO_JOB["description"],
                job_url=DEMO_JOB["job_url"],
                is_in_pool=True,
                application_status="CONFIRMED",
                status_changed_at=datetime.now(UTC),
            )
            db.add(job)
            print("created demo job")
        else:
            print("reuse demo job")

        db.commit()

    print("")
    print("Demo ready:")
    print(f"- email:    {DEMO_EMAIL}")
    print(f"- password: {DEMO_PASSWORD}")
    print("- 登录后进入“岗位池”即可开始模拟面试；配置真实模型后为 HR 对话模式。")


if __name__ == "__main__":
    main()
