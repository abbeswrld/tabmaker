import os
import dotenv

if not int(os.getenv('ENVIRONMENT_LOADED', 0)):
    # TODO Убрать после правильной настройки прода, пока так

    dotenv_path = dotenv.find_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env'))

    # Загружаем переменные из .env, если он найден
    if dotenv_path:
        dotenv.load_dotenv(dotenv_path)

from DebatesTournament.settings.defaults import *
from DebatesTournament.settings.database import *
from DebatesTournament.settings.allauth import *
from DebatesTournament.settings.smtp_email import *
from DebatesTournament.settings.static import *
from DebatesTournament.settings.telegram_bot import *
from DebatesTournament.settings.detact_language import *
from DebatesTournament.settings.debug import *
from DebatesTournament.settings.logging import *
