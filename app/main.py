from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
import logging
from contextlib import asynccontextmanager

from app.api.router import api_router
from app.config import settings
from app.models.database import Base, engine

# Konfigurējam žurnalēšanu
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Funkcija, kas tiek izpildīta, kad aplikācija tiek palaista un apturēta
    """
    # Kods, kas tiek izpildīts, kad aplikācija tiek palaista
    logger.info("RSS Collection Service startējas")
    try:
        # Izveidojam datubāzes tabulasn ja tās vēl nav izveidotas
        # Produkcijā labāk izmantot Alembic migrācijasn bet attīstības vidē var izmantot šo
        Base.metadata.create_all(bind=engine)
        logger.info("Datubāzes tabulas izveidotas/pārbaudītas")
    except Exception as e:
        logger.error(f"Kļūda inicializējot datubāzi: {e}")
        raise
    
    yield  # Aplikācija darbojas
    
    # Kods, kas tiek izpildīts, kad aplikācija tiek apturēta
    logger.info("RSS Collection Service beidz darbu")


# Izveidojam FastAPI instanci
app = FastAPI(
    title=settings.APP_NAME,
    description="RSS datu ievākšanas un apstrādes serviss",
    version="0.1.0",
    lifespan=lifespan,
)

# Konfigurējam CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Produkcijas vidē šeit jānorāda konkrētas atļautās izcelsmes
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pievienojam API maršrutus
app.include_router(api_router, prefix=settings.API_PREFIX)


@app.get("/")
def root():
    """
    Sākuma lapa, kas apstiprina, ka serviss darbojas
    """
    return {
        "status": "online",
        "service": settings.APP_NAME,
        "version": "0.1.0",
        "api_docs": "/docs",
    }


@app.get("/health")
def health_check():
    """
    Veselības pārbaudes galapunkts (health check)
    """
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)