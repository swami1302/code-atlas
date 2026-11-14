from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

# Turns every error into the same JSON shape as ApiResponse in schemas.py:
# {"success": false, "message": "...", "errors": [...] | null}


def error_response(
    status_code: int,
    message: str,
    errors: list[dict] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"success": False, "message": message, "errors": errors},
        headers=headers,
    )


def register_error_handlers(app: FastAPI) -> None:
    # Starlette's HTTPException (not FastAPI's) so this also catches the automatic
    # 404 (unknown URL) and 405 (wrong method). FastAPI's one is a subclass.
    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        # headers: e.g. 405 must send back an Allow header
        return error_response(exc.status_code, str(exc.detail), headers=exc.headers)

    # FastAPI raises this when the request body/query doesn't match the schema
    @app.exception_handler(RequestValidationError)
    async def validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # loc is e.g. ("body", "url"): drop "body" so the client sees just "url"
        errors = [
            {
                "field": ".".join(map(str, e["loc"][1:])) or str(e["loc"][0]),
                "message": e["msg"],
            }
            for e in exc.errors()
        ]
        return error_response(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Invalid request", errors
        )

    # Any crash we didn't expect. The client gets a generic message (no stack trace
    # leaks out); Starlette re-raises afterwards, so uvicorn still logs the traceback.
    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        return error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "Internal server error"
        )
