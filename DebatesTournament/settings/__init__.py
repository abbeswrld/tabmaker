import os
import dotenv

if not int(os.getenv('ENVIRONMENT_LOADED', 0)):
    # TODO Убрать после правильной настройки прода, пока так
   
    dotenv_path = dotenv.find_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env'))

    # Загружаем переменные из .env, если он найден
    if dotenv_path:
        dotenv.load_dotenv(dotenv_path)

from .defaults import *
from .database import *
from .allauth import *
from .smtp_email import *
from .static import *
from .telegram_bot import *
from .detact_language import *
from .debug import *
from .logging import *
