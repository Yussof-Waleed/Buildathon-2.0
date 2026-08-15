# Warsha — demo notes

## 60-second judge path

1. Open tunnel URL (or `http://127.0.0.1:8000/`) → **hero home** with ورشة title and persona tiles
2. Tap **عميل** → enter phone → **chat** → send text or audio (mic icon)
3. **With `CURSOR_API_KEY`:** try **مرحبا** (Arabic reply, no order) vs engine problem (new order + labels on Kareem list)
4. Second tab: **كريم** → login `kareem` / `warsha2026` → **Overview** (`/k/`) or **الطلبات** → open request → see **label chips** → listen to audio → **quote**
5. Customer order page → **agreement ticket** + **ادفع** (or waiting note if keys missing)
6. If Paymob keys unavailable: Kareem **تأكيد الدفع (تجريبي)** → order `in_progress`
7. Kareem **إتمام** per step (or **جاهز للاستلام** shortcut) → customer sees progress + ETA + live messages (HTMX)
8. Kareem **تم الاستلام** → order `completed`
9. Customer **طلباتي** (`/orders/`) shows full history

**Without `CURSOR_API_KEY`:** every chat message still creates an order and redirects to order detail (dumb fallback).

## AI intake (Batch 7)

- Set `CURSOR_API_KEY` in `.env` and `pip install cursor-sdk`
- Chat stays on `/chat/` with thread history (intake conversation)
- Labeler routes: `new_request`, `existing_order`, `irrelevant`
- Tagger assigns labels on new orders — visible on `/k/requests/`

## When keys arrive (5 steps)

1. Paste `PAYMOB_SECRET_KEY` + `PAYMOB_PUBLIC_KEY` (Test mode) into `.env`
   - Secret: `egy_sk_test_…` — **not** the API key (move API key to `PAYMOB_API_KEY`)
   - Public: `egy_pk_test_…`
2. `python manage.py check_paymob` → `ready: true`
3. Restart `runserver` + keep `cloudflared` running
4. Quote order → **ادفع** → Paymob test card
5. Refresh order → `in_progress` → complete steps → **تم الاستلام**

Keep **تأكيد الدفع (تجريبي)** as Plan B if webhook is slow during demo.

## Paymob readiness

```bash
python manage.py check_paymob
curl http://127.0.0.1:8000/health/
```

`/health/` includes `paymob.ready`, `missing`, and `warnings`.

## Paymob (when onboarded)

- Set `PAYMOB_SECRET_KEY` (`egy_sk_test_…`), `PAYMOB_PUBLIC_KEY`, `PAYMOB_HMAC_SECRET`
- Tunnel URL in `.env`: `SITE_URL`, `PAYMOB_NOTIFICATION_URL`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`
- Webhook: `POST /webhooks/paymob/` — HMAC verified, idempotent

## Dev commands

```bash
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate && python manage.py seed_warsha
python manage.py check_paymob
python manage.py runserver
# Optional tunnel:
cloudflared tunnel --url http://127.0.0.1:8000
```

## Kareem credentials (seed)

- Username: `kareem`
- Password: `warsha2026`
