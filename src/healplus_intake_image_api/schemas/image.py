from pydantic import BaseModel, ConfigDict


class ImageCreate(BaseModel):
    name: str


class ImageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str