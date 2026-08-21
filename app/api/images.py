from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.api.deps import get_current_teacher
from app.core.image_store import image_path
from app.schemas.teacher import Teacher

router = APIRouter(prefix="/api/v1/images", tags=["images"], dependencies=[Depends(get_current_teacher)])


@router.get("/{image_id}")
def get_image(image_id: str, teacher: Teacher = Depends(get_current_teacher)) -> FileResponse:
    path = image_path(image_id)
    if path is None:
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(path, media_type="image/png")
