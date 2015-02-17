"""
Django settings for ponytracker project.

For more information on this file, see
https://docs.djangoproject.com/en/dev/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/dev/ref/settings/

For ponytracker specific settings and their values, see
https://ponytracker.readthedocs.org/
"""

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
import os
BASE_DIR = os.path.dirname(os.path.dirname(__file__))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/dev/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'z(j%f+2sh%v1y!f0r5^eo0)nf)z7r!vm+$6y3d!mtb20y5*s0!'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

TEMPLATE_DEBUG = True

TEMPLATE_DIRS = (
    os.path.join(BASE_DIR, 'templates'),
)

STATICFILES_DIRS = (
    os.path.join(BASE_DIR, 'static'),
)

ALLOWED_HOSTS = []


# Application definition

INSTALLED_APPS = (
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'django.contrib.humanize',
    'django.contrib.sites',

    'bootstrap3_datetime',
    'bootstrap3',
    'colorful',
    'accounts',
    'permissions',
    'tracker',
)

from django import VERSION
MIDDLEWARE_CLASSES = (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
)
if VERSION >= (1, 7):
    MIDDLEWARE_CLASSES += (
        'django.contrib.auth.middleware.SessionAuthenticationMiddleware',
    )
MIDDLEWARE_CLASSES += (
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'tracker.middleware.ProjectMiddleware',
)

ROOT_URLCONF = 'ponytracker.urls'

WSGI_APPLICATION = 'ponytracker.wsgi.application'


# Database
# https://docs.djangoproject.com/en/dev/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}

# Internationalization
# https://docs.djangoproject.com/en/dev/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/dev/howto/static-files/

STATIC_URL = '/static/'

LOGIN_URL = '/login'

LOGIN_REDIRECT_URL = '/'

TEMPLATE_CONTEXT_PROCESSORS = (
    'django.contrib.messages.context_processors.messages',
    'django.contrib.auth.context_processors.auth',
    'django.core.context_processors.request',
    'tracker.context_processors.projects',
    'permissions.context_processors.perm',
)

AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
    'permissions.backends.Backend',
)

SITE_ID = 1

EMAIL_HOST = 'smtp'

#FROM_ADDR = 'ponytracker@example.com'

BASE_URL = 'http://localhost:8000'

BOOTSTRAP3 = {

    # The URL to the jQuery JavaScript file
    #'jquery_url': '//code.jquery.com/jquery.min.js',
    'jquery_url': STATIC_URL + 'js/jquery.min.js',

    # The Bootstrap base URL
    #'base_url': '//netdna.bootstrapcdn.com/bootstrap/3.2.0/',
    'base_url': STATIC_URL,

    # The complete URL to the Bootstrap CSS file
    # (None means derive it from base_url)
    'css_url': None,

    # The complete URL to the Bootstrap CSS file
    # (None means no theme)
    'theme_url': None,

    # The complete URL to the Bootstrap JavaScript file
    # (None means derive it from base_url)
    'javascript_url': None,
}

# Celery configuration
BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'djcelery.backends.database:DatabaseBackend'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'

AUTH_USER_MODEL = 'accounts.User'

RESERVED_PROJECT_URLS = [
    'login', 'logout', 'profile', 'admin', 'django-admin'
]

GROUP_MANAGMENT = True
EXTERNAL_AUTH = False

# Pagination
ITEMS_PER_PAGE = 25
