from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    app_name: str = "SynapSet"
    environment: str = "development"
    debug: bool = True

    # Google Gemini
    google_api_key: str = ""
    embedding_model: str = "gemini-embedding-001"
    generation_model: str = "gemini-flash-lite-latest"

    # Neo4j (optional; falls back to NetworkX in-memory/pickle if unset)
    neo4j_uri: str = ""
    neo4j_user: str = ""
    neo4j_password: str = ""

    # Vector store (ChromaDB) — one collection per subject
    chroma_persist_dir: str = str(BASE_DIR / "data" / "chroma")

    # File storage
    upload_dir: str = str(BASE_DIR / "data" / "uploads")

    # Graph storage (used when Neo4j is not configured) — one pickle file per subject
    graph_store_dir: str = str(BASE_DIR / "data" / "graphs")

    # Paper export output
    export_dir: str = str(BASE_DIR / "data" / "exports")

    # Auth
    jwt_secret: str = "dev-insecure-secret-change-me"
    jwt_expire_minutes: int = 60 * 24 * 7

    # SQLite database — teachers, subjects, documents, questions, paper
    # blueprints, builder drafts, and paper templates all live here as real
    # tables (one file, browsable with any SQLite GUI). Knowledge graphs and
    # vector embeddings stay separate since they aren't relational data.
    database_path: str = str(BASE_DIR / "data" / "synapset_school.db")


@lru_cache
def get_settings() -> Settings:
    return Settings()
