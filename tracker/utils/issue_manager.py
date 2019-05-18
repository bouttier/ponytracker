from __future__ import unicode_literals

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Max, Count, F, Q, OuterRef, Subquery, Exists

from tracker.models import Label, Milestone, ReadState, Event
from accounts.models import User

import shlex
from sys import version_info as python_version
from collections import OrderedDict


STATUS_DEFAULT = 'is:open'
STATUS_VALUES = OrderedDict([
        ('is:open', 'Open'),
        ('is:close', 'Closed'),
        ('is:unread', 'Unread'),
        ('*', 'All'),
    ])

SORT_DEFAULT = 'recently-updated'
SORT_VALUES = OrderedDict([
        ('recently-updated', 'Recentely updated'),
        ('least-recently-updated', 'Least recently updated'),
        ('newest', 'Newest'),
        ('oldest', 'Oldest'),
        ('most-urgent', 'Most urgent'),
        ('least-urgent', 'Least urgent'),
#        ('most-commented', 'Most commented'),
#        ('least-commented', 'Least commented'),
    ])


def shell_split(cmd):

   if python_version < (3,):
       cmd = cmd.encode('utf-8')

   args = shlex.split(cmd)

   if python_version < (3,):
       args = [ arg.decode('utf-8') for arg in args ]

   return args


def get_filter_value(key, value):

    if key == 'author':
        return value.username
    elif key == 'label':
        return value.quotted_name
    elif key == 'milestone':
        return value.name
    elif python_version < (3,):
        return unicode(value)
    else:
        return str(value)


class IssueManager:

    def __init__(self, project, filter=None, sort=None, user=None):

        self.project = project
        self.filter = filter or STATUS_DEFAULT
        self.sort = sort or SORT_DEFAULT
        self.user = user

        self.status = None
        self.error = None

        self.labels = Label.objects.filter(project=project, deleted=False)
        self.not_used_labels = self.labels

        self.milestones = Milestone.objects.filter(project=project, deleted=False)
        self.not_used_milestones = self.milestones

        self._constraints = []
        self._filters = []
        self.unread = False

        for constraint in shell_split(self.filter):

            if constraint == '*':
                try:
                    self.handle_is(constraint)
                except ValueError as e:
                    self.error = str(e)
                    break
                continue

            args = constraint.split(':')

            if len(args) != 2:
                self.error = 'There is a syntax error in your filter.'
                break

            key = args[0]
            value = args[1]

            if key == '':
                continue

            handler = getattr(self, 'handle_%s' % key, None)
            if not handler:
                self.error = "Unknown '%s' filtering criterion." % key
                break
            try:
                # If the handler return True, this mean criterion ignored (e.g. doubled)
                skip = handler(value)
            except ValueError as e:
                self.error = str(e)
                break
            if not skip and key != 'is': # status is stored in self.status
                self._constraints += [(key, value)]

        if not self.status:
            self.handle_is(STATUS_DEFAULT.split(':')[1])

    def handle_is(self, value):

        if self.status:
            raise ValueError("The keyword 'is' can appear only once "
                             "and is mutual exclusive with '*'.")

        if value == '*':
            self.status = '*'
        elif value == 'open':
            self.status = 'is:open'
            self._filters.append(Q(closed=False))
        elif value == 'close':
            self.status = 'is:close'
            self._filters.append(Q(closed=True))
        elif value == 'unread':
            self.status = 'is:unread'
            self.unread = True
        else:
            raise ValueError("The keyword 'is' must be followed "
                             "by 'unread', 'open' or 'close'.")

    def handle_label(self, value):

        try:
            label = self.labels.get(name=value)
        except ObjectDoesNotExist:
            raise ValueError("The label '%s' does not exist "
                             "or has been deleted." % value)
        if self.not_used_labels.filter(name=value).exists():
            self._filters.append(Q(labels=label))
            self.not_used_labels = self.not_used_labels.exclude(pk=label.pk)
        else:
            return True

    def handle_milestone(self, value):
        try:
            milestone = self.milestones.get(name=value)
        except ObjectDoesNotExist:
            raise ValueError("The milestone '%s' does not exist." % value)
        if self.not_used_milestones.filter(name=value).exists():
            self._filters.append(Q(milestone=milestone))
            self.not_used_milestones = self.not_used_milestones\
                    .exclude(pk=milestone.pk)
        else:
            return True

    def handle_due(self, value):
        if value == 'yes':
            self._filters.append(Q(due_date__isnull=False))
        elif value == 'no':
            self._filters.append(Q(due_date__isnull=True))
        else:
            raise ValueError("The keyword 'due' must be followed "
                             "by 'yes' or 'no'.")

    def handle_author(self, value):
        try:
            author = User.objects.get(username=value)
        except ObjectDoesNotExist:
            raise ValueError("The user '%s' does not exist." % value)
        self._filters.append(Q(author=author))


    @property
    def issues(self):
        issues = self.project.issues
        for filter in self._filters:
            issues = issues.filter(filter)

        if self.unread and self.user.is_authenticated:
            datelastread = ReadState.objects.filter(issue=OuterRef('pk'),user=self.user)
            datelastupdate = Event.objects.filter(issue=OuterRef('pk')).order_by('-date')
            issues = issues.annotate(datelastupdate=Subquery(datelastupdate.values('date')[:1]), \
                                     datelastread=Subquery(datelastread.values('lastread'))) \
                           .filter(Q(datelastread__isnull=True) | Q(datelastread__lt=F('datelastupdate')))

        if self.sort == 'newest':
            issues = issues.order_by('-opened_at')
        elif self.sort == 'oldest':
            issues = issues.order_by('opened_at')
        elif self.sort == 'most-urgent':
            issues = issues.annotate(null_due_date=Count('due_date'))\
                    .order_by('-null_due_date', 'due_date', 'opened_at')
        elif self.sort == 'least-urgent':
            issues = issues.order_by('-due_date', '-opened_at')
        elif self.sort == 'least-recently-updated':
            issues = issues.annotate(last_activity=Max('events__date'))\
                    .order_by('last_activity')
        else: # recently-updated
            issues = issues.annotate(last_activity=Max('events__date'))\
                    .order_by('-last_activity')

        return issues

    @property
    def resettable(self):
        return bool(len(self._constraints))

    def get_parameters(self, **kwargs):
        url = ''

        if 'status' in kwargs:
            status = kwargs['status']
            del kwargs['status']
        else:
            status = self.status

        if 'sort' in kwargs:
            sort = kwargs['sort']
            del kwargs['sort']
        else:
            sort = self.sort

        if 'reset' in kwargs:
            reset = True
            del kwargs['reset']
        else:
            reset = False

        if status != STATUS_DEFAULT or \
                ( not reset and ( len(self._constraints) or len(kwargs) ) ):
            if url:
                url += '&q='
            else:
                url += 'q='
            filter = ' ' + status
            if not reset:
                constraints = list(self._constraints)
                for key, value in kwargs.items():
                    value = get_filter_value(key, value)
                    if (key, value) in constraints:
                        # this criterions is already present
                        continue
                    # label criterions can appears several time
                    if key != 'label':
                        # cleaning old(s) value(s) before inserting new one
                        constraints = [c for c in constraints if key != c[0]]
                    constraints += [(key, value)]
                for key, value in constraints:
                    filter += ' %s:%s' % (key, value)
            url += filter[1:]

        if sort != SORT_DEFAULT:
            if url:
                url += '&sort='
            else:
                url += 'sort='
            url += sort

        return url
