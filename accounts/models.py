from django.db import models
from django.db.models import Q
from django.contrib.auth.models import AbstractUser
from django.contrib import auth
from django.utils.safestring import mark_safe
from django.urls import reverse


__all__ = ['User', 'Group', 'Team']


class User(AbstractUser):

    class Meta:
        ordering = ['username']

    NOTIFICATIONS_NEVER = 0 # do not change: used as boolean value
    NOTIFICATIONS_OTHERS = 1
    NOTIFICATIONS_ALWAYS = 2
    NOTIFICATIONS_CHOICES = (
        (NOTIFICATIONS_NEVER, 'Never'),
        (NOTIFICATIONS_OTHERS, 'Ignore my actions'),
        (NOTIFICATIONS_ALWAYS, 'Always'),
    )

    notifications = models.IntegerField(choices=NOTIFICATIONS_CHOICES,
            default=NOTIFICATIONS_OTHERS)

    @property
    def teams(self):
        query = Q(groups__in=self.groups.all()) | Q(users=self)
        return Team.objects.filter(query).distinct()

    @property
    def username_and_fullname(self):
        fullname = self.fullname
        if fullname:
            return "%s (%s)" % (self.username, fullname)
        else:
            return self.username

    @property
    def fullname(self):
        fullname = ''
        if self.first_name:
            fullname += self.first_name
        if self.last_name:
            if fullname:
                fullname += ' '
            fullname += self.last_name
        return fullname

    def url(self, project):
        url = reverse('list-issue', kwargs={'project': project})
        url += '?q=is:open%20author:' + self.username
        return mark_safe(url)

    def __str__(self):
        return self.username


class Group(auth.models.Group):

    class Meta:
        ordering = ['name']
        proxy = True

    @property
    def users(self):
        return User.objects.filter(groups=self)


class Team(models.Model):

    class Meta:
        ordering = ['name']

    name = models.CharField(max_length=128, unique=True)

    # We dont want related field on User object because we use
    # a special function that retrieve also team through group
    users = models.ManyToManyField(User, blank=True, related_name='teams+')
    groups = models.ManyToManyField(Group, blank=True, related_name='teams')

    def __str__(self):
        return self.name
