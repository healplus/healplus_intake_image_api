from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from healplus_intake_image_api.core.config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


def get_db() -> Generator[Session, None, None]:
    """Gerenciador de contexto para sessões de banco de dados.
    
    Garante que:
    - A sessão é criada para cada requisição
    - Rollback é feito em caso de exceção
    - A sessão é sempre fechada ao final
    """
    db = SessionLocal()

    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()