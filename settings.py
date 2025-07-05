from pathlib import Path
import os

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "REMOVED"

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['*']

# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    'rest_framework.authtoken',
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",  # Required for django-allauth
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    # Third-party authentication apps
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'allauth.socialaccount.providers.facebook',
    # Local apps
    'users',
    'labs',
    'billing',
    'test_app',
    'django.contrib.humanize',  # For formatting numbers in templates
    'pharmacy',
    'appointment',
    'scheduling',
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    # Add allauth middleware
    'allauth.account.middleware.AccountMiddleware',
]

ROOT_URLCONF = "RxBackend.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, 'templates')],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "notifications.context_processors.notifications",
            ],
            'libraries': {
                'custom_filters': 'users.templatetags.custom_filters',
            },
        },
    },
]

WSGI_APPLICATION = "RxBackend.wsgi.application"


# Database
# https://docs.djangoproject.com/en/5.1/ref/settings/#databases

DATABASES = {
   'default': {
       'ENGINE': 'django.db.backends.postgresql',
       'NAME': 'rxdoctor',
       'USER': 'postgres',
       'PASSWORD': 'admin',
       'HOST': 'localhost',
       'PORT': '5432',
   },
#    'default': {
#        'ENGINE': 'django.db.backends.postgresql',
#        'NAME': 'rxdoctor',
#        'USER': 'REMOVED ',
#        'PASSWORD': 'REMOVED',
#        'HOST': 'REMOVED',
#        'PORT': 'REMOVED',
#    }
}

# Add the new PostgreSQL configuration
#DATABASES = {
#    'default': {
#        'ENGINE': 'django.db.backends.postgresql',
#        'NAME': 'rxdoctor',
#        'USER': 'postgres',
#        'PASSWORD': 'admin',  # the password you set
#        'HOST': 'localhost',
#        'PORT': '5432',
#    }
#}

# Make sure there are no other DATABASES settings in the file


# Password validation
# https://docs.djangoproject.com/en/5.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.1/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.1/howto/static-files/

STATIC_URL = "/static/"

STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")

STATICFILES_DIRS = [
    os.path.join(BASE_DIR, "static"),
]

STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
]

# Default primary key field type
# https://docs.djangoproject.com/en/5.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
}



CORS_ALLOW_ALL_ORIGINS = True  # For development only
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

# REST Framework settings
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',  # Added for allauth compatibility
    ),
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

 # For development only
ALLOWED_HOSTS = ['*']



LOGIN_URL = 'users:login'  # URL where users will be redirected if login is required
LOGIN_REDIRECT_URL = 'users:dashboard'  # URL to redirect after successful login
LOGOUT_REDIRECT_URL = 'users:login'  # URL to redirect after logout


# Add media settings
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Custom User Model
AUTH_USER_MODEL = 'users.User'

# django-allauth settings
AUTHENTICATION_BACKENDS = [
    # Needed to login by username in Django admin
    'django.contrib.auth.backends.ModelBackend',
    # allauth specific authentication methods
    'allauth.account.auth_backends.AuthenticationBackend',
    # Firebase authentication
    'users.firebase_auth.FirebaseAuthBackend',
]

SITE_ID = 1

# allauth settings
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_AUTHENTICATION_METHOD = 'email'
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_EMAIL_VERIFICATION = 'mandatory'
ACCOUNT_ADAPTER = 'users.adapters.CustomAccountAdapter'
SOCIALACCOUNT_ADAPTER = 'users.adapters.CustomSocialAccountAdapter'
ACCOUNT_UNIQUE_EMAIL = True

# Social account providers settings
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': [
            'profile',
            'email',
        ],
        'AUTH_PARAMS': {
            'access_type': 'online',
        }
    },
    'facebook': {
        'METHOD': 'oauth2',
        'SCOPE': ['email', 'public_profile'],
        'AUTH_PARAMS': {'auth_type': 'reauthenticate'},
        'FIELDS': [
            'id',
            'email',
            'name',
            'first_name',
            'last_name',
            'picture',
        ],
        'EXCHANGE_TOKEN': True,
        'VERIFIED_EMAIL': False,
    }
}

# Firebase Authentication
FIREBASE_AUTH = {
    'SERVICE_ACCOUNT_KEY_FILE': os.path.join(BASE_DIR, 'firebase-service-account.json'),
}
