from fastapi import APIRouter, File, UploadFile

from deps import Conn, CurrentUser
from services import importer

router = APIRouter(prefix="/api/documents", tags=["import"])


@router.post("/import", status_code=201)
def import_document(conn: Conn, user: CurrentUser, file: UploadFile = File(...)):
    return {"id": importer.import_file(conn, user, file.filename, file.file)}
