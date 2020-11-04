from __future__ import unicode_literals

from django.db import models
from django.core.validators import RegexValidator
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.utils.html import escape, format_html
from django.contrib.sites.models import Site
from django.core.validators import MinValueValidator, MaxValueValidator
from django.urls import reverse
from django.contrib.sites.shortcuts import get_current_site
from django.core.exceptions import ObjectDoesNotExist

from colorful.fields import RGBColorField

import json
from datetime import datetime, timedelta

from accounts.models import User


__all__ = ['Project', 'Issue', 'Label', 'Milestone', 'ReadState', 'Event']


class Settings(models.Model):

    EDIT_NOTIMEOUT = 0
    EDIT_TIMEOUT = 1
    EDIT_NOMORECOMMENT = 2
    EDIT_TYPE = (
        (EDIT_NOTIMEOUT, 'No timeout'),
        (EDIT_TIMEOUT, 'Timeout'),
        (EDIT_NOMORECOMMENT, 'As long no next comment'),
    )

    site = models.OneToOneField(Site, editable=False,
            related_name='settings', on_delete=models.CASCADE)
    items_per_page = models.IntegerField(default=25,
            verbose_name="Items per page",
            validators=[
                MinValueValidator(1),
                MaxValueValidator(500)
            ])
    edit_policy = models.IntegerField(choices=EDIT_TYPE,
            default=EDIT_NOTIMEOUT,
            verbose_name="Policy for \"Modify his issue and comment\" permission")
    edit_policy_timeout = models.IntegerField(default=30,
            verbose_name="Timeout for \"Modify his issue and comment\" permission (in min)",
            validators=[
                MinValueValidator(1),
            ])




class Project(models.Model):

    class Meta:
        ordering = ['name']

    ACCESS_PUBLIC = 1
    ACCESS_REGISTERED = 2
    ACCESS_PRIVATE = 3
    ACCESS_TYPE = (
        (ACCESS_PUBLIC, 'Public'),
        (ACCESS_REGISTERED, 'Registration required'),
        (ACCESS_PRIVATE, 'Private'),
    )

    display_name = models.CharField(max_length=32, unique=True,
            verbose_name="Project name")

    name = models.SlugField(max_length=32, unique=True,
            verbose_name="URL name")

    description = models.TextField(blank=True, default="",
            verbose_name="Description")

    access = models.IntegerField(choices=ACCESS_TYPE, default=ACCESS_PUBLIC)

    subscribers = models.ManyToManyField(User, blank=True,
            related_name='subscribed_projects')

    archived = models.BooleanField(default=False)

    @property
    def labels(self):
        return Label.objects.filter(project=self, deleted=False)

    @property
    def milestones(self):
        return Milestone.objects.filter(project=self, deleted=False)

    def get_unread_issues_nb(self, user):
        if not user.is_authenticated:
            return 0
        count = 0
        for issue in self.issues.all():
            if issue.have_unread_message(user):
                count +=1
        return count


    def __str__(self):
        return self.display_name


class Label(models.Model):

    project = models.ForeignKey(Project, related_name='+', on_delete=models.CASCADE)

    name = models.CharField(max_length=32)

    deleted = models.BooleanField(default=False)

    color = RGBColorField(default='#000000',
            verbose_name="Background color")

    inverted = models.BooleanField(default=True,
            verbose_name="Inverse text color")

    @property
    def url(self):

        url = reverse('list-issue', kwargs={'project': self.project.name})
        url += '?q=is:open%20label:' + self.quotted_name

        return mark_safe(url)

    @property
    def style(self):

        if self.inverted:
            fg = '#fff'
        else:
            fg = '#000'

        style = "background-color: {bg}; color: {fg}; vertical-align: middle;"

        return style.format(bg=self.color, fg=fg)

    @property
    def quotted_name(self):
        if ' ' in self.name:
            name = '&quot;' + escape(self.name) + '&quot'
        else:
            name = escape(self.name)
        return mark_safe(name)

    def __str__(self):
        return self.name


class Milestone(models.Model):

    class Meta:
        ordering = ['due_date']
        unique_together = ['project', 'name']

    name_validator = RegexValidator(regex='^[a-z0-9_.-]+$',
            message="Please enter only lowercase characters, number, "
                    "dot, underscores or hyphens.")

    project = models.ForeignKey(Project, related_name='+', on_delete=models.CASCADE)

    name = models.CharField(max_length=32, validators=[name_validator])

    due_date = models.DateTimeField(blank=True, null=True)

    closed = models.BooleanField(default=False)

    deleted = models.BooleanField(default=False)

    def closed_issues(self):

        return self.issues.filter(closed=True).count()

    def total_issues(self):

        return self.issues.count()

    def progress(self):

        closed = self.closed_issues()
        total = self.total_issues()

        if total:
            return int(100 * closed / total)
        else:
            return 0

    @property
    def url(self):

        url = reverse('list-issue', kwargs={'project': self.project.name})
        url += '?q=is:open%20milestone:' + self.name

        return mark_safe(url)

    def __str__(self):
        return self.name


class Issue(models.Model):

    # id is the id in the project, not the pk, so we need one
    primarykey = models.AutoField(primary_key=True)

    project = models.ForeignKey(Project, related_name='issues', on_delete=models.CASCADE)
    id = models.IntegerField(editable=False)

    class Meta:
        unique_together = ['project', 'id']

    title = models.CharField(max_length=128)

    author = models.ForeignKey(User, related_name='+', on_delete=models.PROTECT)

    opened_at = models.DateTimeField(auto_now_add=True)

    due_date = models.DateTimeField(blank=True, null=True)

    closed = models.BooleanField(default=False)

    labels = models.ManyToManyField(Label, blank=True,
            related_name='issues')

    milestone = models.ForeignKey(Milestone, blank=True, null=True,
            related_name='issues', on_delete=models.SET_NULL)

    assignee = models.ForeignKey(User, blank=True, null=True, related_name='+',
            on_delete=models.SET_NULL)

    subscribers = models.ManyToManyField(User, blank=True,
            related_name='subscribed_issues')

    @staticmethod
    def next_id(project):

        last_issue = project.issues.last()
        if last_issue:
            return last_issue.id + 1
        else:
            return 1

    @property
    def comments(self):

        return self.events.filter(code=Event.COMMENT)

    @property
    def overdue(self):

        if self.due_date:
            return self.due_date < timezone.now()
        else:
            return False

    def getdescevent(self):
        desc = self.events.filter(code=Event.DESCRIBE)
        if desc.exists():
            return desc.first()
        else:
            return None

    def getdesc(self):
        desc = self.getdescevent()
        if desc:
            return desc.additionnal_section
        else:
            return None

    def setdesc(self, value):
        desc = self.getdescevent()
        if desc:
            desc.additionnal_section = value
            desc.save()
        else:
            desc = Event(issue=self, author=self.author, code=Event.DESCRIBE,
                    additionnal_section=value)
            desc.save()

    def deldesc(self):
        desc = self.getdescevent()
        if desc:
            desc.delete()

    description = property(getdesc, setdesc, deldesc)

    def add_label(self, author, label, commit=True):
        if self.labels.filter(pk=label.pk).exists():
            return
        self.labels.add(label)
        if commit:
            self.save()
        event = Event(issue=self, author=author,
                code=Event.ADD_LABEL, args={'label': label.id})
        event.save()

    def remove_label(self, author, label, commit=True):
        self.labels.remove(label)
        if commit:
            self.save()
        event = Event(issue=self, author=author,
                code=Event.DEL_LABEL, args={'label': label.id})
        event.save()

    def add_milestone(self, author, milestone, commit=True):
        if self.milestone == milestone:
            return
        if self.milestone:
            event = Event(issue=self, author=author,
                    code=Event.CHANGE_MILESTONE,
                    args={'old_milestone': self.milestone.name,
                          'new_milestone': milestone.name})
            event.save()
        else:
            event = Event(issue=self, author=author,
                    code=Event.SET_MILESTONE,
                    args={'milestone': milestone.name})
            event.save()
        self.milestone = milestone
        if commit:
            self.save()

    def remove_milestone(self, author, milestone, commit=True):
        self.milestone = None
        if commit:
            self.save()
        event = Event(issue=self, author=author,
                code=Event.UNSET_MILESTONE,
                args={'milestone': milestone.name})
        event.save()

    def have_unread_message(self, user):
        if not user.is_authenticated:
            return False
        try:
            readstate = self.readstates.get(user=user)
        except ObjectDoesNotExist:
            return True
        return self.events.filter(date__gt=readstate.lastread).exists()

    def get_unread_event_nb(self, user):
        if not user.is_authenticated:
            return 0
        try:
            readstate = self.readstates.get(user=user)
        except ObjectDoesNotExist:
            return self.events.count()
        return self.events.filter(date__gt=readstate.lastread).count()

    def mark_as_read(self, user):
        if not user.is_authenticated:
            return timezone.now()
        try:
            readstate = self.readstates.get(user=user)
            olddate = readstate.lastread
        except ObjectDoesNotExist:
            readstate = ReadState(issue=self, user=user)
            olddate = self.opened_at
        readstate.lastread = timezone.now()
        readstate.save()
        return olddate

    def __str__(self):
        return self.title

class ReadState(models.Model):

    issue = models.ForeignKey(Issue, related_name="%(class)ss", on_delete=models.CASCADE)

    user = models.ForeignKey(User, related_name='%(class)ss', on_delete=models.CASCADE)

    lastread = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('issue', 'user')

    def __str__(self):
        return "%s : User=%s lastread=%s" % (self.issue, self.user, self.lastread)


class Event(models.Model):

    UNKNOW = 0
    CLOSE = 1
    REOPEN = 2
    RENAME = 3
    ADD_LABEL = 4
    DEL_LABEL = 5
    SET_MILESTONE = 6
    CHANGE_MILESTONE = 7
    UNSET_MILESTONE = 8
    REFERENCE = 9
    COMMENT = 10
    DESCRIBE = 11
    ASSIGN = 12
    UNASSIGN = 13
    SET_DUE_DATE = 14
    CHANGE_DUE_DATE = 15
    UNSET_DUE_DATE = 16

    issue = models.ForeignKey(Issue, related_name="%(class)ss", on_delete=models.CASCADE)

    date = models.DateTimeField(auto_now_add=True)

    author = models.ForeignKey(User, on_delete=models.PROTECT)

    code = models.IntegerField(default=UNKNOW)

    _args = models.CharField(max_length=1024, blank=True, default="{}")

    def getargs(self):
        return json.loads(self._args)

    def setargs(self, args):
        self._args = json.dumps(args)

    def delargs(self):
        self._args = "{}"
    args = property(getargs, setargs, delargs)

    additionnal_section = models.TextField(blank=True, default="")

    def editable(self):

        return self.code == Event.COMMENT or self.code == Event.DESCRIBE


    def editable_by(self, request):
        if not self.editable():
            return False

        if request.user.has_perm('modify_comment', self.issue.project) and self.code == Event.COMMENT:
            return True
        elif request.user.has_perm('modify_issue', self.issue.project) and self.code == Event.DESCRIBE:
            return True
        elif not request.user.has_perm('modify_own_comment', self.issue.project) or \
                not self.author == request.user:
            return False

        policy = get_current_site(request).settings.edit_policy
        if policy == Settings.EDIT_TIMEOUT:
            return self.date + timedelta(minutes=get_current_site(request).settings.edit_policy_timeout) > timezone.now()
        elif policy == Settings.EDIT_NOMORECOMMENT:
            return not self.issue.events.filter(code=Event.COMMENT, date__gt=self.date).exists()
        return True

    def glyphicon(self):

        if self.code == Event.COMMENT:
            return "comment"
        elif self.code == Event.DESCRIBE:
            return "edit"
        elif self.code == Event.CLOSE:
            return "ban-circle"
        elif self.code == Event.REOPEN:
            return "refresh"
        elif self.code == Event.RENAME:
            return "transfer"
        elif self.code == Event.ADD_LABEL \
                or self.code == Event.DEL_LABEL:
            return "tag"
        elif self.code == Event.SET_MILESTONE \
                or self.code == Event.CHANGE_MILESTONE \
                or self.code == Event.UNSET_MILESTONE:
            return "road"
        elif self.code == Event.REFERENCE:
            return "transfer"
        elif self.code == Event.ASSIGN \
                or self.code == Event.UNASSIGN:
            return "user"
        elif self.code == Event.SET_DUE_DATE \
                or self.code == Event.CHANGE_DUE_DATE \
                or self.code == Event.UNSET_DUE_DATE:
            return "calendar"
        else:
            return "cog"

    def activity(self):

        args = {k: escape(v) for k, v in self.args.items()}

        if self.code == Event.DESCRIBE:
            description = "created issue"
        elif self.code == Event.COMMENT:
            description = "commented on issue"
        elif self.code == Event.CLOSE:
            description = "closed issue"
        elif self.code == Event.REOPEN:
            description = "reopened issue"
        elif self.code == Event.RENAME:
            description = "changed the title of issue"
        elif self.code == Event.ADD_LABEL or self.code == Event.DEL_LABEL:
            label = Label.objects.get(id=args['label'])
            if self.code == Event.ADD_LABEL:
                action = 'added'
            else:
                action = 'removed'
            description = '%s the <a href="%s" class="label" ' \
                          'style="%s">%s</a> label to issue' \
                          % (action, label.url, label.style, label)
        elif self.code == Event.SET_MILESTONE \
                or self.code == Event.UNSET_MILESTONE:
            milestone = Milestone(name=args['milestone'],
                    project=self.issue.project)
            if self.code == Event.SET_MILESTONE:
                action = 'added to'
            else:
                action = 'removed from'
            description = '%s the <span class="glyphicon ' \
                          'glyphicon-road"></span> <a href="%s">' \
                          '<b>%s</b></a> milestone the issue' \
                          % (action, milestone.url, milestone)
        elif self.code == Event.CHANGE_MILESTONE:
            old_ms = Milestone(name=args['old_milestone'],
                    project=self.issue.project)
            new_ms = Milestone(name=args['new_milestone'],
                    project=self.issue.project)
            description = 'moved from the <span class="glyphicon ' \
                          'glyphicon-road"></span> <a href="%s">' \
                          '<b>%s</b></a> milestone ' \
                          'to the <span class="glyphicon ' \
                          'glyphicon-road"></span> <a href="%s">' \
                          '<b>%s</b></a> milestone the issue' \
                          % (old_ms.url, old_ms, new_ms.url, new_ms)
        elif self.code == Event.REFERENCE:
            description = "referenced the issue"
        elif self.code == Event.SET_DUE_DATE:
            due_date = datetime.fromtimestamp(float(args['due_date']))
            description = 'set the due date to <em>%s</em> of issue' \
                          % due_date
        elif self.code == Event.CHANGE_DUE_DATE:
            old_due_date = datetime.fromtimestamp(float(args['old_due_date']))
            new_due_date = datetime.fromtimestamp(float(args['new_due_date']))
            description = 'changed the due date from <em>%s</em> to ' \
                          '<em>%s</em> of issue' \
                          % (old_due_date, new_due_date)
        elif self.code == Event.UNSET_DUE_DATE:
            description = 'removed the due date of issue'
        else:
            return None

        return description

    def __str__(self):

        args = {k: escape(v) for k, v in self.args.items()}

        if self.code == Event.COMMENT or self.code == Event.DESCRIBE:
            description = "commented"
        elif self.code == Event.CLOSE:
            description = "closed this issue"
        elif self.code == Event.REOPEN:
            description = "reopened this issue"
        elif self.code == Event.RENAME:
            description = "changed the title from <mark>%s</mark> " \
                          "to <mark>%s</mark>" \
                          % (args['old_title'], args['new_title'])
        elif self.code == Event.ADD_LABEL or self.code == Event.DEL_LABEL:
            label = Label.objects.get(id=args['label'])
            if self.code == Event.ADD_LABEL:
                action = 'added'
            else:
                action = 'removed'
            description = '%s the <a href="%s" class="label" ' \
                          'style="%s">%s</a> label' \
                          % (action, label.url, label.style, label)
        elif self.code == Event.SET_MILESTONE \
                or self.code == Event.UNSET_MILESTONE:
            milestone = Milestone(name=args['milestone'],
                    project=self.issue.project)
            if self.code == Event.SET_MILESTONE:
                action = 'added'
            else:
                action = 'removed'
            description = '%s this to the <span class="glyphicon ' \
                          'glyphicon-road"></span> <a href="%s">' \
                          '<b>%s</b></a> milestone' \
                          % (action, milestone.url, milestone)
        elif self.code == Event.CHANGE_MILESTONE:
            old_ms = Milestone(name=args['old_milestone'],
                    project=self.issue.project)
            new_ms = Milestone(name=args['new_milestone'],
                    project=self.issue.project)
            description = 'moved this from the <span class="glyphicon ' \
                          'glyphicon-road"></span> <a href="%s">' \
                          '<b>%s</b></a> milestone ' \
                          'to the <span class="glyphicon ' \
                          'glyphicon-road"></span> <a href="%s">' \
                          '<b>%s</b></a> milestone' \
                          % (old_ms.url, old_ms, new_ms.url, new_ms)
        elif self.code == Event.REFERENCE:
            description = "referenced this issue"
        elif self.code == Event.REFERENCE:
            description = "referenced the issue"
        elif self.code == Event.SET_DUE_DATE:
            due_date = datetime.fromtimestamp(float(args['due_date']))
            description = 'set the due date to <em>%s</em>' \
                          % due_date
        elif self.code == Event.CHANGE_DUE_DATE:
            old_due_date = datetime.fromtimestamp(float(args['old_due_date']))
            new_due_date = datetime.fromtimestamp(float(args['new_due_date']))
            description = 'changed the due date from <em>%s</em> to <em>%s</em>' \
                          % (old_due_date, new_due_date)
        elif self.code == Event.UNSET_DUE_DATE:
            description = 'removed the due date'
        else:
            return None

        return description
