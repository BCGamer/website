import os
import uuid
import logging

from autoslug import AutoSlugField
from autoslug.utils import slugify
from django.contrib.auth.models import User
from django.db import models

from website.apps.salesbro.models import Ticket, TicketOption
from sorl.thumbnail import ImageField

logger = logging.getLogger(__name__)


def generate_slug(instance):
    name = instance.name
    return slugify(name)


def rename_image(instance, filename):
    extension = filename.split('.')[-1]
    filename = '%s.%s' % (uuid.uuid4(), extension)
    return os.path.join('eventbro/images', filename)


class Convention(models.Model):
    uid = models.UUIDField(default=uuid.uuid4, unique=True, primary_key=True, editable=False,)
    name = models.CharField(max_length=100)
    slug = AutoSlugField(populate_from='name', unique=True,)
    description = models.TextField(blank=True, null=True)
    start = models.DateTimeField()
    end = models.DateTimeField()
    published = models.BooleanField(default=False)

    def __unicode__(self):
        return '{name}'.format(name=self.name)


class Sponsor(models.Model):
    PLATINUM = 1
    GOLD = 2
    SILVER = 3
    BRONZE = 4
    SPONSOR_LEVEL_CHOICES = (
        (PLATINUM, 'Presenting'),
        (GOLD, 'Gold'),
        (SILVER, 'Silver'),
        (BRONZE, 'Bronze'),
    )

    uid = models.UUIDField(default=uuid.uuid4, unique=True, primary_key=True, editable=False,)
    name = models.CharField(max_length=255)
    slug = AutoSlugField(populate_from='name', unique=True,)
    description = models.TextField(blank=True, null=True)
    logo = ImageField(upload_to=rename_image, blank=True, null=True)
    level = models.PositiveSmallIntegerField(blank=True, null=True, choices=SPONSOR_LEVEL_CHOICES)
    convention = models.ForeignKey(Convention, related_name='sponsor_convention_uid')

    def __unicode__(self):
        return '{name}'.format(name=self.name)


class EventType(models.Model):
    uid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, unique=True)
    name = models.CharField(max_length=100, unique=True)
    slug = AutoSlugField(populate_from='name', unique=True,)
    overlapping = models.BooleanField(verbose_name='Overlapping event registration', default=False)

    def __unicode__(self):
        return '{name}'.format(name=self.name)


class Event(models.Model):
    uid = models.UUIDField(primary_key=True, editable=False, default=uuid.uuid4)
    convention = models.ForeignKey(Convention, related_name='event_convention_uid')
    name = models.CharField(verbose_name='Event Name', max_length=100)
    slug = AutoSlugField(populate_from='name', unique=True,)
    description = models.TextField(blank=True, null=True)
    start = models.DateTimeField(verbose_name='Start Time')
    end = models.DateTimeField(verbose_name='End Time')
    size = models.PositiveSmallIntegerField(verbose_name='Max Size', blank=True, null=True)
    published = models.BooleanField(default=False)
    valid_options = models.ManyToManyField(TicketOption, related_name='event_valid_tickets',
                                           verbose_name='Valid participants')
    group_event = models.BooleanField(default=False, verbose_name='Is group event')
    require_game_id = models.BooleanField(default=False, verbose_name='Require special ID')
    game_id_name = models.CharField(max_length=100, blank=True, null=True,
                                    verbose_name='Unique identifier')
    event_type = models.ForeignKey(EventType, related_name='event_type_id', blank=True, null=True)
    image = ImageField(upload_to=rename_image, blank=True, null=True)
    prizes = models.TextField(blank=True, null=True)
    rules = models.TextField(blank=True, null=True)
    sponsor = models.ForeignKey(Sponsor, related_name='event_sponsor', blank=True, null=True)
    organizer = models.CharField(max_length=100, blank=True, null=True)

    def __unicode__(self):
        return '{name}'.format(name=self.name)

    def available_spots(self):
        registered = Registration.objects.filter(event=self).count()
        available = self.size - registered
        return available

    def is_full(self):
        registered = Registration.objects.filter(event=self).count()
        if registered >= self.size:
            return True
        else:
            return False

    def get_registration_form_class(self):

        from website.apps.eventbro.forms import GroupEventRegistrationForm, IndividualEventRegistrationForm

        if self.group_event:
            return GroupEventRegistrationForm
        else:
            return IndividualEventRegistrationForm

    def get_blank_registration_form(self):
        form_class = self.get_registration_form_class()
        return form_class(event=self)

    def register(self, user, group=None, game_id=None, is_captain=False):
        """
        Registers a user for an event if they are not registered
        """

        defaults = {
            'game_id': game_id,
            'group_captain': is_captain,
            'group_name': group,
        }

        registrant, created = Registration.objects.get_or_create(user=user, event=self, defaults=defaults)

        return registrant

    def unregister(self, user):
        """
        Un-registers a user from an event if they are registered
        """
        queryset = self.registrants.filter(user=user)

        try:
            reg = queryset.get()
            reg.delete()
            logger.debug("Unregistered user %s from event %s", user.id, self)

        except Registration.DoesNotExist:
            # Do nothing, user is already unregistered
            pass


class Registration(models.Model):
    user = models.ForeignKey(User, related_name='registration_user')
    event = models.ForeignKey(Event, related_name='registrats', blank=True, null=True)
    date_added = models.DateTimeField(auto_now_add=True)
    group_name = models.CharField(max_length=255, blank=True, null=True, verbose_name='Group Name')
    group_captain = models.BooleanField(default=False)
    game_id = models.CharField(max_length=255, blank=True, null=True, verbose_name='Game ID',
                               help_text='eg Battle.net ID, Summoner ID, etc')
