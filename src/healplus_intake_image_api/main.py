from fastapi import FastAPI

from healplus_intake_image_api.api.routes import image

app = FastAPI(
    title="Healplus Image Intake API",
)

app.include_router(image.router)

