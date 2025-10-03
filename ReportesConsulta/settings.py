"""
Django settings for reportes_project project.
"""

from pathlib import Path
import os

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-your-dev-key-here')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DEBUG', 'False') == 'True'

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1,reportes,*').split(',')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'reportes',  # Tu app correcta
    'corsheaders',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Para servir archivos estáticos
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'ReportesConsulta.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'ReportesConsulta.wsgi.application'

# Database - Conecta a la misma BD que tu backend principal
DATABASE_URL = os.environ.get('DATABASE_URL')

if DATABASE_URL:
    # PRODUCCIÓN (Render) - Usa la misma BD que tu backend principal
    import dj_database_url
    DATABASES = {
        'default': dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=600,
            ssl_require=True
        )
    }
else:
    # DESARROLLO LOCAL
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ.get('POSTGRES_DB', 'SportCareIdet'),
            'USER': os.environ.get('POSTGRES_USER', 'postgres'),
            'PASSWORD': os.environ.get('POSTGRES_PASSWORD', 'postgres'),
            'HOST': os.environ.get('POSTGRES_HOST', 'localhost'),
            'PORT': os.environ.get('POSTGRES_PORT', '5432'),
        }
    }

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'es-mx'
TIME_ZONE = 'America/Mexico_City'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# CORS Configuration
CORS_ALLOWED_ORIGINS = os.environ.get('CORS_ALLOWED_ORIGINS', 'http://localhost:5173').split(',')
CORS_ALLOW_ALL_ORIGINS = os.environ.get('CORS_ALLOW_ALL_ORIGINS', 'False') == 'True'

# API Configuration - URLs dinámicas para comunicarse con tu backend principal
BACKEND_HOST = os.environ.get('BACKEND_HOST', 'localhost')
BACKEND_PORT = os.environ.get('BACKEND_PORT', '8000')
BACKEND_PROTOCOL = os.environ.get('BACKEND_PROTOCOL', 'http')

# Construir URL base (sin puerto si es 443 en HTTPS o 80 en HTTP)
if (BACKEND_PROTOCOL == 'https' and BACKEND_PORT == '443') or (BACKEND_PROTOCOL == 'http' and BACKEND_PORT == '80'):
    API_BASE_URL = f'{BACKEND_PROTOCOL}://{BACKEND_HOST}'
else:
    API_BASE_URL = f'{BACKEND_PROTOCOL}://{BACKEND_HOST}:{BACKEND_PORT}'

# URLs de APIs del backend principal (si necesitas consumir sus endpoints)
API_CITAS = f'{API_BASE_URL}/Modulos/Citas/'
API_PROFESIONALES = f'{API_BASE_URL}/Catalogos/Profesionales-Salud/'
API_ATLETAS = f'{API_BASE_URL}/Catalogos/Atletas/'
API_AREAS = f'{API_BASE_URL}/Catalogos/Areas/'
API_REPORTES = f'{API_BASE_URL}/Reportes/'
API_CONSULTAS = f'{API_BASE_URL}/Consultas/'