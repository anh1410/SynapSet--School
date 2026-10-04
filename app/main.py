from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, auth, credits, drafts, graph, images, paper, questions, subjects, submissions, templates
from app.core.bootstrap import ensure_admin_exists
from app.core.config import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_admin_exists()
    yield


app = FastAPI(title=f"{settings.app_name} API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5174"] if settings.environment == "development" else [],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(subjects.router)
app.include_router(submissions.router)
app.include_router(credits.router)
app.include_router(drafts.router)
app.include_router(templates.router)
app.include_router(images.router)
app.include_router(graph.router)
app.include_router(questions.router)
app.include_router(paper.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
