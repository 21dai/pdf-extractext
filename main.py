"""Application entry point"""

import uvicorn

from app.config import settings
from app.main import create_app

app = create_app()

if __name__ == "__main__":
    # La app se pasa como import string: uvicorn lo exige para reload y workers.
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        workers=settings.web_concurrency,
        # Sin la config de logging de uvicorn: sus logs pasan por el handler
        # JSON que instala create_app (una linea JSON por evento en stdout).
        log_config=None,
    )
