from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from pythonjsonlogger import json
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

LOGGER_NAME = "ai_job_agent"
REQUEST_ID_HEADER = "X-Request-ID"


def configure_logging() -> None:
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    if logger.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(
        json.JsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s "
            "%(request_id)s %(method)s %(path)s %(status_code)s %(duration_ms)s"
        )
    )
    logger.addHandler(handler)
    logger.propagate = False


def request_id_from_scope(request: Request) -> str:
    return getattr(request.state, "request_id", "")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid4().hex
        request.state.request_id = request_id
        started_at = time.perf_counter()
        response: Response | None = None
        try:
            response = await call_next(request)
            return response
        finally:
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            status_code = response.status_code if response is not None else 500
            if response is not None:
                response.headers[REQUEST_ID_HEADER] = request_id
            logging.getLogger(LOGGER_NAME).info(
                "request_completed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                },
            )


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        return _error_response(
            request=request,
            status_code=exc.status_code,
            code=_error_code_for_status(exc.status_code),
            message=str(exc.detail),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return _error_response(
            request=request,
            status_code=422,
            code="VALIDATION_ERROR",
            message="请求参数不符合要求。",
            details=exc.errors(),
        )

    @app.exception_handler(Exception)
    async def unexpected_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logging.getLogger(LOGGER_NAME).exception(
            "request_failed",
            extra={
                "request_id": request_id_from_scope(request),
                "method": request.method,
                "path": request.url.path,
                "status_code": 500,
                "duration_ms": None,
            },
        )
        return _error_response(
            request=request,
            status_code=500,
            code="INTERNAL_ERROR",
            message="服务暂时不可用，请稍后重试。",
        )


def _error_response(
    *,
    request: Request,
    status_code: int,
    code: str,
    message: str,
    details: object | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    request_id = request_id_from_scope(request)
    payload = {
        "error": {
            "code": code,
            "message": message,
            "request_id": request_id,
        }
    }
    if details is not None:
        payload["error"]["details"] = details
    response = JSONResponse(status_code=status_code, content=payload, headers=headers)
    if request_id:
        response.headers[REQUEST_ID_HEADER] = request_id
    return response


def _error_code_for_status(status_code: int) -> str:
    if status_code == 401:
        return "UNAUTHORIZED"
    if status_code == 403:
        return "FORBIDDEN"
    if status_code == 404:
        return "NOT_FOUND"
    if status_code == 409:
        return "CONFLICT"
    if status_code == 422:
        return "BUSINESS_RULE_ERROR"
    return "HTTP_ERROR"
