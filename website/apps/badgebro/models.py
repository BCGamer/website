import uuid
from decimal import Decimal

import StringIO
import qrcode
from django.conf import settings
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.db import models, transaction

from cartridge.shop.models import Order, OrderItem
from django.utils import timezone

from website.apps.salesbro.models import TicketOption


class BadgeGroup(object):

    VENDOR = 'vendor'
    TOURNAMENT = 'tournament'
    STAFF = 'staff'
    GENERAL = 'general'

    CHOCIES = (
        (VENDOR, 'Vendor'),
        (TOURNAMENT, 'Tournament'),
        (STAFF, 'Staff'),
        (GENERAL, 'General')
    )


class BadgeManager(models.Manager):

    def create_badge(self, order, item, ticket_option):
        """
        Creates a badge for a given order
        """

        ticket_option = TicketOption.objects.get(sku=item.sku)
        ticket = ticket_option.ticket

        badge = self.model()
        badge.order = order
        badge.order_item = item
        badge.ticket = ticket_option
        badge.first_name = order.billing_detail_first_name
        badge.last_name = order.billing_detail_last_name
        badge.option = ticket_option.title

        if ticket.title.endswith(' Pass'):
            badge.type = ticket.title[:-5]
        else:
            badge.type = ticket.title

        badge.save()

        return badge

    def option_choices(self):
        """
        Get all distinct existing non-null values for option
        """
        queryset = self.get_queryset()
        queryset = queryset.distinct()
        queryset = queryset.values_list('option', flat=True)
        queryset = queryset.exclude(option__isnull=True)

        return queryset

    def type_choices(self):
        """
        Get all distinct existing non-null values for type
        """
        queryset = self.get_queryset()
        queryset = queryset.distinct()
        queryset = queryset.values_list('type', flat=True)
        queryset = queryset.exclude(type__isnull=True)

        return queryset


class Badge(models.Model):

    uid = models.CharField(max_length=34, unique=True)

    user = models.OneToOneField(settings.AUTH_USER_MODEL, blank=True, null=True)

    # We don't necessarily need order/order items for a badge.
    # eg. Dobbo's badge would not have an order associated with it
    order = models.ForeignKey(Order, related_name='badge_order_id', blank=True, null=True)
    order_item = models.ForeignKey(OrderItem, related_name='badge_order_item', blank=True, null=True)

    ticket = models.ForeignKey(TicketOption, related_name='badges')

    # Date/Time tracking
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)
    printed = models.DateTimeField(blank=True, null=True)
    collected = models.DateTimeField(blank=True, null=True)

    network = models.CharField(max_length=20, default=BadgeGroup.GENERAL, choices=BadgeGroup.CHOCIES)

    # Need to add denormalized first/last name for the user onto the badge as
    # badges purchased at event may not have a user object to associate
    first_name = models.CharField(max_length=100, blank=True, null=True)
    last_name = models.CharField(max_length=100, blank=True, null=True)

    # Denormalizing 'ticket option' values on the badge as the ticket
    # might be different if the person is an exhibitor/staff
    type = models.CharField(max_length=30, blank=True, null=True)
    option = models.CharField(max_length=30, blank=True, null=True)

    qr_code = models.ImageField(blank=True, null=True, upload_to='badges/qrcodes/%Y')

    objects = BadgeManager()

    def save(self, *args, **kwargs):

        if not self.uid:
            self.uid = self.generate_uid()

        super(Badge, self).save(*args, **kwargs)

        if not self.qr_code:
            self.create_qr_code()

    def __unicode__(self):
        # return '{user}'.format(user=self.user_id)
        return '{uid}'.format(uid=self.uid)

    def mark_printed(self):
        self.printed = timezone.now()
        self.save()

    def mark_collected(self):
        self.collected = timezone.now()
        self.save()

    def generate_uid(self):
        return 'BA{uid}'.format(uid=uuid.uuid4().hex)

    def release(self):
        with transaction.atomic():
            self.user.registration_user.all().delete()
            self.user = None
            self.save()

    def create_qr_code(self):
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=4,
        )
        qr.add_data(self.uid)

        qr.make(fit=True)

        img = qr.make_image()

        tempfile_io = StringIO.StringIO()
        img.save(tempfile_io, kind='JPEG')

        image_file = InMemoryUploadedFile(tempfile_io, None, 'rotate.jpg','image/jpeg', tempfile_io.len, None)

        file_name = 'badge_%s.jpg' % self.id
        self.qr_code.save(file_name, image_file)
        self.save()

    def get_convention_year(self):
        # replace this next year this is bad :)
        return '2016'

    def get_partial_badge_id(self):
        return '{uid}'.format(uid=self.uid[-12:])


class PaymentMethod(object):

    VISA = 'visa'
    MASTERCARD = 'mastercard'
    AMEX = 'amex'
    DISCOVER = 'discover'
    DEBIT = 'debit'
    CASH = 'cash'

    CHOICES = (
        (VISA, 'Visa'),
        (MASTERCARD, 'Mastercard'),
        (DISCOVER, 'Discover'),
        (AMEX, 'American Express'),
        (DEBIT, 'Debit'),
        (CASH, 'Cash')
    )


class UpgradeTransaction(models.Model):

    old_ticket = models.ForeignKey(TicketOption, related_name='+')
    new_ticket = models.ForeignKey(TicketOption, related_name='+')

    badge = models.ForeignKey(Badge, related_name='upgrades')

    payment_method = models.CharField(max_length=10, choices=PaymentMethod.CHOICES)

    difference = models.IntegerField()
    tax = models.IntegerField()
    total = models.IntegerField()

    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    def save(self, **kwargs):

        with transaction.atomic():

            old_price = int(self.badge.order_item.unit_price * 100)
            new_price = int(self.new_ticket.price() * 100)

            self.difference = new_price - old_price
            self.tax = int(self.difference * 0.05)
            self.total = self.tax + self.difference

            super(UpgradeTransaction, self).save(**kwargs)

            self.badge.ticket = self.new_ticket
            self.badge.option = self.new_ticket.title

            if self.new_ticket.title.endswith(' Pass'):
                self.badge.type = self.new_ticket.title[:-5]
            else:
                self.badge.type = self.new_ticket.title

            self.badge.save()
