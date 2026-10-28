# Certification Generation Portal

A Django portal for issuing and managing course-completion and achievement certificates.
It provides an admin portal (students, courses, enrollments, attendance, approvals,
certificates, organization settings) and a student portal (dashboard, my courses,
attendance, my certificates, profile), built with Django templates, HTML, CSS and
vanilla JavaScript, and backed by SQLite.

**Stack:** Python · Django · HTML/CSS/JavaScript · SQLite · ReportLab

## Features

- **Admin portal** — dashboard, student records, courses, enrollments, attendance,
  completion approvals, certificate issuance, organization settings.
- **Student portal** — dashboard, my courses, attendance, my certificates, profile.
- **Certificates** — completion and achievement certificate templates, rendered
  server-side to PDF with ReportLab.
- **Authentication** — Django's built-in auth with admin and student login screens.
- **Responsive UI** — component-based templates (`base`, sidebar, topbar, modals,
  notifications) with dedicated CSS/JS under `myportalapp/static/`.

## Project layout

```
manage.py               Django entry point
portal/                 Project package (settings, urls, wsgi, asgi)
myportalapp/            Application package
  templates/            admin / student / certificates / components templates
  static/               css, js and images
  migrations/           Database migrations
  tests.py              Application tests
requirements.txt        Python dependencies
.env.example            Environment variable template
```

## Requirements

- Python 3.10 or newer
- `pip` and `venv`

## Setup

### 1. Clone the repository

```bash
git clone <repository-url>
cd Certificateportal
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv
```

Linux / macOS:

```bash
source venv/bin/activate
```

Windows (PowerShell):

```powershell
.\venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Copy the template and adjust the values:

```bash
cp .env.example .env
```

| Variable        | Purpose                                            | Example                          |
| --------------- | -------------------------------------------------- | -------------------------------- |
| `SECRET_KEY`    | Django signing key — generate a fresh random value | `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` |
| `DEBUG`         | `True` locally, `False` in production              | `True`                           |
| `ALLOWED_HOSTS` | Comma-separated hostnames                          | `localhost,127.0.0.1`            |

`.env` is git-ignored and must never be committed. If you do not export the variables
yourself, the application falls back to development-only defaults — set them explicitly
for anything beyond local development.

### 5. Apply database migrations

```bash
python manage.py migrate
```

### 6. Create the administrator

```bash
python manage.py createsuperuser
```

Enter a username, email and password when prompted (choose your own strong password;
do not reuse one from this repository or its documentation).

### 7. Run the development server

```bash
python manage.py runserver
```

- Admin portal: <http://127.0.0.1:8000/admin/>
- Site URLs are defined in `portal/urls.py` and `myportalapp`.

## Running tests

```bash
python manage.py test myportalapp
```

Additional pre-flight checks:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
```

## Certificate generation

- Certificate templates live in `myportalapp/templates/certificates/`
  (`completion_certificate.html` and `achievement_certificate.html`) and are rendered
  from the admin **Certificates** screen, which creates the certificate record and its
  certificate number.
- PDF rendering is performed server-side with **ReportLab** (listed in
  `requirements.txt`); generated files belong under `media/`, which is git-ignored so
  issued certificates are never committed.
- No certificate data or rendering credentials are exposed to the browser.

> **Project status:** The portal backend, models, views, forms, ReportLab PDF rendering
> engine, authentication/authorization layers, and comprehensive test suite are fully
> implemented, integrated with the templates and static UI, and verified.


## Environment and secrets

- Never commit `.env`, real `SECRET_KEY` values, database files or issued certificates.
- `.gitignore` excludes `.env`, `db.sqlite3`, `media/`, logs, virtual environments and
  Python cache files.
- `.env.example` contains placeholder values only.

## License

Not specified.
