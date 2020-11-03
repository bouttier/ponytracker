from django.db import models
from django.db.models import Q

from tracker.models import Project
from accounts.models import *


__all__ = ['GlobalPermission', 'ProjectPermission']


class PermissionField(models.BooleanField):
    pass


class GlobalPermissionField(PermissionField):
    pass


class ProjectPermissionField(PermissionField):
    pass


class PermissionModel(models.Model):

    class Meta:
        abstract = True

    GRANTEE_USER = 0
    GRANTEE_GROUP = 1
    GRANTEE_TEAM = 2
    GRANTEE_TYPE = (
        (GRANTEE_USER, 'User'),
        (GRANTEE_GROUP, 'Group'),
        (GRANTEE_TEAM, 'Team'),
    )

    grantee_type = models.IntegerField(choices=GRANTEE_TYPE,
            default=GRANTEE_USER, verbose_name="Grantee type")
    grantee_id = models.IntegerField()

    def get_grantee(self):
        if self.grantee_type == self.GRANTEE_USER:
            Model = User
        elif self.grantee_type == self.GRANTEE_GROUP:
            Model = Group
        else:
            Model = Team
        return Model.objects.get(id=self.grantee_id)

    def set_grantee(self, grantee):
        if isinstance(grantee, User):
            self.grantee_type = self.GRANTEE_USER
        elif isinstance(grantee, Group):
            self.grantee_type = self.GRANTEE_GROUP
        elif isinstance(grantee, Team):
            self.grantee_type = self.GRANTEE_TEAM
        else:
            raise ValueError('Grantee object must be '
                    'an User, a Group or a Team instance.')
        self.grantee_id = grantee.id

    grantee = property(get_grantee, set_grantee)

    def granted_to(self, user):
        if not user.is_authenticated:
            return False
        if self.grantee_type == self.GRANTEE_USER:
            return user.id == self.grantee_id
        elif self.grantee_type == self.GRANTEE_GROUP:
            return user.groups.filter(id=self.grantee_id).exists()
        elif self.grantee_type == self.GRANTEE_TEAM:
            return Team.objects.filter(id=self.grantee_id) \
                .filter(Q(groups__in=user.groups.all()) | Q(users=user)) \
                .exists()
        else:
            return False

    @property
    def all_perms(self):
        for field in self._meta.fields:
            if isinstance(field, PermissionField):
                yield field.name

    @property
    def all_perms_fields_values(self):
        for field in self._meta.fields:
            if isinstance(field, PermissionField):
                yield (field, getattr(self, field.name))

    @property
    def type(self):
        return self.get_grantee_type_display()

    @property
    def name(self):
        return self.grantee.__str__()

    def __str__(self):
        return self.grantee.__str__() + "'s permissions"


class GlobalPermission(PermissionModel):

    class Meta:
        unique_together = ('grantee_type', 'grantee_id')

    @property
    def global_perms_fields_values(self):
        for field in self._meta.fields:
            if isinstance(field, GlobalPermissionField):
                yield (field, getattr(self, field.name))

    @property
    def project_perms_fields_values(self):
        for field in self._meta.fields:
            if isinstance(field, ProjectPermissionField):
                yield (field, getattr(self, field.name))

    # Global permissions

    create_project = GlobalPermissionField(default=True,
            verbose_name='Create project')
    modify_project = GlobalPermissionField(default=False,
            verbose_name='Modify project')
    delete_project = GlobalPermissionField(default=False,
            verbose_name='Delete project')

    manage_settings = GlobalPermissionField(default=False,
            verbose_name='Manage settings')
    manage_accounts = GlobalPermissionField(default=False,
            verbose_name='Manage users, groups and teams')
    manage_global_permission = GlobalPermissionField(default=False,
            verbose_name='Manage global permissions')

    # Project permissions, given on ALL projects

    access_project = ProjectPermissionField(default=False,
            verbose_name='Access all project')

    create_issue = ProjectPermissionField(default=False,
            verbose_name='Create issue')
    modify_issue = ProjectPermissionField(default=False,
            verbose_name='Modify issue')
    manage_issue = ProjectPermissionField(default=False,
            verbose_name='Manage issue')
    delete_issue = ProjectPermissionField(default=False,
            verbose_name='Delete issue')

    create_comment = ProjectPermissionField(default=False,
            verbose_name='Create comment')
    modify_comment = ProjectPermissionField(default=False,
            verbose_name='Modify comment')
    modify_own_comment = ProjectPermissionField(default=False,
            verbose_name='Modify his issue and comment')
    delete_comment = ProjectPermissionField(default=False,
            verbose_name='Delete comment')

    manage_tags = ProjectPermissionField(default=False,
            verbose_name='Assign and remove labels and milestones')
    delete_tags = ProjectPermissionField(default=False,
            verbose_name='Delete labels and milestones')

    manage_project_permission = ProjectPermissionField(default=False,
            verbose_name='Manage project permissions')

    def __str__(self):
        return self.grantee.__str__() + "'s global permissions"


class ProjectPermission(PermissionModel):

    class Meta:
        unique_together = ('project', 'grantee_type', 'grantee_id')

    project = models.ForeignKey(Project, related_name='permissions',
            on_delete=models.CASCADE)

    create_issue = PermissionField(default=False,
            verbose_name='Create issue')
    modify_issue = PermissionField(default=False,
            verbose_name='Modify issue')
    manage_issue = PermissionField(default=False,
            verbose_name='Manage issue')
    delete_issue = PermissionField(default=False,
            verbose_name='Delete issue')

    create_comment = PermissionField(default=False,
            verbose_name='Create comment')
    modify_comment = PermissionField(default=False,
            verbose_name='Modify comment')
    modify_own_comment = PermissionField(default=False,
            verbose_name='Modify his issue and comment')
    delete_comment = PermissionField(default=False,
            verbose_name='Delete comment')

    manage_tags = PermissionField(default=False,
            verbose_name='Assign and remove labels and milestones')
    delete_tags = PermissionField(default=False,
            verbose_name='Delete labels and milestones')

    manage_project_permission = PermissionField(default=False,
            verbose_name='Manage project permissions')

    def __str__(self):
        return self.grantee.__str__() + "'s permissions on " \
            + self.project.name + " project"
