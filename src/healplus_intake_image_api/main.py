from fastapi import FastAPI

from healplus_intake_image_api.api.routes import image

app = FastAPI(
    title="Healplus Intake Image API",
)

app.include_router(image.router)

