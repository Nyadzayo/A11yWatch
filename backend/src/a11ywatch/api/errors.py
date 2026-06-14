from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

_STATUS_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    409: "conflict",
    422: "validation_error",
}


def api_error(status_code: int, code: str, message: str) -> HTTPException:
    """Raise-ready HTTPException carrying our error envelope code + message."""
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


def _envelope(code: str, message: str, details=None) -> dict:
    body: dict = {"error": {"code": code, "message": message}}
    if details is not None:
        body["error"]["details"] = details
    return body


def _safe_validation_details(errors: list[dict]) -> list[dict]:
    # Drop `input`/`url`/`ctx` so submitted values (e.g. passwords) are never echoed back.
    return [{"loc": e.get("loc"), "msg": e.get("msg"), "type": e.get("type")} for e in errors]


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def _on_validation(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content=_envelope(
                "validation_error",
                "Request validation failed",
                jsonable_encoder(_safe_validation_details(exc.errors())),
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _on_http(request: Request, exc: StarletteHTTPException):
        detail = exc.detail
        if isinstance(detail, dict) and "code" in detail:
            code = detail["code"]
            message = detail.get("message", "")
        else:
            code = _STATUS_CODES.get(exc.status_code, "error")
            message = detail if isinstance(detail, str) else str(detail)
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(code, message),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(Exception)
    async def _on_unhandled(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content=_envelope("internal_error", "Internal server error"),
        )
