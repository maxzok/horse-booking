from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from django.db.models import Q, Count, Sum
from datetime import datetime, timedelta
from .models import *
from .forms import BookingForm
from .utils import suggest_available_slots


@login_required
def dashboard(request):
    """Главная панель с обзором на сегодня"""
    today = timezone.now().date()
    todays_bookings = (
        Booking.objects.filter(start_time__date=today)
        .select_related("client", "trainer", "horse")
        .order_by("start_time")
    )

    context = {
        "todays_bookings": todays_bookings,
        "pending_count": Booking.objects.filter(status="pending").count(),
        "active_clients": Client.objects.filter(is_active=True).count(),
        "trainers": Trainer.objects.filter(is_active=True),  # <-- добавлено
        "horses": Horse.objects.filter(is_active=True),  # <-- добавлено
    }
    return render(request, "booking/dashboard.html", context)


@login_required
def calendar_view(request):
    """Календарь записей (можно использовать FullCalendar)"""
    return render(request, "booking/calendar.html")


@login_required
def bookings_json(request):
    """API для FullCalendar – возвращает JSON с событиями"""
    start = request.GET.get("start")
    end = request.GET.get("end")
    bookings = Booking.objects.filter(
        start_time__gte=start,
        end_time__lte=end,
        status__in=["confirmed", "pending", "completed"],
    ).select_related("client", "trainer", "horse", "service_type")

    events = []
    for b in bookings:
        events.append(
            {
                "id": b.id,
                "title": f"{b.client} - {b.horse.name} ({b.trainer})",
                "start": b.start_time.isoformat(),
                "end": b.end_time.isoformat(),
                "backgroundColor": "#3788d8" if b.status == "confirmed" else "#ffc107",
                "extendedProps": {"status": b.status, "service": b.service_type.name},
            }
        )
    return JsonResponse(events, safe=False)


@login_required
def booking_create(request):
    """Создание новой записи"""
    if request.method == "POST":
        form = BookingForm(request.POST)
        if form.is_valid():
            booking = form.save(commit=False)
            # Привязываем абонемент, если есть
            active_sub = booking.client.active_subscription()
            if active_sub and active_sub.remaining_visits > 0:
                booking.used_subscription = active_sub
                # Списание произойдёт при подтверждении или завершении
            booking.save()
            messages.success(request, "Запись создана.")
            return redirect("booking:calendar")
    else:
        form = BookingForm()
    return render(request, "booking/booking_form.html", {"form": form})


@login_required
def booking_edit(request, pk):
    booking = get_object_or_404(Booking, pk=pk)
    if request.method == "POST":
        form = BookingForm(request.POST, instance=booking)
        if form.is_valid():
            form.save()
            return redirect("booking:calendar")
    else:
        form = BookingForm(instance=booking)
    return render(request, "booking/booking_form.html", {"form": form})


@login_required
def get_available_slots(request):
    """AJAX-эндпоинт для динамической подгрузки свободных слотов"""
    date_str = request.GET.get("date")
    trainer_id = request.GET.get("trainer")
    horse_id = request.GET.get("horse")
    service_id = request.GET.get("service")
    if not all([date_str, trainer_id, horse_id, service_id]):
        return JsonResponse({"error": "Missing parameters"}, status=400)

    date = datetime.strptime(date_str, "%Y-%m-%d").date()
    service = ServiceType.objects.get(pk=service_id)
    trainer = Trainer.objects.get(pk=trainer_id) if trainer_id else None
    horse = Horse.objects.get(pk=horse_id) if horse_id else None

    slots = suggest_available_slots(date, service.duration, trainer, horse)
    return JsonResponse({"slots": [s.strftime("%H:%M") for s in slots]})


@login_required
def client_detail(request, pk):
    client = get_object_or_404(Client, pk=pk)
    bookings = client.booking_set.all().order_by("-start_time")[:20]
    subscriptions = client.subscriptions.all().order_by("-purchase_date")
    context = {
        "client": client,
        "bookings": bookings,
        "subscriptions": subscriptions,
        "active_subscription": client.active_subscription(),
    }
    return render(request, "booking/client_detail.html", context)


@login_required
def complete_booking(request, pk):
    booking = get_object_or_404(Booking, pk=pk)
    if booking.status != "completed":
        booking.status = "completed"

        # Если способ оплаты - абонемент, списываем занятие
        if booking.payment_method == "subscription" and booking.used_subscription:
            success = booking.used_subscription.use_visit()
            if not success:
                messages.error(request, "Ошибка списания с абонемента.")
        elif booking.payment_method == "subscription" and not booking.used_subscription:
            # Попробуем автоматически подвязать активный абонемент клиента
            active_sub = booking.client.active_subscription()
            if active_sub and active_sub.remaining_visits > 0:
                booking.used_subscription = active_sub
                success = active_sub.use_visit()
                if not success:
                    messages.error(request, "Ошибка списания с абонемента.")
            else:
                messages.warning(
                    request, "У клиента нет активного абонемента, занятие не списано."
                )

        booking.save()
        messages.success(request, "Занятие завершено.")
    return redirect("booking:calendar")


@login_required
def trainer_stats(request, pk):
    trainer = get_object_or_404(Trainer, pk=pk)
    today = timezone.now().date()
    year = int(request.GET.get("year", today.year))
    month = int(request.GET.get("month", today.month))

    stats = trainer.get_monthly_stats(year, month)

    # Для выбора месяца/года в шаблоне
    months = [(i, datetime(year, i, 1).strftime("%B")) for i in range(1, 13)]
    years = range(today.year - 2, today.year + 1)

    context = {
        "trainer": trainer,
        "stats": stats,
        "months": months,
        "years": years,
        "selected_year": year,
        "selected_month": month,
    }
    return render(request, "booking/trainer_stats.html", context)


@login_required
def horse_stats(request, pk):
    horse = get_object_or_404(Horse, pk=pk)
    today = timezone.now().date()
    year = int(request.GET.get("year", today.year))
    month = int(request.GET.get("month", today.month))

    stats = horse.get_monthly_stats(year, month)
    months = [(i, datetime(year, i, 1).strftime("%B")) for i in range(1, 13)]
    years = range(today.year - 2, today.year + 1)

    context = {
        "horse": horse,
        "stats": stats,
        "months": months,
        "years": years,
        "selected_year": year,
        "selected_month": month,
    }
    return render(request, "booking/horse_stats.html", context)


@login_required
def client_list(request):
    """Список клиентов с поиском"""
    query = request.GET.get("q", "")
    if query:
        clients = Client.objects.filter(
            models.Q(first_name__icontains=query)
            | models.Q(last_name__icontains=query)
            | models.Q(phone__icontains=query)
        ).order_by("last_name", "first_name")
    else:
        clients = Client.objects.all().order_by("last_name", "first_name")

    context = {
        "clients": clients,
        "query": query,
    }
    return render(request, "booking/client_list.html", context)


@login_required
def active_subscriptions(request):
    """Список активных абонементов с фильтрацией по клиенту"""
    query = request.GET.get("q", "")
    subscriptions = (
        ClientSubscription.objects.filter(
            remaining_visits__gt=0, end_date__gte=timezone.now().date()
        )
        .select_related("client", "subscription")
        .order_by("client__last_name", "client__first_name")
    )

    if query:
        subscriptions = subscriptions.filter(
            Q(client__first_name__icontains=query)
            | Q(client__last_name__icontains=query)
            | Q(client__phone__icontains=query)
        )

    context = {
        "subscriptions": subscriptions,
        "query": query,
        "total_active": subscriptions.count(),
    }
    return render(request, "booking/active_subscriptions.html", context)


@login_required
def subscription_detail(request, pk):
    """Детали абонемента со списком списаний"""
    subscription = get_object_or_404(
        ClientSubscription.objects.select_related(
            "client", "subscription__service_type"
        ),
        pk=pk,
    )

    # Находим все завершённые занятия, где использовался этот абонемент
    used_bookings = (
        subscription.booking_set.filter(status="completed")
        .select_related("service_type", "horse", "trainer")
        .order_by("-start_time")
    )

    context = {
        "subscription": subscription,
        "used_bookings": used_bookings,
        "total_spent": used_bookings.count(),
        "remaining": subscription.remaining_visits,
    }
    return render(request, "booking/subscription_detail.html", context)
