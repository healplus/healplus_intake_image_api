import logging

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from healplus_intake_image_api.models.image import Image
from healplus_intake_image_api.repositories.image import (
    create_image as repo_create_image,
    get_all_images as repo_get_all_images,
    get_image as repo_get_image,
)
from healplus_intake_image_api.schemas.image import ImageCreate

logger = logging.getLogger(__name__)


def create_image(db: Session, image: ImageCreate) -> Image:
    """Criar uma nova imagem com tratamento de erros.
    
    Args:
        db: Sessão do banco de dados
        image: Dados da imagem a ser criada
        
    Returns:
        Image: Imagem criada
        
    Raises:
        HTTPException: Em caso de erro na persistência
    """
    try:
        return repo_create_image(db, image)
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Erro de integridade ao criar imagem: {e}")
        raise HTTPException(
            status_code=409,
            detail="Imagem com estes dados já existe"
        )
    except OperationalError as e:
        db.rollback()
        logger.error(f"Erro operacional ao criar imagem: {e}")
        raise HTTPException(
            status_code=503,
            detail="Banco de dados indisponível no momento"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Erro inesperado ao criar imagem: {e}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao processar requisição"
        )


def get_image(db: Session, image_id: int) -> Image | None:
    """Obter uma imagem por ID com tratamento de erros.
    
    Args:
        db: Sessão do banco de dados
        image_id: ID da imagem
        
    Returns:
        Image | None: Imagem encontrada ou None
        
    Raises:
        HTTPException: Em caso de erro na consulta
    """
    try:
        return repo_get_image(db, image_id)
    except OperationalError as e:
        logger.error(f"Erro operacional ao buscar imagem {image_id}: {e}")
        raise HTTPException(
            status_code=503,
            detail="Banco de dados indisponível no momento"
        )
    except Exception as e:
        logger.error(f"Erro inesperado ao buscar imagem {image_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao processar requisição"
        )


def get_all_images(db: Session) -> list[Image]:
    """Obter todas as imagens com tratamento de erros.
    
    Args:
        db: Sessão do banco de dados
        
    Returns:
        list[Image]: Lista de imagens
        
    Raises:
        HTTPException: Em caso de erro na consulta
    """
    try:
        return repo_get_all_images(db)
    except OperationalError as e:
        logger.error(f"Erro operacional ao buscar imagens: {e}")
        raise HTTPException(
            status_code=503,
            detail="Banco de dados indisponível no momento"
        )
    except Exception as e:
        logger.error(f"Erro inesperado ao buscar imagens: {e}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao processar requisição"
        )