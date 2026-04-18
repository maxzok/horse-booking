from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from datetime import date, timedelta
from django.db.models import Sum


class Client(models.Model):
    """Клиент клуба (может быть связан с User для онлайн-доступа)"""

    user = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Пользователь",
    )
    first_name = models.CharField(max_length=100, verbose_name="Имя")
    last_name = models.CharField(max_length=100, verbose_name="Фамилия")
    phone = models.CharField(max_length=20, unique=True, verbose_name="Телефон")
    email = models.EmailField(blank=True, verbose_name="Email")
    birth_date = models.DateField(null=True, blank=True, verbose_name="Дата рождения")
    riding_level = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name="Уровень катания (1-5)",
    )
    medical_notes = models.TextField(blank=True, verbose_name="Медицинские заметки")
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Клиент"
        verbose_name_plural = "Клиенты"
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return f"{self.last_name} {self.first_name}"

    def active_subscription(self):
        """Возвращает активный абонемент клиента (если есть)"""
        today = timezone.now().date()
        return self.subscriptions.filter(
            start_date__lte=today, end_date__gte=today, remaining_visits__gt=0
        ).first()


class Trainer(models.Model):
    """Тренер"""

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, verbose_name="Пользователь"
    )
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    specialization = models.CharField(
        max_length=200, blank=True, verbose_name="Специализация"
    )
    max_horses_per_day = models.PositiveSmallIntegerField(
        default=4, verbose_name="Макс. лошадей в день"
    )
    is_active = models.BooleanField(default=True)
    commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=50.00,
        verbose_name="Процент от стоимости услуг (%)",
    )

    class Meta:
        verbose_name = "Тренер"
        verbose_name_plural = "Тренеры"

    def __str__(self):
        return f"{self.last_name} {self.first_name}"

    def get_workload_for_date(self, date):
        """Возвращает количество записей тренера на конкретную дату"""
        return self.booking_set.filter(
            start_time__date=date, status__in=["confirmed", "completed"]
        ).count()

    def get_monthly_stats(self, year, month):
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1)
        else:
            end_date = date(year, month + 1, 1)

        bookings = self.booking_set.filter(
            start_time__date__gte=start_date,
            start_time__date__lt=end_date,
            status__in=["completed", "confirmed"],
        )

        total_bookings = bookings.count()
        total_revenue = sum(
            b.price_charged if b.price_charged else b.service_type.default_price
            for b in bookings
        )
        trainer_earned = total_revenue * (self.commission_rate / 100)

        return {
            "total_bookings": total_bookings,
            "total_revenue": total_revenue,
            "commission_rate": float(self.commission_rate),
            "earned": trainer_earned,
            "month": month,
            "year": year,
        }


class Horse(models.Model):
    """Лошадь"""

    name = models.CharField(max_length=100, verbose_name="Кличка")
    breed = models.CharField(max_length=100, blank=True)
    age = models.PositiveSmallIntegerField(null=True, blank=True)
    HORSE_LEVELS = [(i, str(i)) for i in range(1, 6)]
    level = models.PositiveSmallIntegerField(
        choices=HORSE_LEVELS, default=1, verbose_name="Уровень подготовки (1-5)"
    )
    max_workload_per_day = models.PositiveSmallIntegerField(
        default=3, verbose_name="Макс. занятий в день"
    )
    rest_hours_between = models.PositiveSmallIntegerField(
        default=2, verbose_name="Часы отдыха между занятиями"
    )
    notes = models.TextField(blank=True, verbose_name="Особые отметки")
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Лошадь"
        verbose_name_plural = "Лошади"

    def __str__(self):
        return self.name

    def get_workload_for_date(self, date):
        """Количество занятий на дату"""
        return self.booking_set.filter(
            start_time__date=date, status__in=["confirmed", "completed"]
        ).count()

    def get_monthly_stats(self, year, month):
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1)
        else:
            end_date = date(year, month + 1, 1)

        bookings = self.booking_set.filter(
            start_time__date__gte=start_date,
            start_time__date__lt=end_date,
            status__in=["completed", "confirmed"],
        )
        total_bookings = bookings.count()
        total_minutes = sum(b.service_type.duration for b in bookings)
        total_hours = total_minutes / 60.0

        return {
            "total_bookings": total_bookings,
            "total_hours": total_hours,
            "month": month,
            "year": year,
        }

    def is_available(self, start_time, end_time, exclude_booking_id=None):
        # Проверяем пересекающиеся бронирования
        bookings = self.booking_set.filter(
            start_time__lt=end_time,
            end_time__gt=start_time,
            status__in=["confirmed", "pending"],
        )
        if exclude_booking_id is not None:
            bookings = bookings.exclude(id=exclude_booking_id)
        if bookings.exists():
            return False

        # Проверяем отдых до и после
        rest_delta = timedelta(hours=self.rest_hours_between)
        before = self.booking_set.filter(
            end_time__gt=start_time - rest_delta,
            end_time__lte=start_time,
            status__in=["confirmed", "completed"],
        )
        if exclude_booking_id is not None:
            before = before.exclude(id=exclude_booking_id)
        after = self.booking_set.filter(
            start_time__gte=end_time,
            start_time__lt=end_time + rest_delta,
            status__in=["confirmed", "pending"],
        )
        if exclude_booking_id is not None:
            after = after.exclude(id=exclude_booking_id)
        if before.exists() or after.exists():
            return False
        return True


class ServiceType(models.Model):
    """Тип услуги (индивидуальное занятие, групповая тренировка, прогулка и т.д.)"""

    name = models.CharField(max_length=100, verbose_name="Название")
    duration = models.PositiveSmallIntegerField(
        help_text="Длительность в минутах", verbose_name="Длительность (мин)"
    )
    default_price = models.DecimalField(
        max_digits=8, decimal_places=2, verbose_name="Базовая стоимость"
    )
    description = models.TextField(blank=True)

    class Meta:
        verbose_name = "Тип услуги"
        verbose_name_plural = "Типы услуг"

    def __str__(self):
        return f"{self.name} ({self.duration} мин)"


class Booking(models.Model):
    """Запись на занятие"""

    STATUS_CHOICES = [
        ("pending", "Ожидание"),
        ("confirmed", "Подтверждено"),
        ("cancelled", "Отменено"),
        ("completed", "Завершено"),
        ("no_show", "Неявка"),
    ]

    PAYMENT_METHODS = [
        ("card", "Карта"),
        ("cash", "Наличные"),
        ("certificate", "Подарочный сертификат"),
        ("subscription", "Абонемент"),
    ]

    client = models.ForeignKey(Client, on_delete=models.CASCADE, verbose_name="Клиент")
    trainer = models.ForeignKey(
        Trainer, on_delete=models.CASCADE, verbose_name="Тренер"
    )
    horse = models.ForeignKey(Horse, on_delete=models.CASCADE, verbose_name="Лошадь")
    service_type = models.ForeignKey(
        ServiceType, on_delete=models.PROTECT, verbose_name="Услуга"
    )
    start_time = models.DateTimeField(verbose_name="Начало")
    end_time = models.DateTimeField(verbose_name="Окончание")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    notes = models.TextField(blank=True, verbose_name="Заметки")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHODS,
        default="card",
        verbose_name="Способ оплаты",
    )

    # Связь с абонементом (если занятие списывается с абонемента)
    used_subscription = models.ForeignKey(
        "ClientSubscription",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="Использованный абонемент",
    )
    price_charged = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Списанная сумма",
    )

    class Meta:
        verbose_name = "Запись"
        verbose_name_plural = "Записи"
        ordering = ["-start_time"]

    def __str__(self):
        return f"{self.client} - {self.start_time.strftime('%d.%m.%Y %H:%M')}"

    def save(self, *args, **kwargs):
        # Автоматически вычисляем end_time на основе длительности услуги
        if not self.end_time:
            self.end_time = self.start_time + timedelta(
                minutes=self.service_type.duration
            )
        super().save(*args, **kwargs)

    def clean(self):
        from django.core.exceptions import ValidationError

        # Проверяем, что все необходимые поля заполнены
        if not all(
            [
                self.horse_id,
                self.trainer_id,
                self.start_time,
                self.end_time,
                self.service_type_id,
            ]
        ):
            # Если не все поля заданы, Django сам отловит это в валидации формы
            return
        # Проверка доступности лошади
        if not self.horse.is_available(self.start_time, self.end_time, self.id):
            raise ValidationError(
                "Лошадь недоступна в выбранное время (недостаточно отдыха или уже занята)."
            )


class Subscription(models.Model):
    """Шаблон абонемента (описание)"""

    name = models.CharField(max_length=100, verbose_name="Название")
    service_type = models.ForeignKey(
        ServiceType, on_delete=models.PROTECT, verbose_name="Тип услуги"
    )
    visits = models.PositiveSmallIntegerField(verbose_name="Количество занятий")
    price = models.DecimalField(
        max_digits=8, decimal_places=2, verbose_name="Стоимость"
    )
    validity_days = models.PositiveSmallIntegerField(
        verbose_name="Срок действия (дней)"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Абонемент"
        verbose_name_plural = "Абонементы"

    def __str__(self):
        return f"{self.name} ({self.visits} занятий)"


class ClientSubscription(models.Model):
    """Приобретённый абонемент клиента"""

    client = models.ForeignKey(
        Client, on_delete=models.CASCADE, related_name="subscriptions"
    )
    subscription = models.ForeignKey(Subscription, on_delete=models.PROTECT)
    start_date = models.DateField(default=timezone.now)
    end_date = models.DateField()
    visits_total = models.PositiveSmallIntegerField()
    remaining_visits = models.PositiveSmallIntegerField()
    purchase_date = models.DateTimeField(auto_now_add=True)
    is_paid = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Абонемент клиента"
        verbose_name_plural = "Абонементы клиентов"

    def __str__(self):
        return f"{self.client}: {self.subscription.name} (осталось {self.remaining_visits})"

    def save(self, *args, **kwargs):
        if not self.visits_total:
            self.visits_total = self.subscription.visits
            self.remaining_visits = self.visits_total
        if not self.end_date:
            self.end_date = self.start_date + timedelta(
                days=self.subscription.validity_days
            )
        super().save(*args, **kwargs)

    def use_visit(self):
        if self.remaining_visits > 0:
            self.remaining_visits -= 1
            self.save(
                update_fields=["remaining_visits"]
            )  # <-- лучше указать update_fields
            return True
        return False
