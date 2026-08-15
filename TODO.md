# Warsha — build tracker

Hackathon slice: **customer chat → Kareem quote → Paymob pay → work → pickup → completed**.

Full product spec: [AGENTS.md](AGENTS.md).

---

## Done

- [x] **AGENTS.md** — product & engineering contract
- [x] **Batch 1 — Foundation**
  - [x] Django apps: `accounts`, `catalog`, `jobs`, `payments`
  - [x] Core models: `Customer`, `Label`, `Diagnostic`, `DiagnosticStep`, `Order`, `OrderStep`, `Conversation`, `Message`, `Payment`
  - [x] Settings: `Africa/Cairo`, Arabic default, media uploads, DRF installed
  - [x] `requirements.txt` cleaned (removed bogus `django-rest-framework` package)
  - [x] Django admin for all models
  - [x] `python manage.py seed_warsha` — Kareem user + sample diagnostics
  - [x] `jobs.services.snapshot_diagnostic_on_order` — quote snapshot helper (for Batch 3)
  - [x] URL stubs for all AGENTS.md routes (501 until implemented)
  - [x] `.env.example`

---

## In scope (next batches — ~2h demo)

### Batch 2 — Customer (target: ~20 min)

- [x] Phone session gate on `/` (no OTP)
- [x] Chat UI — text message creates `Order` + `Message` (dumb intake, no AI)
- [x] Order detail `/orders/<id>/` — messages, status, agreement when quoted

### Batch 3 — Kareem portal (target: ~25 min) — **done**

- [x] Staff login `/k/login/`
- [x] Requests list `/k/`
- [x] Request detail `/k/requests/<id>/` — view messages
- [x] Quote action — pick diagnostic, call `snapshot_diagnostic_on_order`

### Batch 4 — Paymob (target: ~30 min) — **done**

- [x] `POST /api/orders/<id>/checkout/` — Intention + checkout URL
- [x] Pay button on customer order detail when `quoted`
- [x] `POST /webhooks/paymob/` — HMAC-SHA-512, idempotent, `quoted` → `in_progress`
- [x] Cloudflare tunnel for local webhook (teammate or ngrok) — see NOTES.md
- [x] Dev fallback: manual “confirm paid” if tunnel fails live

### Batch 5 — Status + demo polish (target: ~15 min) — **done**

- [x] Kareem “Mark ready for pickup” when `in_progress`
- [x] System message to customer
- [x] Paymob readiness (`check_paymob`, `/health/`, UI when keys missing)
- [x] Premium UI sprint — Tailwind CDN + hero home, WhatsApp chat, agreement ticket
- [x] Arabic status labels (`jobs/templatetags/warsha_ui.py`)
- [x] End-to-end demo script in NOTES.md (including keys-arrival checklist)

### Batch 6 — Operational depth — **done**

- [x] Audio intake on chat + playback in message threads
- [x] Per-step completion (`complete_order_step`) + Kareem **إتمام** UI
- [x] Remaining ETA + step checkmarks on customer order detail
- [x] Customer orders list `/orders/`
- [x] Mark `completed` when car collected
- [x] HTMX poll on active order threads (customer + Kareem)
- [x] NOTES.md judge path through `completed`

### Batch 7 — AI intake — **done**

- [x] `ai` app + `cursor-sdk` adapter (`ai/llm.py`)
- [x] Labeler (new / existing / irrelevant) + Tagger (label M2M)
- [x] Intake conversation + `process_chat_message` with dumb fallback
- [x] Persistent chat thread on `/chat/` with order links
- [x] Label chips on Kareem requests list + detail

---

## Later (post-demo / v1)

- [ ] Full i18n (`makemessages`, `{% trans %}`)
- [ ] WhatsApp channel
- [ ] LangGraph graphs (optional upgrade from one-shot prompts)
- [ ] Transaction inquiry fallback for stuck payments

---

## Quick commands

```bash
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_warsha
python manage.py runserver
```

**Kareem admin:** http://127.0.0.1:8000/admin/ — `kareem` / `warsha2026` (after seed)

**Health:** http://127.0.0.1:8000/health/
