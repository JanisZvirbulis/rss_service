# RSS datu ievākšanas serviss

Šis mikroserviss ir paredzēts RSS barotņu datu automātiskai ievākšanai, uzglabāšanai un pārvaldībai. Serviss apkopo ziņas no dažādiem RSS avotiem, saglabā tās datubāzē un nodrošina API piekļuvi šiem datiem.

## Galvenās funkcijas

- 🔄 Automātiska RSS ziņu ievākšana no norādītajiem avotiem
- 📅 Periodiska datu atjaunināšana, izmantojot Celery uzdevumu plānotāju
- 🔍 Ziņu filtrēšana un meklēšana pēc dažādiem kritērijiem
- 📊 Statistika par ievāktajiem datiem
- 🚀 RESTful API integrācijai ar citiem servisiem

## Tehnoloģijas

- **FastAPI**: Moderns, ātrs (lielā ātruma dēļ nosaukts "Fast") Python tīmekļa ietvars
- **SQLAlchemy**: SQL komplekts un ORM risinājums
- **Celery**: Asinhrono uzdevumu izpildes rinda
- **Redis**: Atmiņas datu struktūru krātuve, ko izmanto kā Celery brokeri
- **PostgreSQL**: Relāciju datubāze datu uzglabāšanai
- **Alembic**: Datubāzes migrācijas rīks

## Uzstādīšana

### Priekšnosacījumi

- Python 3.9+
- PostgreSQL
- Redis

### Vides sagatavošana

1. Klonējiet repozitoriju
```bash
git clone https://github.com/yourusername/rss-service.git
cd rss-service
```

2. Izveidojiet virtuālo vidi un instalējiet atkarības
```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
# vai
venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

3. Izveidojiet `.env` failu ar sekojošiem iestatījumiem
```
# Datubāzes konfigurācija
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=rss_service

# Celery konfigurācija
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Debugging (tikai izstrādes vidē)
DEBUG=True
```

4. Inicializējiet datubāzi, izmantojot Alembic
```bash
alembic revision --autogenerate -m "Initial migration"
alembic upgrade head
```

## Servisa palaišana

1. Startējiet FastAPI servisu
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

2. Palaistiet Celery darbinieku
```bash
celery -A celeryworker worker --loglevel=info
celery -A celeryworker worker --pool=solo -Q feeds,maintenance --loglevel=info

```

3. Palaistiet Celery Beat plānotāju (periodiskie uzdevumi)
```bash
celery -A celeryworker beat --loglevel=info
```

4. (Pēc izvēles) Palaistiet Flower monitoringu
```bash
celery -A celeryworker flower
```

## API dokumentācija

Kad serviss ir palaists, API dokumentācija ir pieejama:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## RSS barotņu pārvaldība

### Barotnes pievienošana

```bash
curl -X POST "http://localhost:8000/api/feeds/" \
     -H "Content-Type: application/json" \
     -d '{"url": "https://www.example.com/rss", "active": true}'
```

### Barotņu saraksta iegūšana

```bash
curl -X GET "http://localhost:8000/api/feeds/"
```

### Manuāla barotnes ievākšana

```bash
curl -X POST "http://localhost:8000/api/feeds/1/fetch"
```

## Ierakstu pārlūkošana

### Ierakstu saraksta iegūšana ar filtriem

```bash
curl -X GET "http://localhost:8000/api/entries/?feed_id=1&search=Latvia&limit=10"
```

### Ziņas iegūšana pēc ID

```bash
curl -X GET "http://localhost:8000/api/entries/your-entry-id"
```

## Docker izmantošana (pēc izvēles)

Projektam var izveidot Docker konfigurāciju, lai atvieglotu tā darbināšanu dažādās vidēs.

## Projekta turpmākā attīstība

- Ziņu konteksta analīze un grupēšana
- Sentimenta analīze
- Automatizētu kopsavilkumu veidošana
- Tēmu (topics) automātiska atpazīšana
- Integrācija ar shortNews servisu

## Licences

MIT