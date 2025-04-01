from django.db.models import Q
from apps.team.models import Team
from apps.tournament.models import Game, Room
from .utils import get_available_adjudicator, get_available_place


def create_games_for_round(round_obj):
    real_teams = Team.objects.filter(
        teamtournamentrel__tournament=round_obj.tournament,
        is_fake=False
    ).distinct()

    total_teams = real_teams.count()
    num_fake = (4 - (total_teams % 4)) % 4
    fake_teams = Team.objects.filter(is_fake=True)[:num_fake]
    all_teams = list(real_teams) + list(fake_teams)

    for i in range(0, len(all_teams), 4):
        teams_group = all_teams[i:i+4]
        
        game = Game.objects.create(
            og=teams_group[0],
            oo=teams_group[1],
            cg=teams_group[2],
            co=teams_group[3],
            chair=get_available_adjudicator(round_obj.tournament),
            motion=round_obj.motion,
            date=round_obj.start_time,
        )
        
        Room.objects.create(
            round=round_obj,
            game=game,
            number=i//4 + 1,
            place=get_available_place(round_obj.tournament),
        )