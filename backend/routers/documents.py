from fastapi import APIRouter, Response

from deps import Conn, CurrentUser, IdParam
from schemas import DocCreate, DocUpdate
from services import documents

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.get("")
def list_documents(conn: Conn, user: CurrentUser):
    return documents.list_for_user(conn, user)


@router.post("", status_code=201)
def create_document(conn: Conn, user: CurrentUser, body: DocCreate | None = None):
    return {"id": documents.create(conn, user, body.title if body else None)}


@router.get("/{doc_id}")
def get_document(doc_id: IdParam, conn: Conn, user: CurrentUser):
    return documents.get(conn, doc_id, user)


@router.put("/{doc_id}")
def update_document(doc_id: IdParam, body: DocUpdate, conn: Conn, user: CurrentUser):
    return {"version": documents.save(conn, doc_id, user, body.title, body.content, body.base_version)}


@router.delete("/{doc_id}", status_code=204)
def delete_document(doc_id: IdParam, conn: Conn, user: CurrentUser):
    documents.remove(conn, doc_id, user)
    return Response(status_code=204)
