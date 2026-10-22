# Django Deployment Checklist

This checklist describes the Django application in `django_store`. It does not deploy the application automatically.

## Requirements

- Python 3.10 or newer
- A supported production WSGI/ASGI host
- HTTPS and a persistent location for uploaded media
- A production database configured in `django_store/config/settings.py`

## Prepare the application

1. Keep the repository outside the public document root. Do not expose `.env`, the database file, or uploaded media through an unprotected web directory.
2. From the repository root, install dependencies with `python -m pip install -r requirements-python.txt`.
3. Configure `DJANGO_SECRET_KEY` with a unique random secret, set `DJANGO_DEBUG=false`, and list the hostnames in `DJANGO_ALLOWED_HOSTS`.
4. Set `API_KEY` and `COST_API_KEY` when using the transaction API and Komerce/RajaOngkir endpoints. Never commit or expose these values.
5. Back up existing data. The Django schema is separate; migrations do not import the former application's database.
6. Change to `django_store/`, run `python manage.py migrate`, and create an administrator with `python manage.py createsuperuser`.
7. From `django_store/`, run `python manage.py collectstatic` and configure the host to serve collected static files. Configure persistent private storage for payment proof, profile, and product uploads.
8. Serve the project with the hosting provider's production WSGI/ASGI server. Do not use Django's `runserver` in production.
9. Verify sign-in, registration, checkout, admin access, and API authorization after deployment.
10. Configure database backups, log rotation, and a process for rotating API/provider credentials.

SQLite is configured by default for local development. Review the database, media storage, HTTPS, and backup configuration before production use. Do not share `.env`, database credentials, API keys, or administrator credentials when requesting deployment help.
