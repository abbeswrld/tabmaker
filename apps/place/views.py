from django.shortcuts import render
from django.http import HttpResponse
from django.urls import reverse
from django.urls import reverse_lazy
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_protect
from django.views.decorators.http import require_POST

from apps.tournament.views import access_by_status
from apps.tournament.consts import ROLE_MEMBER, TEAM_IN_GAME, 
from apps.tournament.messages import MSG_JSON_OK, MSG_JSON_BAD
from apps.tournament.utils import json_response
from apps.tournament.views import ajax_request



@ensure_csrf_cookie
@login_required(login_url=reverse_lazy('account_login'))
@access_by_status(name_page='edit')
def place_list(request, tournament):
    return render(
        request,
        'tournament/place_list.html',
        {
            'is_check_page': request.path == reverse('tournament:place_check', args=[tournament.id]),
            'places_need': tournament.teamtournamentrel_set.filter(role=ROLE_MEMBER).count() // TEAM_IN_GAME,
            'places': tournament.place_set.all(),
            'tournament': tournament,
        }
    )


@csrf_protect
@ajax_request
@login_required(login_url=reverse_lazy('account_login'))
@access_by_status(name_page='edit')
def place_update(request, tournament):
    place_id = request.POST.get('place_id', '')
    is_active = request.POST.get('is_active', '').lower() == 'true'
    if not tournament.place_set.filter(pk=place_id).exists():
        return json_response(MSG_JSON_BAD, 'Нет такой')

    tournament.place_set.filter(pk=place_id).update(is_active=is_active)

    return json_response(
        MSG_JSON_OK, is_active
    )


@csrf_protect
@ajax_request
@login_required(login_url=reverse_lazy('account_login'))
@access_by_status(name_page='edit')
def place_add(request, tournament):
    place_name = request.POST.get('place', '').strip()[:100]  # max length of place name
    place = tournament.place_set.get_or_create(place=place_name, tournament=tournament)
    if not place[1]:
        return json_response(MSG_JSON_BAD, 'уже есть')

    return json_response(
        MSG_JSON_OK, {
            'place_id': place[0].id,
            'name': place[0].place,
        }
    )


@csrf_protect
@ajax_request
@login_required(login_url=reverse_lazy('account_login'))
@access_by_status(name_page='edit')
def place_remove(request, tournament):
    place_id = request.POST.get('id', '')
    if not tournament.place_set.filter(pk=place_id).exists():
        return json_response(MSG_JSON_BAD, 'Нет такой')

    tournament.place_set.filter(pk=place_id).delete()

    return json_response(
        MSG_JSON_OK, 'ok'
    )