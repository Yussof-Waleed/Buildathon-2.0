# Warsha — demo notes

## 60-second judge path

1. Open tunnel URL (or `http://127.0.0.1:8000/`) → **hero home** with ورشة title and persona tiles
2. Tap **عميل** → enter phone → **chat** → send text or audio (mic icon)
3. **With `GROQ_API_KEY`:** try **مرحبا** (Arabic reply, no order — stay on `/chat/`) vs engine problem (same chat **binds** to a new order; you land on `/orders/<id>/`)
4. Second tab: **كريم** → login `kareem` / `warsha2026` → **Overview** (`/k/`) or **الطلبات** → open request → **reply in the thread** → see **label chips** → listen to audio → **quote**
5. Customer order page is the dedicated chat (composer at the bottom) → pay from the quote bubble (or waiting note if keys missing)
6. Follow-ups stay on that order chat. A **second unrelated repair** from the same thread **forks** a new chat (parent link on the old thread)
7. If Paymob keys unavailable: Kareem **تأكيد الدفع (تجريبي)** → order `in_progress`
8. Kareem **إتمام** per step (or **جاهز للاستلام** shortcut) → customer sees progress + ETA + live messages (HTMX)
9. Kareem **تم الاستلام** → order `completed`
10. Customer **طلباتي** (`/orders/`) shows full history

**Without `GROQ_API_KEY`:** first repair message **binds** the current chat to an order and redirects to order detail. Later messages on that order append (no extra threads).

## Continual chats

- Unbound `/chat/` is intake. Labeler `new_request` binds **this** conversation to the Order (no copy).
- `/orders/<id>/` and `/k/requests/<id>/` are the same thread with composers for both parties.
- Visiting `/chat/` while an order is open redirects to that order’s chat.
- New repair on a bound thread: child `Conversation.parent` = current; triggering customer message is **moved**.

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

`/health/` includes `paymob.ready`, `missing`, `warnings`, and `groq.configured`.

## Paymob (when onboarded)

- Set `PAYMOB_SECRET_KEY` (`egy_sk_test_…`), `PAYMOB_PUBLIC_KEY`, `PAYMOB_HMAC_SECRET`
- Tunnel URL in `.env`: `SITE_URL`, `PAYMOB_NOTIFICATION_URL` (hosts: `.trycloudflare.com` / `https://*.trycloudflare.com` are always allowed)
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
