from datetime import datetime, timedelta
from django.db.models import Q
from .models import Booking, Trainer, Horse


def check_availability(trainer, horse, start_time, end_time, exclude_booking_id=None):
    # Проверка лошади
    if not horse.is_available(start_time, end_time, exclude_booking_id):
        return False, f"Лошадь {horse.name} недоступна в это время."

    # Проверка тренера: пересекающиеся бронирования
    trainer_bookings = Booking.objects.filter(
        trainer=trainer,
        start_time__lt=end_time,
        end_time__gt=start_time,
        status__in=["confirmed", "pending"],
    )
    if exclude_booking_id is not None:
        trainer_bookings = trainer_bookings.exclude(id=exclude_booking_id)
    if trainer_bookings.exists():
        return False, f"Тренер {trainer} уже занят в это время."

    # Проверка дневной нагрузки тренера
    day_start = start_time.replace(hour=0, minute=0, second=0)
    day_end = day_start + timedelta(days=1)
    day_bookings = Booking.objects.filter(
        trainer=trainer,
        start_time__gte=day_start,
        start_time__lt=day_end,
        status__in=["confirmed", "pending"],
    )
    if exclude_booking_id is not None:
        day_bookings = day_bookings.exclude(id=exclude_booking_id)
    if day_bookings.count() >= trainer.max_horses_per_day:
        return False, f"Тренер {trainer} достиг максимальной нагрузки на день."

    # Проверка дневной нагрузки лошади
    day_horse_bookings = Booking.objects.filter(
        horse=horse,
        start_time__gte=day_start,
        start_time__lt=day_end,
        status__in=["confirmed", "pending"],
    )
    if exclude_booking_id is not None:
        day_horse_bookings = day_horse_bookings.exclude(id=exclude_booking_id)
    if day_horse_bookings.count() >= horse.max_workload_per_day:
        return False, f"Лошадь {horse.name} достигла максимальной нагрузки на день."

    return True, "OK"


def suggest_available_slots(date, service_duration_minutes, trainer=None, horse=None):
    """
    Возвращает список доступных временных слотов на заданную дату с учётом
    работы клуба (например, с 9:00 до 21:00) и доступности.
    """
    slots = []
    work_start = datetime.combine(date, datetime.strptime("09:00", "%H:%M").time())
    work_end = datetime.combine(date, datetime.strptime("21:00", "%H:%M").time())
    slot_duration = timedelta(minutes=30)  # шаг сетки 30 мин
    service_duration = timedelta(minutes=service_duration_minutes)

    current = work_start
    while current + service_duration <= work_end:
        end_time = current + service_duration
        if trainer and horse:
            avail, _ = check_availability(trainer, horse, current, end_time)
        elif trainer:
            # проверка только тренера
            avail = not Booking.objects.filter(
                trainer=trainer,
                start_time__lt=end_time,
                end_time__gt=current,
                status__in=["confirmed", "pending"],
            ).exists()
        elif horse:
            avail = horse.is_available(current, end_time)
        else:
            avail = True  # без фильтра

        if avail:
            slots.append(current.time())
        current += slot_duration
    return slots
