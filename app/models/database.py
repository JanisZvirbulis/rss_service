from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.config import settings

# Izveidojam datubāzes dzinēju
engine = create_engine(
    str(settings.SQLALCHEMY_DATABASE_URI),
    pool_pre_ping=True,  # Pārbauda savienojumu pirms tā izmantošanas
    pool_recycle=3600,   # Atjauno savienojumus pēc stundas
)

# Izveidojam sesijas fabriku
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Izveidojam bāzes modeli
Base = declarative_base()


# Utilitātes funkcija, lai iegūtu datubāzes sesiju
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()