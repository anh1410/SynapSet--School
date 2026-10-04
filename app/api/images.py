from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.api.deps import get_current_teacher
from app.core.image_store import MAX_UPLOAD_BYTES, InvalidImageError, image_path, save_uploaded_image
from app.schemas.teacher import Teacher

router = APIRouter(prefix="/api/v1/images", tags=["images"], dependencies=[Depends(get_current_teacher)])


@router.post("")
async def upload_image(file: UploadFile = File(...), teacher: Teacher = Depends(get_current_teacher)) -> dict:
    """Any logged-in account can upload a picture (a diagram for a question, or a
    picture for an LKG/UKG worksheet). Returns the id to reference it by."""
    data = await file.read(MAX_UPLOAD_BYTES + 1)  # +1 so "exactly too big" is detectable without reading it all
    try:
        return {"image_id": save_uploaded_image(data)}
    except InvalidImageError as exc:
        status = 413 if "too large" in str(exc) else 422
        raise HTTPException(status_code=status, detail=str(exc)) from exc


@router.get("/{image_id}")
def get_image(image_id: str, teacher: Teacher = Depends(get_current_teacher)) -> FileResponse:
    path = image_path(image_id)
    if path is None:
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(path, media_type="image/png")
