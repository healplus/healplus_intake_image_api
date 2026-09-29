from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from healplus_intake_image_api.core.database import get_db
from healplus_intake_image_api.schemas.image import ImageCreate, ImageResponse
from healplus_intake_image_api.services.image import (
    create_image,
    get_all_images,
    get_image,
)

router = APIRouter(
    prefix="/images",
    tags=["images"],
)


@router.post(
    "/",
    response_model=ImageResponse,
    status_code=201,
)
def create(
    image: ImageCreate,
    db: Session = Depends(get_db),
) -> ImageResponse:
    """Criar uma nova imagem.
    
    Args:
        image: Dados da imagem (nome obrigatório)
        
    Returns:
        Imagem criada com ID
        
    Raises:
        409: Imagem com estes dados já existe
        500: Erro ao processar requisição
    """
    return create_image(db, image)


@router.get(
    "/",
    response_model=list[ImageResponse],
)
def read_all(
    db: Session = Depends(get_db),
) -> list[ImageResponse]:
    """Obter todas as imagens.
    
    Returns:
        Lista de todas as imagens
        
    Raises:
        500: Erro ao processar requisição
    """
    return get_all_images(db)


@router.get(
    "/{image_id}",
    response_model=ImageResponse,
)
def read_one(
    image_id: int,
    db: Session = Depends(get_db),
) -> ImageResponse:
    """Obter uma imagem específica.
    
    Args:
        image_id: ID da imagem
        
    Returns:
        Imagem encontrada
        
    Raises:
        404: Imagem não encontrada
        500: Erro ao processar requisição
    """
    image = get_image(db, image_id)
    if image is None:
        raise HTTPException(status_code=404, detail="Imagem não encontrada")
    return image

