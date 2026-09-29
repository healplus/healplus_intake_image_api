from sqlalchemy.orm import Session

from healplus_intake_image_api.models.image import Image
from healplus_intake_image_api.schemas.image import ImageCreate


def create_image(db: Session, image: ImageCreate) -> Image:
    """Persistir uma nova imagem no banco de dados."""
    db_image = Image(name=image.name)
    db.add(db_image)
    db.commit()
    db.refresh(db_image)
    return db_image


def get_image(db: Session, image_id: int) -> Image | None:
    """Buscar uma imagem por ID."""
    return db.query(Image).filter(Image.id == image_id).first()


def get_all_images(db: Session) -> list[Image]:
    """Buscar todas as imagens."""
    return db.query(Image).all()