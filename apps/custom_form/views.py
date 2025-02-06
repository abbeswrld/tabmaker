from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.urls import reverse_lazy
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_protect
from django.db.models import F

from apps.tournament.consts import 
    CUSTOM_FORM_TYPES, \
    REQUIRED_ALIASES, \
    CUSTOM_FORM_AJAX_ACTIONS, \
    CUSTOM_FORM_QUESTIONS_TITLES

from apps.tournament.messages import MSG_JSON_OK,MSG_JSON_BAD
from apps.tournament.models import \
    CustomForm, \
    CustomFormAnswers, \
    CustomQuestion, \
    FeedbackAnswer
from apps.tournament.registration_forms import CustomFeedbackForm
from apps.tournament.views import access_by_status, ajax_request
from apps.tournament.utils import json_response




@ensure_csrf_cookie
@login_required(login_url=reverse_lazy('account_login'))
@access_by_status(name_page='custom_questions')
def custom_form_edit(request, tournament, form_type):
    form = CustomForm.get_or_create(tournament, CUSTOM_FORM_TYPES[form_type])
    questions = CustomQuestion.objects.filter(form=form).select_related('alias').order_by('position')

    return render(
        request,
        'tournament/custom_form_edit.html',
        {
            'tournament': tournament,
            'form': form,
            'questions': questions,
            'required_aliases': REQUIRED_ALIASES,
            'actions': CUSTOM_FORM_AJAX_ACTIONS,
            'title': CUSTOM_FORM_QUESTIONS_TITLES[CUSTOM_FORM_TYPES[form_type]],
        }
    )


@csrf_protect
@ajax_request
@login_required(login_url=reverse_lazy('account_login'))
@access_by_status(name_page='custom_questions')
def custom_form_edit_field(request, tournament):
    form_id = int(request.POST.get('form_id', '0'))
    action = request.POST.get('action', '')

    form = CustomForm.objects.filter(pk=form_id).first()

    if not form or form.tournament != tournament:
        status = MSG_JSON_BAD
        message = 'Такой формы не найдено'
    elif action == CUSTOM_FORM_AJAX_ACTIONS['edit_question']:
        status, message = _form_edit_field(request, form)
    elif action == CUSTOM_FORM_AJAX_ACTIONS['remove_question']:
        status, message = _form_remove_field(request, form)
    elif action == CUSTOM_FORM_AJAX_ACTIONS['up_question']:
        status, message = _form_up_field(request, form)
    elif action == CUSTOM_FORM_AJAX_ACTIONS['down_question']:
        status, message = _form_down_field(request, form)
    else:
        status = MSG_JSON_BAD
        message = 'Чё надо то'

    return json_response(status, message)


def _form_edit_field(request, form: CustomForm):
    field_id = int(request.POST.get('question_id', 0))
    question = request.POST.get('question', '')
    comment = request.POST.get('comment', '')
    is_required = request.POST.get('is_required', '0') == '1'

    if not question:
        return MSG_JSON_BAD, 'Вопрос не может быть пустым'

    if field_id:
        field = form.customquestion_set.filter(pk=field_id).first()
        if not field:
            return MSG_JSON_BAD, 'Вопрос не найден'

        if field.alias in REQUIRED_ALIASES:
            return MSG_JSON_BAD, 'Этот вопрос является обязательным, его нельзя редактировать'

        field.question = question
        field.comment = comment
        field.required = is_required
        field.save()
        message = 'Вопрос сохранён'
    else:
        position = form.customquestion_set.latest('position').position + 1 if form.customquestion_set.count() else 1
        field = CustomQuestion.objects.create(
            question=question,
            comment=comment,
            position=position,
            required=is_required,
            form=form,
        )
        message = 'Вопрос добавлен'

    return MSG_JSON_OK, {
        'question_id': field.id,
        'message': message,
    }


def _form_remove_field(request, form: CustomForm):
    from django.db.models import F

    field_id = int(request.POST.get('question_id', 0))
    field = form.customquestion_set.filter(pk=field_id).first()
    if not field:
        return MSG_JSON_BAD, 'Вопрос не найден'

    if field.alias in REQUIRED_ALIASES:
        return MSG_JSON_BAD, 'Обязательные вопросы нельзя удалять'

    form.customquestion_set.filter(position__gt=field.position).update(position=F('position') - 1)
    field.delete()

    return MSG_JSON_OK, 'Вопрос удалён'


def _swap_field(field, prev_field):
    if not field or not prev_field:
        return MSG_JSON_BAD, 'Вопрос не найден'

    if prev_field.position + 1 != field.position:
        return MSG_JSON_BAD, 'Невозможно изменить порядок вопросов'

    field.position -= 1
    field.save()

    prev_field.position += 1
    prev_field.save()

    return MSG_JSON_OK, 'Изменения сохранены'


def _form_up_field(request, form: CustomForm):
    field_id = int(request.POST.get('question_id', 0))
    field = form.customquestion_set.filter(pk=field_id).first()

    prev_field_id = int(request.POST.get('prev_question_id', 0))
    prev_field = form.customquestion_set.filter(pk=prev_field_id).first()

    return _swap_field(field, prev_field)


def _form_down_field(request, form: CustomForm):
    field_id = int(request.POST.get('question_id', 0))
    field = form.customquestion_set.filter(pk=field_id).first()

    next_field_id = int(request.POST.get('next_question_id', 0))
    next_field = form.customquestion_set.filter(pk=next_field_id).first()

    return _swap_field(next_field, field)


@login_required(login_url=reverse_lazy('account_login'))
@access_by_status(name_page='custom_answers')
def custom_form_show_answers(request, tournament, form_type):
    custom_form = get_object_or_404(CustomForm, tournament=tournament, form_type=CUSTOM_FORM_TYPES[form_type])

    title = ''
    column_names = list(map(lambda x: x.question, custom_form.customquestion_set.all().order_by('position')))
    if custom_form.form_type == FORM_FEEDBACK_TYPE:
        column_names = [LBL_ROUND_FEEDBACK, LBL_CHAIR_FEEDBACK] + column_names
    column_values = []
    for custom_form_answers in CustomFormAnswers.objects.filter(form=custom_form).order_by('id'):
        answers = custom_form_answers.get_answers()
        column_values.append(list(map(lambda x: answers.get(x, ''), column_names)))

    return render(
        request,
        'tournament/custom_form_answers.html',
        {
            'tournament': tournament,
            'title': CUSTOM_FORM_ANSWERS_TITLES[CUSTOM_FORM_TYPES[form_type]],
            'column_names': column_names,
            'rows': column_values,
        }
    )