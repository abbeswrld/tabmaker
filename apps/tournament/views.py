import random
import logging

from datetime import date, timedelta

# from django.db.models import Count, Q
# from django.shortcuts import render

# from apps.tournament.consts import *
# from apps.tournament.models import Tournament
# from apps.tournament.utils import paging

from django.contrib.auth.decorators import login_required
from django.db.models import Case, When, IntegerField
from django.urls import \
    reverse_lazy, \
    reverse
from django.http import \
    HttpResponseBadRequest, \
    Http404

from django.shortcuts import \
    render, \
    get_object_or_404, \
    redirect
from django.views.decorators.csrf import \
    csrf_protect, \
    ensure_csrf_cookie

from .forms import EditForm

from .utils import \
    json_response, \
    paging

from .consts import *
from .forms import \
    TournamentForm, \
    CheckboxForm, \
    СonfirmForm, \
    RoundForm, \
    ActivateResultForm, \
    GameForm, \
    MotionForm
from .logic import \
    can_change_team_role, \
    check_games_results_exists, \
    check_final, \
    check_last_round_results, \
    check_teams_and_adjudicators, \
    generate_next_round, \
    generate_playoff, \
    get_all_rounds_and_rooms, \
    get_games_and_results, \
    get_rooms_by_user, \
    get_motions, \
    get_rooms_from_last_round, \
    get_tab, \
    get_teams_by_user, \
    publish_last_round, \
    remove_last_round, \
    remove_playoff, \
    user_can_edit_tournament
from .messages import *
from .models import \
    AccessToPage, \
    Tournament, \
    TeamTournamentRel, \
    UserTournamentRel
    
from apps.profile.models import TelegramToken, User

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Count, Q


def access_by_status(name_page=None, only_owner=False):
    # TODO Страницы в константы
    # TODO Закешировать массив с уровнем доступа
    def decorator_maker(func):

        def check_access_to_page(request, tournament_id, *args, **kwargs):
            tournament = get_object_or_404(Tournament, pk=tournament_id)
            if name_page:
                security = AccessToPage.objects.filter(status=tournament.status, page__name=name_page) \
                    .select_related('page').first()
                if not security.page.is_public and not user_can_edit_tournament(tournament, request.user, only_owner):
                    return _show_message(request, MSG_ERROR_TO_ACCESS)

                if not security.access:
                    return _show_message(request, security.message)

            return func(request, tournament, *args, **kwargs)

        return check_access_to_page

    return decorator_maker


def check_tournament(func):
    def decorator(request, tournament):
        error = check_last_round_results(tournament)
        if error:
            return _show_message(request, error)

        error = check_teams_and_adjudicators(tournament)
        if error:
            return _show_message(request, error)

        error = check_final(tournament)
        if error:
            return _show_message(request, error)

        return func(request, tournament)

    return decorator


def ajax_request(func):
    def decorator(request, *args, **kwargs):
        if request.method != 'POST' or not request.is_ajax():
            return HttpResponseBadRequest

        return func(request, *args, **kwargs)

    return decorator


def _confirm_page(request, tournament, need_message, template_body, redirect_to, callback, redirect_args=None):
    if not redirect_args:
        redirect_args = {}
    confirm_form = СonfirmForm(request.POST)
    is_error = False
    if request.method == 'POST' and confirm_form.is_valid():
        message = confirm_form.cleaned_data.get('message', '')
        is_error = not (message == need_message)
        if not is_error:
            callback(tournament)

            return redirect(redirect_to, **redirect_args)

    return render(
        request,
        'tournament/confirm.html',
        {
            'tournament': tournament,
            'form': confirm_form,
            'need_message': need_message,
            'is_error': is_error,
            'template_body': template_body,
            'path': request.path
        }
    )


def _show_message(request, message):
    return render(
        request,
        'main/message.html',
        {
            'message': message,
        }
    )


def _convert_tab_to_table(table: list, show_all):
    def _playoff_position(res):
        if not res.count_playoff_rounds:
            return LBL_NOT_IN_BREAK
        if res.playoff_position > res.count_playoff_rounds:
            return LBL_WINNER
        elif res.playoff_position == res.count_playoff_rounds:
            return LBL_FINALISTS
        elif res.playoff_position == 0:
            return LBL_NOT_IN_BREAK
        else:
            return LBL_ONE_p % str(2 ** (res.count_playoff_rounds - res.playoff_position))

    lines = []
    count_rounds = max(list(map(lambda x: len(x.rounds), table)) + [0])
    line = [LBL_N, LBL_TEAM, LBL_SUM_POINTS, LBL_PLAYOFF, LBL_SUM_SPEAKERS]

    for i in range(1, count_rounds + 1):
        line.append(LBL_ROUND_p % i)
    lines.append(line)

    for team in table:
        team.show_all = show_all

    table = sorted(table, reverse=True)
    for i in range(len(table)):
        line = []
        n = lines[-1][0] if i > 0 and table[i - 1] == table[i] else i + 1
        line += [n, table[i].team.name, table[i].sum_points, _playoff_position(table[i]), table[i].sum_speakers]
        for cur_round in table[i].rounds:
            round_res = str(cur_round.points * bool(not cur_round.is_closed or show_all))
            line.append(round_res)
        lines.append(line)

    return lines


def _convert_tab_to_speaker_table(table: list, is_show):
    speakers = []
    for team_result in table:
        speakers += team_result.extract_speakers_result()

    if is_show:
        speakers = sorted(speakers, reverse=True)
    else:
        random.shuffle(speakers)

    lines = []
    count_rounds = max(list(map(lambda x: len(x.points), speakers)) + [0])
    head = [LBL_N, LBL_SPEAKER, LBL_TEAM, LBL_SUM_SPEAKERS]

    for i in range(1, count_rounds + 1):
        head.append(LBL_ROUND_p % i)
    lines.append(head)

    for i in range(len(speakers)):
        line = []
        n = lines[-1][0] if i > 0 and speakers[i - 1] == speakers[i] else i + 1
        line += [n, speakers[i].user.name(), speakers[i].team.name, speakers[i].sum_points() * int(is_show)]
        for point in speakers[i].points:
            line.append(point * int(is_show))
        lines.append(line)

    return lines


def _get_or_check_round_result_forms(request, rooms, is_admin=False, is_playoff=False, is_final=False):
    from .forms import \
        FinalGameResultForm, \
        PlayoffGameResultForm, \
        QualificationGameResultForm

    all_is_valid = True
    forms = []

    ResultForm = FinalGameResultForm if is_final \
        else PlayoffGameResultForm if is_playoff \
        else QualificationGameResultForm

    for room in get_games_and_results(rooms):
        activate_form = ActivateResultForm(request.POST or None, prefix='af_%s' % room['game'].id)

        if request.method == 'POST' and activate_form.is_valid() and activate_form.is_active():
            result_form = ResultForm(request.POST, instance=room['result'], prefix='rf_%s' % room['game'].id)
            all_is_valid &= result_form.is_valid()
            if result_form.is_valid():
                result_form.save()
        else:
            result_form = ResultForm(instance=room['result'], prefix='rf_%s' % room['game'].id)
            activate_form.init(is_admin)
            result_form.initial['game'] = room['game'].id

        forms.append({
            'game': room['game'],
            'result': result_form,
            'activate_result': activate_form,
            'show_checkbox': is_admin,
        })
    return all_is_valid, forms


##################################
#    Management of tournament    #
##################################

@login_required(login_url=reverse_lazy('account_login'))
def new(request):
    if request.method == 'POST':
        tournament_form = TournamentForm(request.POST)
        if tournament_form.is_valid():
            tournament_obj = tournament_form.save(commit=False)
            tournament_obj.status = STATUS_REGISTRATION
            tournament_obj.save()
            UserTournamentRel.objects.create(
                user=request.user,
                tournament=tournament_obj,
                role=ROLE_OWNER
            )

            CustomForm.get_or_create(tournament_obj, FORM_REGISTRATION_TYPE)
            CustomForm.get_or_create(tournament_obj, FORM_ADJUDICATOR_TYPE)

            return redirect('tournament:created', tournament_id=tournament_obj.id)

    else:
        tournament_form = TournamentForm()

    return render(
        request,
        'tournament/new.html',
        {
            'form': tournament_form,
        }
    )


@login_required(login_url=reverse_lazy('account_login'))
@access_by_status(name_page='edit')
def created(request, tournament):
    return render(
        request,
        'tournament/created.html',
        {
            'tournament': tournament,
        }
    )


@access_by_status(name_page='show')
def show(request, tournament):

    if request.GET.get('new', None):
        return show2(request, tournament)

    is_chair = request.user.is_authenticated \
        and tournament.status in [STATUS_PLAYOFF, STATUS_STARTED] \
        and get_rooms_from_last_round(tournament, False, request.user).count()

    need_show_feedback_button = request.user.is_authenticated \
        and get_rooms_by_user(tournament, request.user) \
        and CustomForm.objects.filter(tournament=tournament, form_type=FORM_FEEDBACK_TYPE).count()

    return render(
        request,
        'tournament/show.html',
        {
            'tournament': tournament,
            'team_tournament_rels': tournament.get_teams(),
            'adjudicators': tournament.get_users(ADJUDICATOR_ROLES),
            'is_owner': user_can_edit_tournament(tournament, request.user),
            'is_chair': is_chair,
            'need_show_feedback_button': need_show_feedback_button,
        }
    )


# @access_by_status(name_page='show')
def show2(request, tournament):

    # is_chair = request.user.is_authenticated \
    #     and tournament.status in [STATUS_PLAYOFF, STATUS_STARTED] \
    #     and get_rooms_from_last_round(tournament, False, request.user).count()
    #
    # need_show_feedback_button = request.user.is_authenticated \
    #     and get_rooms_by_user(tournament, request.user) \
    #     and CustomForm.objects.filter(tournament=tournament, form_type=FORM_FEEDBACK_TYPE).count()

    is_owner = user_can_edit_tournament(tournament, request.user)

    tabs = []

    # Текущий раунд
    if tournament.status in [STATUS_STARTED, STATUS_PLAYOFF]:
        tab_config = {'title': 'Раунд'}
        rooms = get_rooms_from_last_round(tournament, True)
        if not rooms or not rooms[0].round.is_public:
            tab_config['message'] = MSG_ROUND_NOT_PUBLIC
        else:
            tab_config['data'] = rooms
            tab_config['template'] = 'tournament/tabs/public/round.html'

        tabs.append(tab_config)

    # Командный теб + Спикерский теб
    if tournament.status in [STATUS_STARTED, STATUS_PLAYOFF, STATUS_FINISHED]:
        show_all = tournament.status == STATUS_FINISHED or is_owner
        results = get_tab(tournament)

        tab_config = {'title': 'Результаты команд'}
        if not results:
            tab_config['message'] = 'Результатов нет'
        else:
            tab_config['data'] = _convert_tab_to_table(results, show_all)
            tab_config['template'] = 'tournament/tabs/public/tab.html'

        tabs.append(tab_config)

        if tournament.status == STATUS_FINISHED:
            tab_config = {'title': 'Результаты спикеров'}
            if not results:
                tab_config['message'] = 'Результатов нет'
            else:
                tab_config['data'] = _convert_tab_to_speaker_table(results, show_all)
                tab_config['template'] = 'tournament/tabs/public/tab.html'

            tabs.append(tab_config)

        tabs.append({
            'title': 'Темы',
            'data': get_motions(tournament),
            'template': 'tournament/tabs/public/motions.html',
        })

        if tournament.status == STATUS_FINISHED:
            tabs.append({
                'title': 'Раунды',
                'data': get_all_rounds_and_rooms(tournament),
                'template': 'tournament/tabs/public/results.html',
            })

    tabs.append({
        'title': 'О турнире',
        'data': tournament,
        'template': 'tournament/tabs/public/info.html',
    })

    tab_config = {'title': 'Команды'}
    if not is_owner and tournament.status == STATUS_REGISTRATION and tournament.is_registration_hidden:
        tab_config['message'] = 'Информация закрыта'
        tab_config['comment'] = 'Организаторы турнира скрыли инфомацию о уже зарегистрированных командах'
    else:
        teams = tournament.get_teams()
        if not len(teams):
            tab_config['message'] = 'Пока никто не зарегистрировался'
            tab_config['comment'] = 'Вы можете стать первым участником'
        else:
            tab_config['data'] = teams
            tab_config['template'] = 'tournament/tabs/public/teams.html'

    tabs.append(tab_config)

    tab_config = {'title': 'Судьи'}
    adjudicators = tournament.get_users(ADJUDICATOR_ROLES)
    if not len(adjudicators):
        tab_config['message'] = 'Пока никто не зарегистрировался'
        tab_config['comment'] = 'Вы можете стать первым cудьей'
    else:
        tab_config['data'] = adjudicators
        tab_config['template'] = 'tournament/tabs/public/adjudicators.html'

    tabs.append(tab_config)

    tabs.append({
        'title': 'На карте',
        'data': True,
        'template': 'tournament/tabs/public/map.html',
    })

    return render(
        request,
        'tournament/show2.html',
        {
            'tournament': tournament,
            'is_owner': is_owner,
            'tabs': tabs,
            # 'is_chair': is_chair,
            # 'need_show_feedback_button': need_show_feedback_button,
            # 'user_messages': messages.get_messages(request),
        }
    )


@login_required(login_url=reverse_lazy('account_login'))
@access_by_status(name_page='edit')
def edit(request, tournament):
    if request.method == 'POST':
        tournament_form = TournamentForm(request.POST, instance=tournament)
        if tournament_form.is_valid():
            tournament_form.save()

            return _show_message(request, MSG_TOURNAMENT_CHANGED)

    else:
        tournament_form = TournamentForm(instance=tournament)

    team_form = CustomForm.get_or_create(tournament, FORM_REGISTRATION_TYPE)
    team_questions = CustomQuestion.objects.filter(form=team_form).select_related('alias').order_by('position')

    adjudicator_form = CustomForm.get_or_create(tournament, FORM_ADJUDICATOR_TYPE)
    adjudicator_questions = CustomQuestion.objects.filter(form=adjudicator_form) \
        .select_related('alias') \
        .order_by('position')

    return render(
        request,
        'tournament/edit.html',
        {
            'form': tournament_form,
            'tournament': tournament,
            'team_form': team_form,
            'team_questions': team_questions,
            'adjudicator_form': adjudicator_form,
            'adjudicator_questions': adjudicator_questions,
            'required_aliases': REQUIRED_ALIASES,
            'actions': CUSTOM_FORM_AJAX_ACTIONS,
        }
    )


@access_by_status(name_page='result')
def result(request, tournament):
    is_owner = user_can_edit_tournament(tournament, request.user)
    show_all = tournament.status == STATUS_FINISHED or is_owner
    tab = get_tab(tournament)

    return render(
        request,
        'tournament/result.html',
        {
            'tournament': tournament,
            'team_tab': _convert_tab_to_table(tab, show_all),
            'speaker_tab': _convert_tab_to_speaker_table(tab, show_all),
            'motions': get_motions(tournament),
            'is_owner': is_owner,
        }
    )


@access_by_status(name_page='result_all')
def result_all_rounds(request, tournament):
    is_owner = user_can_edit_tournament(tournament, request.user)
    if not is_owner and tournament.status != STATUS_FINISHED:
        return _show_message(request, MSG_RESULT_NOT_PUBLISHED)

    return render(
        request,
        'tournament/round_results_show.html',
        {
            'tournament': tournament,
            'results': get_all_rounds_and_rooms(tournament),
            'is_owner': is_owner,
        }
    )


@login_required(login_url=reverse_lazy('account_login'))
@access_by_status(name_page='remove')
def remove(request, tournament):
    if tournament.id == 1:
        return _show_message(request, 'Нельзя удалить тестовый турнир')
    need_message = CONFIRM_MSG_REMOVE
    redirect_to = 'main:index'
    template_body = 'tournament/remove_message.html'

    def tournament_delete(tournament_):
        tournament_.delete()

    return _confirm_page(request, tournament, need_message, template_body, redirect_to, tournament_delete)


@login_required(login_url=reverse_lazy('account_login'))
@access_by_status(name_page='edit')
def print_users(request, tournament):
    return render(
        request,
        'tournament/users_list_for_print.html',
        {
            'teams': tournament.team_members.all()
        }
    )


def feedback(request):
    from django.core.mail import mail_managers

    if request.method == 'POST':
        who = ''
        if request.user.is_authenticated:
            who = '%s (%s)' % (request.user.get_full_name(), request.user.email)

        mail_managers(
            'Tabmaker Feedback',
            '''
            Кто %s \n\n
            Что в Tabmaker сделано хорошо:\n
            %s \n\n\n
            Что в Tabmaker можно улучшить:\n
            %s \n\n\n
            Предложения или пожелания:\n
            %s \n\n\n
            Оценка:\n
            %d \n\n\n
            ''' % (
                who,
                request.POST.get('already_good', ''),
                request.POST.get('can_be_batter', ''),
                request.POST.get('what_you_want', ''),
                int(request.POST.get('nps', 0))
            )
        )

        return _show_message(request, 'Спасибо за ваш отзыв')

    return render(
        request,
        'main/tabmaker_feedback.html'
    )


def support(request):
    from django.core.mail import mail_managers

    if request.method == 'POST':
        who = '%s (%s)' % (request.user.get_full_name(), request.user.email) \
            if request.user.is_authenticated \
            else 'noname'

        mail_managers(
            'Tabmaker: Somebody need help!',
            '''
            Кто %s \n\n
            Проблема:\n
            %s \n\n\n
            Контакты:\n
            %s
            ''' % (
                who,
                request.POST.get('problem', ''),
                request.POST.get('contacts', ''),
            )
        )

        return _show_message(request, 'Мы постараемся ответить как можно быстрее')

    return render(
        request,
        'main/support.html'
    )


##################################
#   Change status of tournament  #
##################################

@login_required(login_url=reverse_lazy('account_login'))
@access_by_status(name_page='registration opening')
def registration_opening(request, tournament):
    tournament.set_status(STATUS_REGISTRATION)
    return redirect('tournament:show', tournament_id=tournament.id)


@login_required(login_url=reverse_lazy('account_login'))
@access_by_status(name_page='registration closing')
def registration_closing(request, tournament):
    if tournament.status == STATUS_STARTED and tournament.cur_round > 0:
        return _show_message(request, MSG_MUST_REMOVE_ROUNDS)

    tournament.set_status(STATUS_PREPARATION)
    return redirect('tournament:show', tournament_id=tournament.id)


@login_required(login_url=reverse_lazy('account_login'))
@access_by_status(name_page='start')
def start(request, tournament):
    if tournament.status == STATUS_PREPARATION:
        error_message = check_teams_and_adjudicators(tournament)
    else:
        error_message = '' if remove_playoff(tournament) else MSG_MUST_REMOVE_PLAYOFF_ROUNDS

    if error_message:
        return _show_message(request, error_message)

    tournament.set_status(STATUS_STARTED)
    return redirect('tournament:show', tournament_id=tournament.id)


@login_required(login_url=reverse_lazy('account_login'))
@access_by_status(name_page='break')
def generate_break(request, tournament):
    tab = sorted(get_tab(tournament), reverse=True)
    table = _convert_tab_to_table(tab, True)
    teams_in_break = []
    teams = []
    for i in range(len(tab)):
        if request.method == 'POST':
            form = CheckboxForm(request.POST, prefix=i, use_required_attribute=False)
            if form.is_valid() and form.cleaned_data.get('is_check', False):
                teams_in_break.append(tab[i].team)
        else:
            form = CheckboxForm(
                initial={
                    'id': tab[i].team.id,
                    'is_check': i < tournament.count_teams_in_break
                },
                prefix=i,
                use_required_attribute=False
            )
        teams.append({
            'checkbox': form,
            'result': table[i + 1],
        })

    error_message = ''
    if request.method == 'POST':
        if len(teams_in_break) != tournament.count_teams_in_break:
            error_message = MSG_SELECT_N_TEAMS_TO_BREAK_p % tournament.count_teams_in_break
        else:
            generate_playoff(tournament, teams_in_break)
            tournament.set_status(STATUS_PLAYOFF)

            return redirect('tournament:show', tournament_id=tournament.id)

    return render(
        request,
        'tournament/break.html',
        {
            'error': error_message,
            'tournament': tournament,
            'header': table[0],
            'teams': teams,
        }
    )


@login_required(login_url=reverse_lazy('account_login'))
@access_by_status(name_page='finished')
def finished(request, tournament):
    need_message = CONFIRM_MSG_FINISHED
    redirect_to = 'main:feedback'
    redirect_args = {}
    template_body = 'tournament/finished_message.html'

    def tournament_finished(tournament_):
        tournament_.set_status(STATUS_FINISHED)

    return _confirm_page(request, tournament, need_message, template_body, redirect_to, tournament_finished,
                         redirect_args)





##################################
#   Management of adjudicator    #
##################################

def _registration_adjudicator(tournament: Tournament, user: User):
    if UserTournamentRel.objects.filter(user=user, tournament=tournament, role__in=ADJUDICATOR_ROLES).exists():
        return False

    UserTournamentRel.objects.create(user=user, tournament=tournament, role=ROLE_ADJUDICATOR_REGISTERED)
    return True


@login_required(login_url=reverse_lazy('account_login'))
@access_by_status(name_page='team/adju. registration')
def registration_adjudicator(request, tournament):
    from .registration_forms import CustomAdjudicatorRegistrationForm

    custom_form = CustomForm.objects.filter(tournament=tournament, form_type=FORM_ADJUDICATOR_TYPE).first()

    if not custom_form:
        message = MSG_ADJUDICATOR_SUCCESS_REGISTERED_p % tournament.name \
            if _registration_adjudicator(tournament, request.user) \
            else MSG_ADJUDICATOR_ALREADY_REGISTERED_p % tournament.name
        return _show_message(request, message)

    questions = CustomQuestion.objects.filter(form=custom_form).select_related('alias').order_by('position')
    if request.method == 'POST':
        adjudicator_form = CustomAdjudicatorRegistrationForm(questions, request.POST)
        if adjudicator_form.is_valid():
            if _registration_adjudicator(tournament, request.user):
                custom_form_answers = CustomFormAnswers.objects.create(form=custom_form)
                custom_form_answers.set_answers(adjudicator_form.get_answers(questions))
                custom_form_answers.save()
                return _show_message(request, MSG_ADJUDICATOR_SUCCESS_REGISTERED_p % tournament.name)
            else:
                return _show_message(request, MSG_ADJUDICATOR_ALREADY_REGISTERED_p % tournament.name)
    else:
        adjudicator_form = CustomAdjudicatorRegistrationForm(questions, initial={'adjudicator': request.user.email})

    return render(
        request,
        'tournament/registration_new.html',
        {
            'title': 'Регистрация судьи',
            'submit_title': 'Судить',
            'action_url': 'tournament:registration_adjudicator',
            'form': adjudicator_form,
            'tournament': tournament,
        }
    )


@csrf_protect
@ajax_request
@login_required(login_url=reverse_lazy('account_login'))
@access_by_status(name_page='team/adju. add')
def add_adjudicator(request, tournament):
    user = User.objects.filter(email__iexact=request.POST.get('email', '')).first()

    if not user:
        return json_response(MSG_JSON_BAD, MSG_USER_NOT_EXIST_p % request.POST.get('email', ''))

    if _registration_adjudicator(tournament, user):
        return json_response(MSG_JSON_OK, MSG_ADJUDICATOR_SUCCESS_REGISTERED_p % tournament.name)
    else:
        return json_response(MSG_JSON_BAD, MSG_ADJUDICATOR_ALREADY_REGISTERED_pp % (user.name(), tournament.name))


@login_required(login_url=reverse_lazy('account_login'))
@access_by_status(name_page='team/adju. edit')
def edit_adjudicator_list(request, tournament):
    return render(
        request,
        'tournament/edit_adjudicator_list.html',
        {
            'is_check_page': request.path == reverse('tournament:check_adjudicator_list', args=[tournament.id]),
            'chair_need': tournament.teamtournamentrel_set.filter(role=ROLE_MEMBER).count() // TEAM_IN_GAME,
            'user_tournament_rels': tournament.get_users(ADJUDICATOR_ROLES),
            'statuses': ADJUDICATOR_ROLES,
            'chair_role': ROLE_CHAIR,
            'tournament': tournament,
        }
    )


@csrf_protect
@ajax_request
@login_required(login_url=reverse_lazy('account_login'))
@access_by_status(name_page='team/adju. edit')
def adjudicator_role_update(request, tournament):
    rel = get_object_or_404(UserTournamentRel, pk=request.POST.get('rel_id', '0'))
    new_role = get_object_or_404(TournamentRole, pk=request.POST.get('new_role_id', '0'))
    if new_role not in ADJUDICATOR_ROLES:
        return json_response(MSG_JSON_BAD, MSG_BAD_ADJUDICATOR_ROLE)

    teams = get_teams_by_user(rel.user, rel.tournament)
    if new_role in [ROLE_CHAIR, ROLE_CHIEF_ADJUDICATOR, ROLE_WING] and teams:
        return json_response(
            MSG_JSON_BAD, MSG_USER_ALREADY_IS_MEMBER_pp % (rel.user.name(), teams[0].team.name)
        )

    rel.role = new_role
    rel.save()

    return json_response(MSG_JSON_OK, MSG_ADJUDICATOR_ROLE_CHANGE)


@ensure_csrf_cookie
@login_required(login_url=reverse_lazy('account_login'))
@access_by_status(name_page='edit', only_owner=True)
def list_admin(request, tournament: Tournament):
    return render(
        request,
        'tournament/admin_list.html',
        {
            'admins': tournament.get_users([ROLE_ADMIN]),
            'owner': request.user,
            'tournament': tournament,
        }
    )


@csrf_protect
@ajax_request
@login_required(login_url=reverse_lazy('account_login'))
@access_by_status(name_page='edit', only_owner=True)
def add_admin(request, tournament):
    user = User.objects.filter(email__iexact=request.POST.get('email', '')).first()

    if not user:
        return json_response(
            MSG_JSON_BAD, MSG_USER_NOT_EXIST_p % request.POST.get('email', '')
        )

    admin_rel = UserTournamentRel.objects.get_or_create(user=user, tournament=tournament, role=ROLE_ADMIN)
    if not admin_rel[1]:
        return json_response(
            MSG_JSON_BAD, MSG_ADMIN_ALREADY_ADD_p % user.name()
        )

    return json_response(
        MSG_JSON_OK, {
            'rel_id': admin_rel[0].id,
            'name': user.name(),
        }
    )


@csrf_protect
@ajax_request
@login_required(login_url=reverse_lazy('account_login'))
@access_by_status(name_page='edit', only_owner=True)
def remove_admin(request, tournament):
    rel_id = request.POST.get('rel_id', '0')
    admin_rel = UserTournamentRel.objects.filter(pk=rel_id, role=ROLE_ADMIN).select_related('user')

    if not admin_rel.first():
        return json_response(MSG_JSON_BAD, MSG_ADMIN_NOT_EXIST)

    admin = admin_rel.first().user
    admin_rel.delete()

    return json_response(
        MSG_JSON_OK, MSG_ADMIN_REMOVE_p % admin.name()
    )


@csrf_protect
@ajax_request
@login_required(login_url=reverse_lazy('account_login'))
@access_by_status(name_page='edit', only_owner=True)
def change_owner(request, tournament):
    owner_rel = UserTournamentRel.objects.filter(user=request.user, tournament=tournament, role=ROLE_OWNER)
    admin_rel = UserTournamentRel.objects.filter(pk=request.POST.get('rel_id', '0'))

    if not admin_rel.first():
        return json_response(MSG_JSON_BAD, MSG_ADMIN_NOT_EXIST)

    owner_rel.update(role=ROLE_ADMIN)
    admin_rel.update(role=ROLE_OWNER)

    return json_response(
        MSG_JSON_OK, MSG_OWNER_CHANGED_p % admin_rel.first().user.name()
    )




# ================================ main

def index(request):
    DAYS_TO_LEAVE_SHORT_LIST = 3
    is_short = request.GET.get('list', None) != 'all'
    tournaments = Tournament.objects.select_related('status').annotate(
        m_count=Count(Case(
            When(teamtournamentrel__role=ROLE_MEMBER, then=1),
            output_field=IntegerField()
        ))
    )
    if is_short:
        # TODO Возможно стоит всегда показывать свои турниры в списке
        tournaments = tournaments.filter(
            Q(status__in=[STATUS_STARTED, STATUS_PLAYOFF, STATUS_FINISHED])
            |
            Q(start_tour__gte=(date.today() - timedelta(days=DAYS_TO_LEAVE_SHORT_LIST)))
        )
    else:
        tournaments = tournaments.all()

    return render(
        request,
        'main/main.html',
        {
            'is_main_page': True,
            'is_short': is_short,
            'objects': paging(
                request, list(tournaments.order_by('-start_tour')), 15
            )
        }
    )


@login_required(login_url=reverse_lazy('account_login'))
@access_by_status(name_page='')
def team_feedback(request, tournament):
    rooms = get_rooms_by_user(tournament, request.user)
    if not rooms:
        return _show_message(request, MSG_USER_FEEDBACK_WITHOUT_ROUNDS)

    custom_form = CustomForm.objects.filter(tournament=tournament, form_type=FORM_FEEDBACK_TYPE).first()
    questions = CustomQuestion.objects.filter(form=custom_form).select_related('alias').order_by('position') \
        if custom_form \
        else None

    if not questions:
        return _show_message(request, MSG_FEEDBACK_WITHOUT_QUESTIONS)

    if request.method == 'POST':
        feedback_form = CustomFeedbackForm(questions, None, request.POST)
        if feedback_form.is_valid():
            round_id = int(request.POST.get('round', 0))
            answers_from_form = {}

            for room in rooms:
                if room.round.id == round_id:
                    answers_from_form = {
                        LBL_ROUND_FEEDBACK: room.round.number,
                        LBL_CHAIR_FEEDBACK: room.game.chair.get_full_name(),
                    }
                    break

            answers_from_form.update(feedback_form.get_answers(questions))

            feedback_answers = FeedbackAnswer.objects.get_or_create(
                user=request.user,
                round_id=int(request.POST.get('round', 0)),
                form=custom_form
            )
            feedback_answers[0].set_answers(answers_from_form)
            feedback_answers[0].save()
            # TODO add message
            return _show_message(request, MSG_FEEDBACK_SAVED)

    else:
        feedback_answers = FeedbackAnswer.objects.filter(user=request.user, round=rooms.last().round).first()
        feedback_form = CustomFeedbackForm(questions, feedback_answers.get_answers() if feedback_answers else None)

    return render(
        request,
        'tournament/team_feedback.html',
        {
            'rooms': rooms,
            'title': 'Обратная связь на судью',
            'submit_title': 'Оставить Feedback',
            'action_url': 'tournament:team_feedback',
            'form': feedback_form,
            'tournament': tournament,
        }
    )