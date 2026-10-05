"""Aplicação HealPlus para intake de imagens clínicas em FHIR R4."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError

from healplus_intake_image_api.api.routes import conformance, image
from healplus_intake_image_api.core.fhir import fhir_error_response, fhir_response
from healplus_intake_image_api.schemas.image import operation_outcome
from healplus_intake_image_api.services.image import FHIRRequestError

app = FastAPI(
    title="API HealPlus de Intake de Imagens FHIR R4",
    description=(
        "API para recebimento assíncrono de fotografias clínicas JPEG por meio "
        "de recursos FHIR R4. A operação `$submit-media` recebe um `Parameters` "
        "com um `Bundle` de recursos `Media` e retorna uma `Task` para "
        "acompanhamento da análise."
    ),
    version="0.1.0",
    openapi_tags=[
        {
            "name": "Intake de imagens FHIR R4",
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
            diagnostics="FHIR request validation failed",
            expression=expressions,
        ),
        status_code=422,
        media_type=(
            "application/json"
            if request.headers.get("accept", "").startswith("application/json")
            else "application/fhir+json"
        ),
    )


app.include_router(image.router)
app.include_router(conformance.router)
