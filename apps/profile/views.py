from django.shortcuts import render, redirect, get_object_or_404
from django.http import Http404
from django.contrib.auth.decorators import login_required
from django.urls import reverse_lazy
from django.db.models import Q, Count, Case, When, IntegerField
from django.views.decorators.csrf import ensure_csrf_cookie
from django_telegrambot.apps import DjangoTelegramBot

from apps.profile.models import User
from apps.tournament.models.tournament import TeamTournamentRel, Tournament
from apps.profile.models import TelegramToken
from apps.tournament.consts import ADJUDICATOR_ROLES, ROLE_MEMBER, ROLE_ADMIN, ROLE_OWNER
from apps.tournament.forms import EditForm
from apps.tournament.utils import paging

def show_profile(request, user_id):
    try:
        # not use get_object_or_404 because need select_related
        users = User.objects
        for name in ['university', 'university__city', 'university__country']:
            users = users.select_related(name)
        user = users.get(pk=user_id)
    except ObjectDoesNotExist:
        raise Http404('User with id %s not exist' % user_id)

    teams_rel = TeamTournamentRel.objects.filter(Q(team__speaker_1=user) | Q(team__speaker_2=user))
    for name in ['role', 'team__speaker_2', 'team__speaker_1', 'tournament']:
        teams_rel = teams_rel.select_related(name)

    adjudicators_rel = user.usertournamentrel_set.filter(role__in=ADJUDICATOR_ROLES)
    for name in ['role', 'tournament']:
        adjudicators_rel = adjudicators_rel.select_related(name)

    return render(
        request,
        'account/show.html',
        {
            'user': user,
            'is_owner': request.user.is_authenticated and user == request.user,
            'teams_objects': teams_rel,
            'adjudicators_objects': adjudicators_rel,
        }
    )


def edit_profile(request):
    if not request.user.is_authenticated:
        raise Http404
    is_success = False
    if request.method == 'POST':
        form = EditForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            is_success = True
    else:
        form = EditForm(instance=request.user)
    return render(
        request,
        'account/signup.html',
        {
            'is_edit_form': True,
            'is_success': is_success,
            'user': request.user,
            'form': form,
        }
    )

@login_required(login_url=reverse_lazy('account_login'))
def connect_telegram(request):
    from django_telegrambot.apps import DjangoTelegramBot

    return redirect('https://telegram.me/%s?start=%s' % (
        DjangoTelegramBot.getBot().username,
        TelegramToken.generate(request.user).value
    ))


def show_tournaments_of_user(request, user_id):
    user = get_object_or_404(User, pk=user_id)

    tournaments = Tournament.objects.select_related('status').annotate(
        m_count=Count(Case(
            When(teamtournamentrel__role=ROLE_MEMBER, then=1),
            output_field=IntegerField()
        ))
    ).filter(
        usertournamentrel__user=user,
        usertournamentrel__role__in=[ROLE_ADMIN, ROLE_OWNER]
    ).order_by('-start_tour')

    return render(
        request,
        'main/main.html',
        {
            'is_main_page': False,
            'is_owner': request.user == user,
            'objects': paging(request, tournaments)
        }
    )


@ensure_csrf_cookie
def show_teams_of_user(request, user_id):
    user = get_object_or_404(User, pk=user_id)

    teams_rel = TeamTournamentRel.objects.filter(Q(team__speaker_1=user) | Q(team__speaker_2=user))
    for name in ['role', 'team__speaker_2', 'team__speaker_1', 'tournament']:
        teams_rel = teams_rel.select_related(name)
    return render(
        request,
        'account/teams_of_user.html',
        {
            'is_owner': request.user == user,
            'objects': teams_rel,
        }
    )


@ensure_csrf_cookie
def show_adjudicator_of_user(request, user_id):
    user = get_object_or_404(User, pk=user_id)

    adjudicators_rel = user.usertournamentrel_set.filter(role__in=ADJUDICATOR_ROLES)
    for name in ['role', 'tournament']:
        adjudicators_rel = adjudicators_rel.select_related(name)

    return render(
        request,
        'account/adjudicators_of_user.html',
        {
            'is_owner': request.user == user,
            'objects': adjudicators_rel,
        }
    )