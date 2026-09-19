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
    )
