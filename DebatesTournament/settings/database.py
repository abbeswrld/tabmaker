import os

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DATABASE_NAME', 'debates_tournament'),
        'USER': os.getenv('DATABASE_USER', 'tabmaker'),
        'PASSWORD': os.getenv('DATABASE_PASSWORD', '123456'),
        'HOST': os.getenv('DATABASE_HOST', 'host.docker.internal'),
        'PORT': os.getenv('DATABASE_PORT', '5433'),
    }
}
