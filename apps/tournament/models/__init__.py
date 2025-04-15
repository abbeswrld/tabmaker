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


from apps.tournament.models.language import Language
from apps.tournament.models.motion import Motion
from apps.team.models import Team
from apps.tournament.models.game import \
    Game, \
    GameResult, \
    PlayoffResult, \
    QualificationResult

from apps.tournament.models.tournament import \
    TeamTournamentRel, \
    Tournament, \
    TournamentRole, \
    TournamentStatus, \
    UserTournamentRel

from apps.place.models import Place
from apps.round.models import Round
from apps.tournament.models.room import Room
from apps.tournament.models.page import \
    AccessToPage, \
    Page

from apps.custom_form.models import \
    CustomForm, \
    CustomFieldAlias, \
    CustomFormAnswers, \
    CustomFormType, \
    CustomQuestion, \
    FeedbackAnswer

from apps.tournament.models.bot_users import BotChat, BotUsers
