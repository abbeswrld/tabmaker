from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.urls import reverse, reverse_lazy
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_protect
from django.http import HttpResponse

from apps.tournament.views import access_by_status, ajax_request, _show_message
from apps.tournament.utils import json_response
from apps.custom_forms.models import CustomForm, CustomQuestion, CustomFormAnswers
from apps.tournament.consts import FORM_REGISTRATION_TYPE, ROLE_TEAM_REGISTERED, TEAM_ROLES, ROLE_MEMBER
from apps.tournament.messages import 
    MSG_TEAM_SUCCESS_REGISTERED_pp, \
    MSG_JSON_OK, \
    MSG_JSON_BAD, \
    MSG_BAD_TEAM_ROLE, \
    MSG_TEAM_ROLE_CHANGE
from .models import Team
from apps.tournament.models.tournament import TeamTournamentRel, TournamentRole
from apps.tournament.imports import TeamImportForm, ImportTeam
from apps.tournament.logic import can_change_team_role



@login_required(login_url=reverse_lazy('account_login'))
@access_by_status(name_page='team/adju. registration')
def registration_team(request, tournament):
    from .registration_forms import \
        CustomTeamRegistrationForm, \
        TeamWithSpeakerRegistrationForm

    custom_form = CustomForm.objects.filter(tournament=tournament, form_type=FORM_REGISTRATION_TYPE).first()
    if custom_form:
        RegistrationForm = CustomTeamRegistrationForm
        questions = CustomQuestion.objects.filter(form=custom_form).select_related('alias').order_by('position')
    else:
        RegistrationForm = TeamWithSpeakerRegistrationForm
        questions = None

    if request.method == 'POST':
        team_form = RegistrationForm(tournament, questions, request.POST)
        if team_form.is_valid():
            team = team_form.save(speaker_1=request.user)
            TeamTournamentRel.objects.create(
                team=team,
                tournament=tournament,
                role=ROLE_TEAM_REGISTERED
            )
            if custom_form:
                custom_form_answers = CustomFormAnswers.objects.create(form=custom_form)
                custom_form_answers.set_answers(team_form.get_answers(questions))
                custom_form_answers.save()

            return _show_message(request, MSG_TEAM_SUCCESS_REGISTERED_pp % (team.name, tournament.name))

    else:
        team_form = RegistrationForm(tournament, questions, initial={'speaker_1': request.user.email})

    return render(
        request,
        'tournament/registration_new.html',
        {
            'title': 'Регистрация команды',
            'submit_title': 'Участвовать',
            'action_url': 'tournament:registration_team',
            'form': team_form,
            'tournament': tournament,
        }
    )


@login_required(login_url=reverse_lazy('account_login'))
@access_by_status(name_page='team/adju. add')
def add_team(request, tournament):
    from apps.tournament.registration_forms import TeamRegistrationForm

    saved_team = None
    if request.method == 'POST':
        team_form = TeamRegistrationForm(tournament, request.POST)
        if team_form.is_valid():
            team = team_form.save()
            TeamTournamentRel.objects.create(
                team=team,
                tournament=tournament,
                role=ROLE_TEAM_REGISTERED
            )
            saved_team = team.name
            team_form = TeamRegistrationForm(tournament)
    else:
        team_form = TeamRegistrationForm(tournament)

    return render(
        request,
        'tournament/registration.html',
        {
            'form': team_form,
            'tournament': tournament,
            'show_speaker_1': True,
            'saved_team': saved_team,
        }
    )


@login_required(login_url=reverse_lazy('account_login'))
@access_by_status(name_page='team/adju. add')
def import_team(request, tournament):
    

    message = ''
    results = []
    import_form = TeamImportForm(request.POST or None)
    if request.method == 'POST' and import_form.is_valid():
        imports = ImportTeam(import_form)
        try:
            imports.connect_to_worksheet()
            imports.read_titles()
            is_test = int(request.POST.get('is_test', '0')) == 1
            results = imports.import_teams(tournament, is_test)

        except Exception as ex:
            message = str(ex)

        if results:
            return render(
                request,
                'tournament/import_results.html',
                {
                    'results': results,
                    'tournament': tournament,
                    'statuses': {
                        'add': ImportTeam.STATUS_ADD,
                        'exist': ImportTeam.STATUS_EXIST,
                        'fail': ImportTeam.STATUS_FAIL,
                    },
                }
            )

    return render(
        request,
        'tournament/import_team_form.html',
        {
            'message': message,
            'form': import_form,
            'tournament': tournament,
        }
    )


@ensure_csrf_cookie
@login_required(login_url=reverse_lazy('account_login'))
@access_by_status(name_page='team/adju. edit')
def edit_team_list(request, tournament):
    return render(
        request,
        'tournament/edit_team_list.html',
        {
            'is_check_page': request.path == reverse('tournament:check_team_list', args=[tournament.id]),
            'tournament': tournament,
            'team_tournament_rels': tournament.get_teams(),
            'statuses': TEAM_ROLES,
            'can_remove_teams': tournament.cur_round == 0,
            'member_role': ROLE_MEMBER,
        }
    )


@csrf_protect
@ajax_request
@login_required(login_url=reverse_lazy('account_login'))
@access_by_status(name_page='team/adju. edit')
def team_role_update(request, tournament):
    rel = get_object_or_404(TeamTournamentRel, pk=request.POST.get('rel_id', '0'))
    new_role = get_object_or_404(TournamentRole, pk=request.POST.get('new_role_id', '0'))
    if new_role not in TEAM_ROLES:
        return json_response(MSG_JSON_BAD, MSG_BAD_TEAM_ROLE)

    can_change, message = can_change_team_role(rel, new_role)
    if not can_change:
        return json_response(MSG_JSON_BAD, message)

    rel.role = new_role
    rel.save()

    return json_response(MSG_JSON_OK, MSG_TEAM_ROLE_CHANGE)