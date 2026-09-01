"""Application entry point"""

import uvicorn

from app.config import settings
from app.main import create_app

app = create_app()

if __name__ == "__main__":
    uvicorn.run(app, host=settings.host, port=settings.port, reload=settings.debug)
