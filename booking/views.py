from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
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
    """Отметить занятие как завершённое и списать посещение с абонемента"""
    booking = get_object_or_404(Booking, pk=pk)
    if booking.status != "completed":
        booking.status = "completed"
        if booking.used_subscription:
            success = booking.used_subscription.use_visit()
            if not success:
                messages.error(request, "Ошибка списания с абонемента.")
        booking.save()
        messages.success(request, "Занятие завершено.")
    return redirect("booking:calendar")


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
