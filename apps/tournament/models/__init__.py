#########################
#
# TODO Сделать диаграмму связей
# Models dependence:
#   profile
#   language
#   motion -> language
#   team -> profile
#   game -> team, profile, motion
#   tournament -> team, profile
#   place -> tournament
#   round -> tournament, motion
#   room -> round, place, game
#   page -> tournament
#   custom_form  -> tournament, round, profile
#
#   bot_users -> language
#
#########################

from apps.profile.models import \
    City, \
    Country, \
    University, \
    User, \
    TelegramToken

from . language import Language
from . motion import Motion
from apps.team.models import Team
from . game import \
    Game, \
    GameResult, \
    PlayoffResult, \
    QualificationResult

from . tournament import \
    TeamTournamentRel, \
    Tournament, \
    TournamentRole, \
    TournamentStatus, \
    UserTournamentRel

from apps.place.models import Place
from apps.round.models import Round
from . room import Room
from . page import \
    AccessToPage, \
    Page

from apps.custom_form.models import \
    CustomForm, \
    CustomFieldAlias, \
    CustomFormAnswers, \
    CustomFormType, \
    CustomQuestion, \
    FeedbackAnswer

from . bot_users import BotChat, BotUsers
