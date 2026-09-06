# Kisan Setu Procurement Platform

Kisan Setu (किसान सेतु / किसान सेतू) is a farmer booking and mandi queue platform with live procurement status updates.

## Run locally

1. Start PostgreSQL and Redis:

   ```powershell
   docker compose up -d
   ```

2. Create and activate a virtual environment, then install dependencies:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

3. Start the API:

   ```powershell
   uvicorn backend.main:app --reload
   ```

The API is available at `http://localhost:8000` and its OpenAPI UI is at `/docs`.

4. Start the frontend in a second terminal. Node.js 18+ is required:

   ```powershell
   Set-Location frontend
   npm install
   npm run dev
   ```

The frontend is available at `http://localhost:5173`.

5. Add deterministic Kisan Setu demo data:

   ```powershell
   python -m backend.seed_data
   ```

This creates 24 clearly synthetic Madhya Pradesh demo procurement centers across nine districts, synthetic demo slots, required documents, demo accounts, and procurement records. The seed is repeatable and will not create duplicate centers, slots, accounts, or tokens.

The demo seed currently includes nine Madhya Pradesh districts and multiple clearly synthetic procurement centers per district. SMS notifications use `SMS_MODE=demo` and `SMS_PROVIDER=mock` by default: messages are logged and stored in the existing notification feed without contacting a real provider.

Demo accounts:

- Farmer: `+910000000001` / `Kisan@2026`
- Officer: `+910000000002` / `Mandi@2026`

Operational values are synthetic demo data. See [DATA_SOURCES.md](DATA_SOURCES.md) for the source distinction.

## Database migrations

The schema is managed with Alembic. For an existing database created by the original app, run:

```powershell
alembic upgrade head
```

The first migration preserves the original `IN_YARD`, `WEIGHING`, and `COMPLETED` token states while adding the procurement lifecycle schema. It is intentionally forward-only because existing procurement records must not be removed by a downgrade.

## Booking endpoint

`POST /api/slots/{slot_id}/book`

```json
{
  "farmer_phone": "+919876543210",
  "crop_type": "Wheat",
  "expected_tonnage": 2.5
}
```

The endpoint locks the slot row with PostgreSQL `FOR UPDATE`, checks remaining tonnage, increments `booked_tonnage`, and creates the booking token in the same transaction.

## Live queue API

- `GET /api/slots` lists slots available to the booking flow.
- `GET /api/tokens` loads the operator queue.
- `PATCH /api/tokens/{token_id}/status` advances a token by one stage.
- `WS /ws/queue` streams status changes through Redis Pub/Sub.

The frontend has two views: **Mandi control** for the live Kanban queue and **Farmer booking** for creating a slot booking.
