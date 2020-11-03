from __future__ import unicode_literals

from django.template.loader import render_to_string
from django.urls import reverse
from django.conf import settings
from django.core import mail
from django.core.mail import EmailMultiAlternatives

if settings.CELERY_ENABLED:
    from tracker.tasks import send_mails

from accounts.models import User
from tracker.utils import get_message_id, get_reply_addr


__all__ = [
    'notify_new_issue', 'notify_new_comment',
    'notify_close_issue', 'notify_reopen_issue'
]


def notify_new_issue(issue):

    project = issue.project
    dests = project.subscribers.all().distinct()

    subject = "[%s] %s" % (project, issue.title)
    sender = issue.author

    data = {
        'description': issue.description,
        'project': project,
        'uri': settings.BASE_URL + reverse('show-issue',
            args=[project.name, issue.id]),
    }

    mid = '%s.issue-%d' % (project.name, issue.id)

    notify_by_email(data, 'new_issue', subject, sender, dests, mid)

def notify_new_comment(event):
    notify_event(event, 'new_comment')


def notify_close_issue(event):
    notify_event(event, 'close_issue')


def notify_reopen_issue(event):
    notify_event(event, 'reopen_issue')


def notify_event(event, template):

    issue = event.issue
    project = issue.project

    dests = issue.subscribers.all()
    dests |= project.subscribers.all()
    dests = dests.distinct()

    subject = "Re: [%s] %s" % (project, issue.title)
    sender = event.author

    data = {
        'comment': event.additionnal_section,
        'project': project,
        'uri': settings.BASE_URL + reverse('show-issue',
            args=[project.name, issue.id]),
    }

    ref = '%s.issue-%d' % (project.name, issue.id)
    mid = ref + '.' + str(event.pk)

    notify_by_email(data, template, subject, sender, dests, mid, ref)


def notify_by_email(data, template, subject, sender, dests, mid, ref=None):

    if hasattr(settings, 'REPLY_EMAIL') and hasattr(settings, 'EMAIL_KEY'):
        data.update({'answering': True})

    text_message = render_to_string('emails/%s.txt' % template, data)
    html_message = render_to_string('emails/%s.html' % template, data)

    from_email = '{name} <{email}>'.format(
            name=sender.fullname or sender.username,
            email=settings.DEFAULT_FROM_EMAIL)

    # Generating headers
    headers = {
        'Message-ID': get_message_id(mid),
    }
    if ref:
        # This email reference a previous one
        headers.update({
            'References': get_message_id(ref),
        })

    mails = []

    for dest in dests:

        if dest.notifications == User.NOTIFICATIONS_NEVER:
            continue
        if dest == sender \
                and dest.notifications == User.NOTIFICATIONS_OTHERS:
            continue
        dest_addr = dest.email
        if not dest_addr:
            continue

        reply_to = get_reply_addr(mid, dest)

        mails += [(subject, (text_message, html_message), from_email, [dest_addr], reply_to, headers)]

    if settings.CELERY_ENABLED:
        send_mails.delay(mails)
    else:
        messages = []
        for subject, message, from_email, dests, reply_to, headers in mails:
            text_message, html_message = message
            msg = EmailMultiAlternatives(subject, text_message, from_email, dests, reply_to=reply_to, headers=headers)
            msg.attach_alternative(html_message, 'text/html')
            messages += [msg]
        with mail.get_connection() as connection:
            connection.send_messages(messages)
