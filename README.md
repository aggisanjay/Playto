# Playto Payout Engine

A production-grade payout engine built for the Playto Founding Engineer Challenge. This service enables Indian merchants to view their balance, request payouts, and track payout status — with proper concurrency control, idempotency, and data integrity.

## Architecture

```
┌─────────────────────┐     ┌──────────────────────────────┐
│   React + Tailwind   │────▶│   Django + DRF (REST API)    │
│   Merchant Dashboard │◀────│   /api/v1/payouts            │
└─────────────────────┘     │   /api/v1/merchants          │
                            └──────────┬───────────────────┘
                                       │
                            ┌──────────▼───────────────────┐
                            │   PostgreSQL                  │
                            │   SELECT FOR UPDATE locking   │
                            │   Immutable ledger entries    │
                            └──────────┬───────────────────┘
                                       │
                            ┌──────────▼───────────────────┐
                            │   Celery + Redis              │
                            │   Async payout processing     │
                            │   Retry stuck payouts (beat)  │
                            └──────────────────────────────┘
```

## Quick Start

### Option 1: Docker Compose (Recommended)

```bash
docker-compose up --build
```

This starts PostgreSQL, Redis, Django backend, Celery worker, Celery beat, and the React frontend.

- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000/api/v1/
- **Admin**: http://localhost:8000/admin/

### Option 2: Manual Setup

#### Prerequisites
- Python 3.12+
- Node.js 22+
- PostgreSQL 14+
- Redis 7+

#### Backend Setup

```bash
# Create and activate virtual environment
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create PostgreSQL database
psql -U postgres -c "CREATE DATABASE playto_payouts;"

# Run migrations
python manage.py migrate

# Seed test data (3 merchants with credit history)
python manage.py seed_data

# Start Django server
python manage.py runserver
```

#### Celery Setup (separate terminals)

```bash
# Terminal 2: Celery Worker
celery -A config worker -l info --pool=solo

# Terminal 3: Celery Beat (periodic retry task)
celery -A config beat -l info
```

#### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start dev server (proxies API to Django)
npm run dev
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/merchants/` | List all merchants |
| GET | `/api/v1/merchants/{id}/` | Merchant details |
| GET | `/api/v1/merchants/{id}/balance/` | Computed balance (DB aggregation) |
| GET | `/api/v1/merchants/{id}/ledger/` | Ledger entries |
| GET | `/api/v1/merchants/{id}/bank-accounts/` | Bank accounts |
| POST | `/api/v1/payouts/` | Create payout (requires `Idempotency-Key` header) |
| GET | `/api/v1/payouts/?merchant_id={id}` | List payouts |
| GET | `/api/v1/payouts/{id}/` | Payout detail |

### Example: Create a Payout

```bash
curl -X POST http://localhost:8000/api/v1/payouts/ \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: $(uuidgen)" \
  -d '{
    "merchant_id": "<MERCHANT_UUID>",
    "amount_paise": 500000,
    "bank_account_id": "<BANK_ACCOUNT_UUID>"
  }'
```

## Running Tests

```bash
python manage.py test payouts -v 2
```

## Production Deployment

The project is equipped with a production-ready Docker configuration using **Gunicorn**, **Nginx**, and **multi-stage builds**.

### 1. Environment Configuration
Create a `.env.prod` file (or set these in your CI/CD):
```env
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=your-secure-random-key
ALLOWED_HOSTS=yourdomain.com,backend
CORS_ALLOWED_ORIGINS=https://yourdomain.com
DB_NAME=playto_payouts
DB_USER=postgres
DB_PASSWORD=your-secure-password
```

### 2. Deploy with Docker Compose
Run the production stack:
```bash
docker-compose -f docker-compose.prod.yml up --build -d
```

This will:
- Build the React frontend into optimized static files.
- Start **Nginx** to serve the frontend on port 80 and proxy `/api` requests to the backend.
- Start **Gunicorn** for the Django backend.
- Collect static files for the Django admin and DRF interface.
- Run database migrations automatically.

### 3. Scaling
- **Celery Workers**: Scale workers by running `docker-compose -f docker-compose.prod.yml up -d --scale celery-worker=3`.
- **Backend**: Gunicorn is configured with 4 workers by default in the compose file.

## Deploying to Render

This project includes a `render.yaml` file for "one-click" deployment using Render Blueprints.

1.  **Push your code** to a GitHub or GitLab repository.
2.  **Create a New Blueprint** on Render:
    - Go to [dashboard.render.com](https://dashboard.render.com)
    - Click **New +** > **Blueprint**
    - Connect your repository.
3.  **Approve the Plan**: Render will automatically detect the `render.yaml` and provision:
    - PostgreSQL Database
    - Redis (for Celery)
    - Django Backend (Gunicorn)
    - React Frontend (Nginx)
    - Celery Worker & Beat
4.  **Update Environment Variables**:
    - After the first deploy starts, you may need to update `ALLOWED_HOSTS` and `CORS_ALLOWED_ORIGINS` in the Render dashboard for the Backend service to match your generated URLs.

Key tests:
- **Concurrency**: Two simultaneous ₹60 payouts on ₹100 balance — exactly one succeeds
- **Idempotency**: Duplicate key returns same response, no duplicate payout
- **State Machine**: Illegal transitions (completed→pending, failed→completed) are blocked
- **Balance Integrity**: credits - debits = available + held (invariant check)

## Tech Stack

- **Backend**: Django 6.0 + Django REST Framework 3.17
- **Frontend**: React 19 + Tailwind CSS v4 + Vite 8
- **Database**: PostgreSQL (BigIntegerField for paise, SELECT FOR UPDATE)
- **Queue**: Celery 5.6 + Redis 7
- **Containerization**: Docker Compose

## Project Structure

```
Playto/
├── config/              # Django project settings
│   ├── settings.py      # PostgreSQL, Celery, CORS config
│   ├── celery.py        # Celery app initialization
│   └── urls.py          # Root URL routing
├── payouts/             # Core payout engine
│   ├── models.py        # Merchant, BankAccount, LedgerEntry, Payout, IdempotencyKey
│   ├── services/        # Business logic layer
│   │   ├── __init__.py  # Ledger balance calculation (DB aggregation)
│   │   └── payout_service.py  # Payout creation with SELECT FOR UPDATE
│   ├── tasks.py         # Celery tasks (process_payout, retry_stuck)
│   ├── serializers.py   # DRF serializers
│   ├── views.py         # API viewsets
│   ├── urls.py          # API URL routing
│   ├── tests.py         # Concurrency, idempotency, state machine tests
│   └── management/commands/seed_data.py
├── frontend/            # React dashboard
│   ├── src/
│   │   ├── App.jsx      # Main dashboard layout
│   │   ├── api.js       # Backend API client
│   │   ├── utils.js     # Formatting utilities
│   │   ├── hooks/       # Custom React hooks
│   │   └── components/  # UI components
│   └── vite.config.js   # Vite + API proxy config
├── docker-compose.yml   # Full stack orchestration
├── EXPLAINER.md         # Technical decisions explained
└── README.md            # This file
```
