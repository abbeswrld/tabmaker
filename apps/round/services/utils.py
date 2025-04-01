from apps.tournament.consts import ROLE_CHAIR, ROLE_CHIEF_ADJUDICATOR
from apps.profile.models import User
from apps.place.models import Place

def get_available_adjudicator(tournament):
    adjudicators = tournament.get_users([ROLE_CHAIR, ROLE_CHIEF_ADJUDICATOR])

    from apps.tournament.models import Game
    busy_adjudicators = Game.objects.filter(
        room__round=tournament.cur_round
    ).values_list('chair_id', flat=True)

    available = adjudicators.exclude(id__in=busy_adjudicators)
    
    if not available.exists():
        return adjudicators.order_by('?').first()
    
    return available.order_by('?').first()

def get_available_place(tournament):
    places = tournament.place_set.filter(is_active=True)

    from apps.tournament.models import Room
    busy_places = Room.objects.filter(
        round=tournament.cur_round
    ).exclude(place__isnull=True).values_list('place_id', flat=True)

    available = places.exclude(id__in=busy_places)
    
    if not available.exists():
        return places.order_by('?').first()
    
    return available.order_by('?').first()