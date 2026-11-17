"""Worker de fila persistida: python -m healplus_intake_image_api.worker."""

import argparse
import logging
import time

from healplus_intake_image_api.core.config import settings
from healplus_intake_image_api.core.database import SessionLocal
from healplus_intake_image_api.services.quality import process_next_task

logger = logging.getLogger(__name__)


def main() -> None:
    """Executa a fila, ou uma única passagem com --once, sem memória volátil."""
    parser = argparse.ArgumentParser(description="Worker de qualidade técnica HealPlus")
    parser.add_argument("--once", action="store_true", help="Processa no máximo uma Task e encerra")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    try:
        while True:
            worked = False
            try:
                with SessionLocal() as db:
                    worked = process_next_task(db)
            except Exception:
                # Um erro de conexão não encerra a fila; leases permitem recuperação.
                logger.error("Fila temporariamente indisponível")
                if args.once:
                    raise
            if args.once:
                break
            if not worked:
                time.sleep(getattr(settings, "worker_poll_seconds", 1.0))
    except KeyboardInterrupt:
        logger.info("Worker encerrado")


if __name__ == "__main__":
    main()
