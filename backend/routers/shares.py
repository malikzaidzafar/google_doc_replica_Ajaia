from fastapi import APIRouter

from deps import Conn, CurrentUser, IdParam
from schemas import ShareIn
from services import sharing

router = APIRouter(prefix="/api/documents/{doc_id}/shares", tags=["sharing"])


@router.post("")
def share_document(doc_id: IdParam, body: ShareIn, conn: Conn, user: CurrentUser):
    return {"shares": sharing.share(conn, doc_id, user, body.email, body.role)}


@router.delete("/{user_id}")
def unshare_document(doc_id: IdParam, user_id: IdParam, conn: Conn, user: CurrentUser):
    return {"shares": sharing.unshare(conn, doc_id, user, user_id)}
