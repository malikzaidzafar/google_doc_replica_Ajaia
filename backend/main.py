"""DocShare API: app setup, routers and error handlers only. Logic lives in services/."""
import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from routers import documents, imports, shares, users
from services import errors

logger = logging.getLogger("docshare")

app = FastAPI(title="DocShare API")
for module in (users, imports, documents, shares):
    app.include_router(module.router)


@app.exception_handler(StarletteHTTPException)
async def http_error(_request: Request, exc: StarletteHTTPException):
    # Our services raise FastAPI's HTTPException; plain Starlette ones come from the framework (raw text).
    ours = isinstance(exc, HTTPException)
    return JSONResponse({"detail": errors.humanize_http(exc.status_code, exc.detail, ours)}, exc.status_code,
                        exc.headers)


@app.exception_handler(RequestValidationError)
async def validation_error(_request: Request, exc: RequestValidationError):
    status, message = errors.humanize_validation(exc.errors())
    return JSONResponse({"detail": message}, status)


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception):
    logger.error("Unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse({"detail": errors.GENERIC_500}, 500)
