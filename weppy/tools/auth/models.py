# -*- coding: utf-8 -*-
"""
    weppy.tools.auth.models
    -----------------------

    Provides models for the authorization system.

    :copyright: (c) 2014-2016 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

from datetime import datetime
from ..._compat import iterkeys
from ...globals import current, request
from ...orm import Model, Field, before_insert, rowmethod
from ...security import uuid


def _now():
    if hasattr(current, 'request'):
        return request.now
    return datetime.utcnow()


class TimestampedModel(Model):
    created_at = Field('datetime', default=_now, rw=False)
    updated_at = Field('datetime', default=_now, update=_now, rw=False)


class AuthModel(Model):
    auth = None

    form_registration_rw = {}
    form_profile_rw = {}

    def __super_method(self, name):
        return getattr(super(AuthModel, self), '_Model__' + name)

    def _define_(self):
        self.__super_method('define_validation')()
        self.__super_method('define_defaults')()
        self.__super_method('define_updates')()
        self.__super_method('define_representation')()
        self.__super_method('define_computations')()
        self.__super_method('define_callbacks')()
        self.__super_method('define_scopes')()
        self.__super_method('define_indexes')()
        self.__hide_all()
        self.__super_method('define_form_utils')
        self.__define_authform_utils()
        self.setup()

    #def __define_extra_fields(self):
    #    self.auth.settings.extra_fields['auth_user'] = self.fields

    def __hide_all(self):
        alwaysvisible = ['first_name', 'last_name', 'password', 'email']
        for field in self.table.fields:
            if field not in alwaysvisible:
                self.table[field].writable = self.table[field].readable = \
                    False

    def __base_visibility(self, form_type):
        exclude = []
        if form_type == 'profile_fields':
            exclude.append('password')
            exclude.append('email')
        return [
            field.name for field in self.table if
            field.writable and field.name not in exclude]

    def __define_authform_utils(self):
        settings_map = {
            'register_fields': 'form_registration_rw',
            'profile_fields': 'form_profile_rw'
        }
        for setting, attr in settings_map.items():
            rwdata = self.auth.settings[setting] or \
                self.__base_visibility(setting)
            if not isinstance(rwdata, dict):
                rwdata = {'writable': list(rwdata), 'readable': list(rwdata)}
            for field, value in getattr(self, attr).items():
                if isinstance(value, (tuple, list)):
                    readable, writable = value
                else:
                    readable = writable = value
                if readable:
                    rwdata['readable'].append(field)
                else:
                    if field in rwdata['readable']:
                        rwdata['readable'].remove(field)
                if writable:
                    rwdata['writable'].append(field)
                else:
                    if field in rwdata['writable']:
                        rwdata['writable'].remove(field)
            for key in iterkeys(rwdata):
                rwdata[key] = list(set(rwdata[key]))
            self.auth.settings[setting] = rwdata


class AuthUserBasic(AuthModel, TimestampedModel):
    tablename = "auth_users"
    format = '%(email)s (%(id)s)'
    #: injected by Auth
    #  has_many(
    #      {'memberships': 'AuthMembership'},
    #      {'authevents': 'AuthEvent'},
    #      {'authgroups': {'via': 'memberships'}},
    #      {'permissions': {'via': 'authgroups'}},
    #  )

    email = Field(length=255, unique=True)
    password = Field('password', length=512)
    registration_key = Field(length=512, rw=False, default='')
    reset_password_key = Field(length=512, rw=False, default='')
    registration_id = Field(length=512, rw=False, default='')

    form_labels = {
        'email': 'E-mail',
        'password': 'Password'
    }

    @before_insert
    def set_registration_key(self, fields):
        if self.auth.settings.registration_requires_verification and not \
                fields.get('registration_key'):
            fields['registration_key'] = uuid()

    @rowmethod('disable')
    def _set_disabled(self, row):
        return row.update_record(registration_key='disabled')

    @rowmethod('block')
    def _set_blocked(self, row):
        return row.update_record(registration_key='blocked')

    @rowmethod('allow')
    def _set_allowed(self, row):
        return row.update_record(registration_key='')


class AuthUser(AuthUserBasic):
    format = '%(first_name)s %(last_name)s (%(id)s)'

    first_name = Field(length=128, notnull=True)
    last_name = Field(length=128, notnull=True)

    form_labels = {
        'first_name': 'First name',
        'last_name': 'Last name',
    }


class AuthGroup(TimestampedModel):
    format = '%(role)s (%(id)s)'
    #: injected by Auth
    #  has_many(
    #      {'memberships': 'AuthMembership'},
    #      {'permissions': 'AuthPermission'},
    #      {'users': {'via': 'memberships'}}
    #  )

    role = Field(length=255, default='', unique=True)
    description = Field('text')

    form_labels = {
        'role': 'Role',
        'description': 'Description'
    }


class AuthMembership(TimestampedModel):
    #: injected by Auth
    #  belongs_to({'user': 'AuthUser'}, {'authgroup': 'AuthGroup'})
    pass


class AuthPermission(TimestampedModel):
    #: injected by Auth
    #  belongs_to({'authgroup': 'AuthGroup'})

    name = Field(length=512, default='default', notnull=True)
    table_name = Field(length=512)
    record_id = Field('int', default=0)

    validation = {
        'record_id': {'in': {'range': (0, 10**9)}}
    }

    form_labels = {
        'name': 'Name',
        'table_name': 'Object or table name',
        'record_id': 'Record ID'
    }


class AuthEvent(TimestampedModel):
    #: injected by Auth
    #  belongs_to({'user': 'AuthUser'})

    client_ip = Field()
    origin = Field(length=512, notnull=True)
    description = Field('text', notnull=True)

    default_values = {
        'client_ip': lambda:
            request.client if hasattr(current, 'request') else 'unavailable',
        'origin': 'auth',
        'description': ''
    }

    #: labels injected by Auth
    form_labels = {
        'client_ip': 'Client IP',
        'origin': 'Origin',
        'description': 'Description'
    }


"""
class AuthUserSigned(AuthUser):
    is_active = Field('bool', default=True, rw=False)
    created_on = Field('datetime', default=lambda: datetime.utcnow(), rw=False)
    created_by = Field('reference auth_user', default=auth.user_id, rw=False)
    modified_on = Field('datetime', default=lambda: datetime.utcnow(),
                        update=lambda: datetime.utcnow(), rw=False),
    modified_by = Field('reference auth_user', default=auth.user_id,
                        update=auth.user_id, rw=False)
"""
