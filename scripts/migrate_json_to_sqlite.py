"""One-time migration: import the old flat-JSON stores in data/ into the new
SQLite database (data/synapset_school.db). Safe to re-run — every row is
upserted by primary key, so running it twice just re-writes the same rows.

Run from the project root:
    .venv\\Scripts\\python.exe scripts\\migrate_json_to_sqlite.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings  # noqa: E402
from app.core.document_store import DocumentStore  # noqa: E402
from app.core.draft_store import DraftStore  # noqa: E402
from app.core.paper_store import PaperStore  # noqa: E402
from app.core.question_bank import QuestionBank  # noqa: E402
from app.core.subject_store import SubjectStore  # noqa: E402
from app.core.teacher_store import TeacherStore  # noqa: E402
from app.core.template_store import TemplateStore  # noqa: E402
from app.schemas.document import UploadedDocument  # noqa: E402
from app.schemas.draft import BuilderDraft  # noqa: E402
from app.schemas.paper_blueprint import PaperBlueprint  # noqa: E402
from app.schemas.question import Question  # noqa: E402
from app.schemas.subject import Subject  # noqa: E402
from app.schemas.teacher import Teacher  # noqa: E402
from app.schemas.template import PaperTemplate  # noqa: E402


def _load_json(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    settings = get_settings()
    base = Path(settings.database_path).parent
    db_path = settings.database_path

    migrations = [
        ("teachers.json", Teacher, TeacherStore(db_path).add),
        ("subjects.json", Subject, SubjectStore(db_path).add),
        ("documents.json", UploadedDocument, DocumentStore(db_path).add),
        ("question_bank.json", Question, QuestionBank(db_path).add),
        ("paper_blueprints.json", PaperBlueprint, PaperStore(db_path).add),
        ("builder_drafts.json", BuilderDraft, DraftStore(db_path).upsert),
        ("paper_templates.json", PaperTemplate, TemplateStore(db_path).add),
    ]

    total = 0
    for filename, model, add_fn in migrations:
        rows = _load_json(base / filename)
        for row in rows:
            add_fn(model.model_validate(row))
        print(f"{filename}: migrated {len(rows)} row(s)")
        total += len(rows)

    print(f"\nDone — {total} row(s) migrated into {db_path}")
    print("Old JSON files were left untouched; delete them by hand once you've verified the app.")


if __name__ == "__main__":
    main()
