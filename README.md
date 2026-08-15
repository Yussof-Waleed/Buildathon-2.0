# Buildathon 2.0

Hackathon project built for **Buildathon 2.0**, organized by [Cursor Egypt](https://www.cursor.com/) and [Paymob](https://paymob.com/).

**Product & engineering contract:** see [AGENTS.md](AGENTS.md) — Warsha (ورشة), the neighbourhood garage OS.

This repo is a Django + Django REST Framework backend, starting from a fresh project scaffold.

## Stack

- Python
- Django
- Django REST Framework
- SQLite (default local database)

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

The app will be available at [http://127.0.0.1:8000/](http://127.0.0.1:8000/).

Django admin: [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/)

## Project structure

```
buildathon2/     # Django project settings and URLs
manage.py        # Django CLI
requirements.txt
```

## Organizers

- **Cursor Egypt**
- **Paymob**
