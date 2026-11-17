"""Aplicação HealPlus para avaliação clínica de feridas em FHIR R4."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError

from healplus_intake_image_api.api.routes import avaliacao_ferida, conformance
from healplus_intake_image_api.core.fhir import fhir_error_response, fhir_response
from healplus_intake_image_api.core.config import settings
from healplus_intake_image_api.schemas.avaliacao_ferida import operation_outcome
from healplus_intake_image_api.services.avaliacao_ferida import FHIRRequestError

app = FastAPI(
    title="API HealPlus de Avaliação Clínica de Feridas FHIR R4",
    description=(
        "API para recebimento assíncrono de avaliações clínicas de feridas por "
        "meio de recursos FHIR R4. A operação `$avaliar-feridas` recebe um "
        "`Parameters` com um `Bundle` de recursos clínicos e retorna uma "
        "`Task` para acompanhamento da análise."
    ),
    version="0.2.0",
    openapi_tags=[
        {
            "name": "Avaliação clínica de feridas FHIR R4",
            "description": (
                "Submissão e consulta de Bundles, Media e Tasks da análise."
            ),
        },
        {
            "name": "Conformidade FHIR R4",
            "description": (
                "CapabilityStatement, definição da operação e perfis HealPlus."
            ),
        },
    ],
)


class RequestLimitsMiddleware:
    """Limita o corpo antes do parser JSON, inclusive em envio chunked."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        clinical = scope.get("path", "").startswith("/api/fhir/r4/")
        request = Request(scope)
        limit = settings.max_request_bytes

        async def send_private(message):
            if clinical and message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend([(b"cache-control", b"private, no-store"), (b"x-content-type-options", b"nosniff")])
                message = {**message, "headers": headers}
            await send(message)

        async def too_large():
            response = fhir_response(operation_outcome(severity="error", code="too-costly",
                diagnostics="Corpo da requisição excede o limite permitido", expression=["Parameters"]), status_code=413)
            await response(scope, receive, send_private)

        content_length = request.headers.get("content-length")
        if content_length:
            try:
                declared = int(content_length)
            except ValueError:
                declared = limit + 1
            if declared < 0 or declared > limit:
                return await too_large()
        if scope["method"] in {"POST", "PUT", "PATCH"}:
            body = bytearray()
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                chunk = message.get("body", b"")
                if len(body) + len(chunk) > limit:
                    return await too_large()
                body.extend(chunk)
                if not message.get("more_body", False):
                    break
            iterator = iter([{"type": "http.request", "body": bytes(body), "more_body": False}])

            async def replay():
                return next(iterator, {"type": "http.disconnect"})
            return await self.app(scope, replay, send_private)
        await self.app(scope, receive, send_private)


app.add_middleware(RequestLimitsMiddleware)


@app.exception_handler(FHIRRequestError)
async def handle_fhir_request_error(
    request: Request,
    error: FHIRRequestError,
):
    """Retorna erros da aplicação como recursos FHIR OperationOutcome."""
    return fhir_error_response(error, accept=request.headers.get("accept"))


@app.exception_handler(RequestValidationError)
async def handle_validation_error(
    request: Request,
    error: RequestValidationError,
):
    """Retorna falhas de validação FHIR como recursos OperationOutcome."""
    expressions = []
    for item in error.errors():
        expression = "Parameters"
        for part in item["loc"]:
            if part == "body":
                continue
            if isinstance(part, int):
                expression += f"[{part}]"
            else:
                expression += f".{part}"
        expressions.append(expression)
    return fhir_response(
        operation_outcome(
            severity="error",
            code="invalid",
            diagnostics="Falha na validação da requisição FHIR",
            expression=expressions,
        ),
        status_code=422,
        media_type=(
            "application/json"
            if request.headers.get("accept", "").startswith("application/json")
            else "application/fhir+json"
        ),
    )


app.include_router(avaliacao_ferida.router)
app.include_router(conformance.router)
