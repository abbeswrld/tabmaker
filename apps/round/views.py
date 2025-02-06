from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.urls import reverse_lazy
from django_telegrambot.apps import DjangoTelegramBot

from apps.tournament.views import access_by_status, check_tournament, _show_message
from apps.tournament.logic import 
    generate_next_round, \
    get_rooms_from_last_round, \
    publish_last_round, \
    get_tab, \
    check_games_results_exists
from apps.tournament.messages import MSG_ROUND_NOT_PUBLIC
from apps.tournament.forms import MotionForm, RoundForm, GameForm
from apps.tournament.consts import ROLE_CHAIR, ROLE_CHIEF_ADJUDICATOR, ROLE_WING
from apps.tournament.telegrambot import TabmakerBot

@login_required(login_url=reverse_lazy('account_login'))
@access_by_status(name_page='round_next')
@check_tournament
def next_round(request, tournament):
    if request.method == 'POST':
        motion_form = MotionForm(request.POST)
        round_form = RoundForm(request.POST)
        if motion_form.is_valid() and round_form.is_valid():
            round_obj = round_form.save(commit=False)
            round_obj.motion = motion_form.save()
            error = generate_next_round(tournament, round_obj)
            if error:
                _show_message(request, error)

            return redirect('tournament:edit_round', tournament_id=tournament.id)
    else:
        motion_form = MotionForm()
        round_form = RoundForm()

    return render(
        request,
        'tournament/next_round.html',
        {
            'tournament': tournament,
            'motion_form': motion_form,
            'round_form': round_form,
        }
    )


@access_by_status(name_page='round_show')
def show_round(request, tournament):
    rooms = get_rooms_from_last_round(tournament, True)
    if not rooms or not rooms[0].round.is_public:
        return _show_message(request, MSG_ROUND_NOT_PUBLIC)

    return render(
        request,
        'tournament/show_round.html',
        {
            'rooms': rooms
        },
    )


@login_required(login_url=reverse_lazy('account_login'))
@access_by_status(name_page='round_next')
def presentation_round(request, tournament):
    rooms = get_rooms_from_last_round(tournament, True)
    return render(
        request,
        'tournament/presentation_round.html',
        {
            'rooms': rooms,
            'round': None if not rooms else rooms[0].round
        },
    )


@login_required(login_url=reverse_lazy('account_login'))
@access_by_status(name_page='round_edit')
def publish_round(request, tournament):
    try:
        cur_round = publish_last_round(tournament)
    except Exception as exception :
        return _show_message(request, exception)

    try:
        from . telegrambot import TabmakerBot
        from django_telegrambot.apps import DjangoTelegramBot

        rooms = get_rooms_from_last_round(tournament)
        TabmakerBot.send_round_notifications(DjangoTelegramBot.getBot(), cur_round, rooms),
    except Exception as exception :
        logging.error(exception)

    return redirect('tournament:show', tournament_id=tournament.id)


@login_required(login_url=reverse_lazy('account_login'))
@access_by_status(name_page='round_edit')
def edit_round(request, tournament):
    forms = []
    all_is_valid = True
    rooms = list(get_rooms_from_last_round(tournament))
    for room in rooms:
        if request.method == 'POST':
            form = GameForm(request.POST, instance=room.game, prefix=room.game.id)
            all_is_valid &= form.is_valid()
            if form.is_valid():
                form.save()
                room.place_id = form.get_place_id()
                room.save()
        else:
            form = GameForm(instance=room.game, prefix=room.game.id)
            form.init_place(room.place)

        form.game = room.game
        forms.append(form)

    if all_is_valid and request.method == 'POST':
        return redirect('tournament:show', tournament_id=tournament.id)

    team_results = {}
    for team_result in get_tab(tournament):
        team_results[team_result.team.id] = team_result.sum_points()

    return render(
        request,
        'tournament/edit_round.html',
        {
            'tournament': tournament,
            'forms': forms,
            'warning': check_games_results_exists(list(map(lambda x: x.game, rooms))),
            'adjudicators': tournament.get_users([ROLE_CHAIR, ROLE_CHIEF_ADJUDICATOR, ROLE_WING]),
            'places': tournament.place_set.filter(is_active=True),
            'team_results': team_results,
        }
    )


@login_required(login_url=reverse_lazy('account_login'))
@access_by_status(name_page='round_result')
def result_round(request, tournament):
    is_admin = user_can_edit_tournament(tournament, request.user)
    chair = None if is_admin else request.user
    rooms = get_rooms_from_last_round(tournament, False, chair)
    is_playoff = tournament.status == STATUS_PLAYOFF
    is_final = is_playoff and get_rooms_from_last_round(tournament).count() == 1

    if not is_admin and not rooms:
        return _show_message(request, MSG_NO_ACCESS_IN_RESULT_PAGE)

    is_valid, forms = _get_or_check_round_result_forms(request, rooms, is_admin, is_playoff, is_final)

    if is_valid and request.method == 'POST':
        return redirect('tournament:show', tournament_id=tournament.id)

    return render(
        request,
        'tournament/result_round.html',
        {
            'tournament': tournament,
            'forms': forms,
            'is_playoff': is_playoff,
            'is_final': is_final,
            'result_template': 'tournament/playoff_result_team.html' if is_playoff else 'tournament/result_team.html',
        }
    )


@login_required(login_url=reverse_lazy('account_login'))
@access_by_status(name_page='round_remove')
def remove_round(request, tournament):
    if remove_last_round(tournament):
        return redirect('tournament:show', tournament_id=tournament.id)
    elif tournament.status == STATUS_PLAYOFF:
        return _show_message(request, MSG_NO_ROUND_IN_PLAYOFF_FOR_REMOVE)
    else:
        return _show_message(request, MSG_ROUND_NOT_EXIST)