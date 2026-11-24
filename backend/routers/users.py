from fastapi import APIRouter

from deps import Conn
from services import access

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("")
def list_users(conn: Conn):
    """Seeded accounts for the demo sign-in screen."""
    return access.list_users(conn)
