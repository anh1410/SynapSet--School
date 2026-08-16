import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.api.deps import get_current_teacher, require_subject
from app.core.config import get_settings
from app.core.paper_store import get_paper_store
from app.core.question_bank import get_question_bank
from app.core.subject_store import get_subject_store
from app.schemas.constraints import PaperConstraints
from app.schemas.paper_blueprint import BlueprintSection, BlueprintStatus, PaperBlueprint
from app.schemas.question import Question, QuestionType
from app.schemas.teacher import Teacher
from app.services.paper_export import export_paper_docx, export_paper_pdf
from app.services.paper_optimization import optimize_paper

router = APIRouter(prefix="/api/v1/paper", tags=["paper"], dependencies=[Depends(get_current_teacher)])


def _require_owned_blueprint(blueprint_id: str, teacher: Teacher) -> PaperBlueprint:
    blueprint = get_paper_store().get(blueprint_id)
    if blueprint is None or blueprint.teacher_id != teacher.id:
        raise HTTPException(status_code=404, detail="Blueprint not found")
    return blueprint


class OptimizePaperRequest(BaseModel):
    subject_id: str
    constraints: PaperConstraints
    question_ids: list[str] | None = None


class OptimizePaperResponse(BaseModel):
    status: str
    selected: list[Question]


@router.post("/optimize", response_model=OptimizePaperResponse)
def optimize(request: OptimizePaperRequest, teacher: Teacher = Depends(get_current_teacher)) -> OptimizePaperResponse:
    """Run the CP-SAT solver over the question bank (or a given subset) against hard constraints."""
    require_subject(request.subject_id, teacher)
    bank = get_question_bank()
    if request.question_ids:
        candidates = [q for qid in request.question_ids if (q := bank.get(qid)) is not None]
    else:
        candidates = bank.list_by_subject(request.subject_id)

    if not candidates:
        raise HTTPException(status_code=400, detail="No candidate questions available")

    result = optimize_paper(candidates, request.constraints)
    return OptimizePaperResponse(status=result.status, selected=result.selected)


def _write_export_file(
    blueprint: PaperBlueprint,
    sections: list[tuple[BlueprintSection, list[Question]]],
    teacher_name: str,
    subject_name: str,
    include_answers: bool,
    fmt: str,
) -> Path:
    settings = get_settings()
    export_dir = Path(settings.export_dir)
    export_dir.mkdir(parents=True, exist_ok=True)
    safe_title = "".join(c if c.isalnum() else "_" for c in blueprint.name)[:50] or "paper"
    suffix = "_answer_key" if include_answers else ""

    if fmt == "pdf":
        path = export_dir / f"{safe_title}{suffix}.pdf"
        export_paper_pdf(blueprint, sections, teacher_name, subject_name, include_answers, str(path))
    elif fmt == "docx":
        path = export_dir / f"{safe_title}{suffix}.docx"
        export_paper_docx(blueprint, sections, teacher_name, subject_name, include_answers, str(path))
    else:
        raise HTTPException(status_code=400, detail="format must be 'pdf' or 'docx'")
    return path


_MEDIA_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


class ExportPaperRequest(BaseModel):
    title: str
    questions: list[Question]
    format: str = "pdf"
    variant: Literal["student", "answer_key"] = "student"


@router.post("/export")
def export(request: ExportPaperRequest, teacher: Teacher = Depends(get_current_teacher)) -> FileResponse:
    """Ad-hoc export of an arbitrary question list, without saving a blueprint."""
    blueprint = PaperBlueprint(
        id="adhoc",
        teacher_id=teacher.id,
        subject_id="",
        name=request.title,
        total_marks=sum(q.marks for q in request.questions),
        sections=[BlueprintSection(id="adhoc", title=request.title, question_format=QuestionType.SHORT_ANSWER, question_ids=[q.id for q in request.questions])],
    )
    path = _write_export_file(
        blueprint, [(blueprint.sections[0], request.questions)], teacher.name, "", request.variant == "answer_key", request.format
    )
    return FileResponse(path, media_type=_MEDIA_TYPES[request.format], filename=path.name)


class CreateBlueprintSectionInput(BaseModel):
    title: str
    question_format: QuestionType
    question_ids: list[str] = []


class CreateBlueprintRequest(BaseModel):
    subject_id: str
    name: str
    total_marks: int
    duration_minutes: int | None = None
    sections: list[CreateBlueprintSectionInput] = []


class UpdateBlueprintRequest(BaseModel):
    name: str | None = None
    total_marks: int | None = None
    duration_minutes: int | None = None
    sections: list[CreateBlueprintSectionInput] | None = None
    status: BlueprintStatus | None = None


@router.post("/blueprints", response_model=PaperBlueprint)
def create_blueprint(request: CreateBlueprintRequest, teacher: Teacher = Depends(get_current_teacher)) -> PaperBlueprint:
    require_subject(request.subject_id, teacher)
    blueprint = PaperBlueprint(
        id=str(uuid.uuid4()),
        teacher_id=teacher.id,
        subject_id=request.subject_id,
        name=request.name,
        total_marks=request.total_marks,
        duration_minutes=request.duration_minutes,
        sections=[
            BlueprintSection(id=str(uuid.uuid4()), title=s.title, question_format=s.question_format, question_ids=s.question_ids)
            for s in request.sections
        ],
    )
    get_paper_store().add(blueprint)
    return blueprint


@router.get("/blueprints", response_model=list[PaperBlueprint])
def list_blueprints(subject_id: str, teacher: Teacher = Depends(get_current_teacher)) -> list[PaperBlueprint]:
    require_subject(subject_id, teacher)
    return [b for b in get_paper_store().list_by_teacher(teacher.id) if b.subject_id == subject_id]


class BlueprintDetail(BaseModel):
    blueprint: PaperBlueprint
    questions: list[Question]


@router.get("/blueprints/{blueprint_id}", response_model=BlueprintDetail)
def get_blueprint(blueprint_id: str, teacher: Teacher = Depends(get_current_teacher)) -> BlueprintDetail:
    blueprint = _require_owned_blueprint(blueprint_id, teacher)
    bank = get_question_bank()
    questions = [q for qid in blueprint.question_ids if (q := bank.get(qid)) is not None]
    return BlueprintDetail(blueprint=blueprint, questions=questions)


@router.patch("/blueprints/{blueprint_id}", response_model=PaperBlueprint)
def update_blueprint(blueprint_id: str, request: UpdateBlueprintRequest, teacher: Teacher = Depends(get_current_teacher)) -> PaperBlueprint:
    blueprint = _require_owned_blueprint(blueprint_id, teacher)
    store = get_paper_store()

    update_data = request.model_dump(exclude_unset=True, exclude={"sections"})
    if request.sections is not None:
        update_data["sections"] = [
            BlueprintSection(id=str(uuid.uuid4()), title=s.title, question_format=s.question_format, question_ids=s.question_ids)
            for s in request.sections
        ]
    updated = blueprint.model_copy(update=update_data)
    store.add(updated)
    return updated


@router.delete("/blueprints/{blueprint_id}")
def delete_blueprint(blueprint_id: str, teacher: Teacher = Depends(get_current_teacher)) -> dict:
    _require_owned_blueprint(blueprint_id, teacher)
    get_paper_store().remove(blueprint_id)
    return {"deleted": blueprint_id}


@router.get("/blueprints/{blueprint_id}/export")
def export_blueprint(
    blueprint_id: str,
    format: str = "pdf",
    variant: Literal["student", "answer_key"] = "student",
    teacher: Teacher = Depends(get_current_teacher),
) -> FileResponse:
    blueprint = _require_owned_blueprint(blueprint_id, teacher)
    store = get_paper_store()

    bank = get_question_bank()
    sections = [(s, [q for qid in s.question_ids if (q := bank.get(qid)) is not None]) for s in blueprint.sections]
    subject = get_subject_store().get(blueprint.subject_id)
    subject_name = subject.name if subject else ""

    path = _write_export_file(blueprint, sections, teacher.name, subject_name, variant == "answer_key", format)

    blueprint.status = "exported"
    store.add(blueprint)

    return FileResponse(path, media_type=_MEDIA_TYPES[format], filename=path.name)
