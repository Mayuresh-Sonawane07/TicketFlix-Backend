"""
admin_views.py  —  mount at /api/admin-panel/
All endpoints require role == 'Admin'.
"""
from django.utils import timezone
from django.db.models import Sum, Count, Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from rest_framework.throttling import UserRateThrottle

class AdminThrottle(UserRateThrottle):
    scope = 'admin'

# ── Permission helper ─────────────────────────────────────────────────────────

class IsAdmin(IsAuthenticated):
    def has_permission(self, request, view):
        return (
            super().has_permission(request, view)
            and request.user.role == 'Admin'
            and request.user.is_active
            and not request.user.is_banned
        )


# ── Dashboard stats ───────────────────────────────────────────────────────────

class AdminDashboardView(APIView):
    permission_classes = [IsAdmin]
    throttle_classes = [AdminThrottle]

    def get(self, request):
        from django.contrib.auth import get_user_model
        from events.models import Event
        from theaters.models import Show
        from bookings.models import Booking

        User = get_user_model()

        # User stats
        total_users        = User.objects.count()
        total_customers    = User.objects.filter(role='Customer').count()
        total_venue_owners = User.objects.filter(role='VENUE_OWNER').count()
        pending_approvals  = User.objects.filter(role='VENUE_OWNER', is_approved=False, is_banned=False).count()
        banned_users       = User.objects.filter(is_banned=True).count()

        # Event stats
        total_events    = Event.objects.count()
        pending_events  = Event.objects.filter(status='pending').count()
        approved_events = Event.objects.filter(status='approved').count()
        flagged_events  = Event.objects.filter(status='flagged').count()

        # Booking / Revenue stats
        total_bookings    = Booking.objects.filter(status='Booked').count()
        cancelled_bookings = Booking.objects.filter(status='Cancelled').count()
        total_revenue     = Booking.objects.filter(status='Booked').aggregate(
            total=Sum('total_amount'))['total'] or 0

        # Recent bookings (last 7 days)
        week_ago = timezone.now() - timezone.timedelta(days=7)
        recent_revenue = Booking.objects.filter(
            status='Booked', booking_time__gte=week_ago
        ).aggregate(total=Sum('total_amount'))['total'] or 0

        # Suspicious activity: users with 5+ bookings in last 24h
        day_ago = timezone.now() - timezone.timedelta(hours=24)
        suspicious_users = (
            Booking.objects
            .filter(booking_time__gte=day_ago)
            .values('user')
            .annotate(count=Count('id'))
            .filter(count__gte=5)
            .count()
        )

        return Response({
            'users': {
                'total': total_users,
                'customers': total_customers,
                'venue_owners': total_venue_owners,
                'pending_approvals': pending_approvals,
                'banned': banned_users,
            },
            'events': {
                'total': total_events,
                'pending': pending_events,
                'approved': approved_events,
                'flagged': flagged_events,
            },
            'bookings': {
                'total': total_bookings,
                'cancelled': cancelled_bookings,
            },
            'revenue': {
                'total': float(total_revenue),
                'last_7_days': float(recent_revenue),
            },
            'fraud': {
                'suspicious_users': suspicious_users,
            },
        })


# ── Venue Owner Approval ──────────────────────────────────────────────────────

class AdminVenueOwnersView(APIView):
    permission_classes = [IsAdmin]
    throttle_classes = [AdminThrottle]

    def get(self, request):
        from django.contrib.auth import get_user_model
        User = get_user_model()

        filter_by = request.query_params.get('filter', 'pending')  # pending | approved | banned | all
        qs = User.objects.filter(role='VENUE_OWNER')

        if filter_by == 'pending':
            qs = qs.filter(is_approved=False, is_banned=False)
        elif filter_by == 'approved':
            qs = qs.filter(is_approved=True, is_banned=False)
        elif filter_by == 'banned':
            qs = qs.filter(is_banned=True)

        data = [{
            'id':          u.id,
            'name':        u.first_name or u.email,
            'email':       u.email,
            'phone':       u.phone_number,
            'is_approved': u.is_approved,
            'is_banned':   u.is_banned,
            'is_suspended':u.is_suspended,
            'ban_reason':  u.ban_reason,
            'joined_at':   u.joined_at,
        } for u in qs.order_by('-joined_at')]

        return Response(data)


class AdminApproveVenueOwnerView(APIView):
    permission_classes = [IsAdmin]
    throttle_classes = [AdminThrottle]

    def post(self, request, user_id):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            user = User.objects.get(id=user_id, role='VENUE_OWNER')
            if user.role == 'Admin':
                return Response({'error': 'Cannot modify admin users'}, status=403)
        except User.DoesNotExist:
            return Response({'error': 'Venue owner not found.'}, status=404)

        action = request.data.get('action')  # approve | reject | ban | unban | suspend
        ALLOWED_ACTIONS = ['approve', 'reject', 'ban', 'unban', 'suspend']

        if action not in ALLOWED_ACTIONS:
            return Response({'error': 'Invalid action'}, status=400)

        if action == 'approve':
            user.is_approved = True
            user.is_banned   = False
            user.save()
            from users.models import AdminLog
            AdminLog.objects.create(
                admin=request.user,
                action='APPROVE_VENUE_OWNER',
                target=user.email
            )
            return Response({'message': f'{user.email} approved.'})

        elif action == 'reject':
            user.is_approved = False
            user.save()
            return Response({'message': f'{user.email} rejected.'})

        elif action == 'ban':
            user.is_banned  = True
            user.ban_reason = request.data.get('reason', '')
            user.save()
            return Response({'message': f'{user.email} banned.'})

        elif action == 'unban':
            user.is_banned  = False
            user.ban_reason = ''
            user.save()
            return Response({'message': f'{user.email} unbanned.'})

        elif action == 'suspend':
            user.is_suspended    = True
            user.suspended_until = request.data.get('until')
            user.save()
            return Response({'message': f'{user.email} suspended.'})

        return Response({'error': 'Invalid action.'}, status=400)


# ── All Users Management ──────────────────────────────────────────────────────

class AdminUsersView(APIView):
    permission_classes = [IsAdmin]
    throttle_classes = [AdminThrottle]

    def get(self, request):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        role = request.query_params.get('role')
        qs = User.objects.filter(role='Customer')
        if role:
            qs = qs.filter(role=role)
        
        paginator = PageNumberPagination()
        result_page = paginator.paginate_queryset(qs.order_by('-joined_at'), request)
        data = [{
            'id':          u.id,
            'name':        u.first_name or u.email,
            'email':       u.email,
            'role':        u.role,
            'phone':       u.phone_number,
            'is_approved': u.is_approved,
            'is_banned':   u.is_banned,
            'is_suspended':u.is_suspended,
            'ban_reason':  u.ban_reason,
            'joined_at':   u.joined_at,
        } for u in result_page]
        return paginator.get_paginated_response(data)


class AdminUserActionView(APIView):
    permission_classes = [IsAdmin]
    throttle_classes = [AdminThrottle]

    def post(self, request, user_id):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            user = User.objects.get(id=user_id)
            if user.role == 'Admin':
                return Response({'error': 'Cannot modify admin users'}, status=403)
        except User.DoesNotExist:
            return Response({'error': 'User not found.'}, status=404)

        action = request.data.get('action')  # ban | unban | suspend | delete
        ALLOWED_ACTIONS = ['ban', 'unban', 'suspend', 'delete']

        if action not in ALLOWED_ACTIONS:
            return Response({'error': 'Invalid action'}, status=400)

        if action == 'ban':
            user.is_banned  = True
            user.ban_reason = request.data.get('reason', '')
            user.save()
            from users.models import AdminLog
            AdminLog.objects.create(
                admin=request.user,
                action='BAN_USER',
                target=user.email
            )
            return Response({'message': f'{user.email} banned.'})

        elif action == 'unban':
            user.is_banned  = False
            user.ban_reason = ''
            user.save()
            from users.models import AdminLog
            AdminLog.objects.create(
                admin=request.user,
                action='UNBAN_USER',
                target=user.email
            )
            return Response({'message': f'{user.email} unbanned.'})

        elif action == 'suspend':
            user.is_suspended = True
            user.suspended_until = request.data.get('until')
            user.save()
            return Response({'message': f'{user.email} suspended.'})

        elif action == 'delete':
            user.is_deleted = True
            user.save()
            from users.models import AdminLog
            AdminLog.objects.create(
                admin=request.user,
                action='DELETE_USER',
                target=user.email
            )
            return Response({'message': f'{user.email} soft deleted.'})

        return Response({'error': 'Invalid action.'}, status=400)


# ── Events Moderation ─────────────────────────────────────────────────────────

class AdminEventsView(APIView):
    permission_classes = [IsAdmin]
    throttle_classes = [AdminThrottle]

    def get(self, request):
        from events.models import Event
        status_filter = request.query_params.get('status')
        qs = Event.objects.select_related('created_by').all()
        if status_filter:
            qs = qs.filter(status=status_filter)

        data = [{
            'id':         e.id,
            'title':      e.title,
            'event_type': e.event_type,
            'status':     e.status,
            'created_by': e.created_by.email,
            'created_at': e.created_at,
            'admin_note': e.admin_note,
        } for e in qs.order_by('-created_at')]
        return Response(data)


class AdminEventActionView(APIView):
    permission_classes = [IsAdmin]
    throttle_classes = [AdminThrottle]

    def post(self, request, event_id):
        from events.models import Event
        try:
            event = Event.objects.get(id=event_id)
        except Event.DoesNotExist:
            return Response({'error': 'Event not found.'}, status=404)

        action = request.data.get('action')  # approve | flag | remove | restore
        ALLOWED_ACTIONS = ['approve', 'flag', 'remove', 'restore', 'unflag', 'delete']

        if action not in ALLOWED_ACTIONS:
            return Response({'error': 'Invalid action'}, status=400)

        if action == 'approve':
            event.status      = 'approved'
            event.admin_note  = ''
            event.reviewed_by = request.user
            event.reviewed_at = timezone.now()
            event.save()
            return Response({'message': f'Event "{event.title}" approved.'})

        elif action == 'flag':
            event.status      = 'flagged'
            event.admin_note  = request.data.get('note', '')
            event.reviewed_by = request.user
            event.reviewed_at = timezone.now()
            event.save()
            return Response({'message': f'Event "{event.title}" flagged.'})

        elif action == 'remove':
            event.status      = 'removed'
            event.admin_note  = request.data.get('note', '')
            event.reviewed_by = request.user
            event.reviewed_at = timezone.now()
            event.save()
            return Response({'message': f'Event "{event.title}" removed.'})

        elif action == 'restore':
            event.status     = 'pending'
            event.admin_note = ''
            event.save()
            return Response({'message': f'Event "{event.title}" restored to pending.'})
        
        elif action == 'unflag':
            event.status     = 'approved'   # unflagging → goes back to approved
            event.admin_note = ''
            event.reviewed_by = request.user
            event.reviewed_at = timezone.now()
            event.save()
            return Response({'message': f'Event "{event.title}" unflagged and approved.'})

        elif action == 'delete':
            title = event.title
            event.delete()
            return Response({'message': f'Event "{title}" permanently deleted.'})

        return Response({'error': 'Invalid action.'}, status=400)


# ── Shows Management ──────────────────────────────────────────────────────────

class AdminShowsView(APIView):
    permission_classes = [IsAdmin]
    throttle_classes = [AdminThrottle]

    def get(self, request):
        from theaters.models import Show
        qs = Show.objects.select_related('event', 'screen__theater').all().order_by('show_time')
        data = [{
            'id':           s.id,
            'event_title':  s.event.title,
            'theater':      s.screen.theater.name,
            'screen':       s.screen.screen_number,
            'show_time':    s.show_time,
            'price':        float(s.price),
            'is_cancelled': getattr(s, 'is_cancelled', False),
        } for s in qs]
        return Response(data)


class AdminShowActionView(APIView):
    permission_classes = [IsAdmin]
    throttle_classes = [AdminThrottle]

    def post(self, request, show_id):
        from theaters.models import Show
        try:
            show = Show.objects.get(id=show_id)
        except Show.DoesNotExist:
            return Response({'error': 'Show not found.'}, status=404)

        action = request.data.get('action')  # cancel | reschedule | delete
        ALLOWED_ACTIONS = ['cancel', 'reschedule', 'delete']

        if action not in ALLOWED_ACTIONS:
            return Response({'error': 'Invalid action'}, status=400)

        if action == 'cancel':
            show.is_cancelled = True
            show.save()
            return Response({'message': 'Show cancelled.'})

        elif action == 'reschedule':
            new_time = request.data.get('show_time')
            if not new_time:
                return Response({'error': 'show_time required.'}, status=400)
            show.show_time = new_time
            show.save()
            return Response({'message': f'Show rescheduled to {new_time}.'})

        elif action == 'delete':
            show.delete()
            return Response({'message': 'Show deleted.'})

        return Response({'error': 'Invalid action.'}, status=400)


# ── Bookings ──────────────────────────────────────────────────────────────────

class AdminBookingsView(APIView):
    permission_classes = [IsAdmin]
    throttle_classes = [AdminThrottle]

    def get(self, request):
        from bookings.models import Booking
        qs = Booking.objects.select_related('user', 'show__event', 'show__screen__theater').all()

        status_filter = request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)

        data = [{
            'id':             b.id,
            'user':           b.user.email,
            'event':          b.show.event.title,
            'theater':        b.show.screen.theater.name,
            'show_time':      b.show.show_time,
            'seats':          b.seats.count(),
            'total_amount':   float(b.total_amount),
            'status':         b.status,
            'transaction_id': b.transaction_id,
            'booking_time':   b.booking_time,
        } for b in qs.order_by('-booking_time')]
        return Response(data)


class AdminCancelBookingView(APIView):
    permission_classes = [IsAdmin]
    throttle_classes = [AdminThrottle]

    def post(self, request, booking_id):
        from bookings.models import Booking
        try:
            booking = Booking.objects.get(id=booking_id)
        except Booking.DoesNotExist:
            return Response({'error': 'Booking not found.'}, status=404)

        booking.status = 'Cancelled'
        booking.save()
        return Response({'message': f'Booking #{booking_id} cancelled.'})


# ── Revenue ───────────────────────────────────────────────────────────────────

class AdminRevenueView(APIView):
    permission_classes = [IsAdmin]
    throttle_classes = [AdminThrottle]
    def get(self, request):
        from bookings.models import Booking

        # Total revenue by event
        by_event = (
            Booking.objects
            .filter(status='Booked')
            .values('show__event__title')
            .annotate(revenue=Sum('total_amount'), bookings=Count('id'))
            .order_by('-revenue')[:20]
        )

        # Daily revenue last 30 days
        thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
        from django.db.models.functions import TruncDate
        daily = (
            Booking.objects
            .filter(status='Booked', booking_time__gte=thirty_days_ago)
            .annotate(day=TruncDate('booking_time'))
            .values('day')
            .annotate(revenue=Sum('total_amount'), bookings=Count('id'))
            .order_by('day')
        )

        # Failed / cancelled
        failed = Booking.objects.filter(status='Cancelled').count()
        total  = Booking.objects.filter(status='Booked').aggregate(t=Sum('total_amount'))['t'] or 0

        return Response({
            'total_revenue': float(total),
            'by_event':      list(by_event),
            'daily':         list(daily),
            'cancelled_count': failed,
        })


# ── Fraud Monitoring ──────────────────────────────────────────────────────────

class AdminFraudView(APIView):
    permission_classes = [IsAdmin]
    throttle_classes = [AdminThrottle]

    def get(self, request):
        from bookings.models import Booking

        day_ago  = timezone.now() - timezone.timedelta(hours=24)
        hour_ago = timezone.now() - timezone.timedelta(hours=1)

        # Users with 5+ bookings in last 24h
        suspicious_24h = (
            Booking.objects
            .filter(booking_time__gte=day_ago)
            .values('user__email', 'user__id')
            .annotate(count=Count('id'))
            .filter(count__gte=5)
            .order_by('-count')
        )

        # Users with 3+ bookings in last 1h (rapid booking)
        rapid = (
            Booking.objects
            .filter(booking_time__gte=hour_ago)
            .values('user__email', 'user__id')
            .annotate(count=Count('id'))
            .filter(count__gte=3)
            .order_by('-count')
        )

        # Cancelled bookings ratio per user
        high_cancel = (
            Booking.objects
            .values('user__email', 'user__id')
            .annotate(
                total=Count('id'),
                cancelled=Count('id', filter=Q(status='Cancelled'))
            )
            .filter(total__gte=3, cancelled__gte=2)
            .order_by('-cancelled')
        )

        return Response({
            'suspicious_24h': list(suspicious_24h),
            'rapid_bookings':  list(rapid),
            'high_cancel_rate': list(high_cancel),
        })


# ── Notifications ─────────────────────────────────────────────────────────────

class AdminNotificationsListCreateView(APIView):
    permission_classes = [IsAdmin]
    throttle_classes = [AdminThrottle]

    def get(self, request):
        from users.models import Notification
        notifs = Notification.objects.all()[:50]
        data = [{
            'id':         n.id,
            'title':      n.title,
            'message':    n.message,
            'type':       n.notif_type,
            'target':     n.target,
            'created_at': n.created_at,
            'is_active':  n.is_active,
        } for n in notifs]
        return Response(data)

    def post(self, request):
        from users.models import Notification
        n = Notification.objects.create(
            title      = request.data.get('title', ''),
            message    = request.data.get('message', ''),
            notif_type = request.data.get('type', 'announcement'),
            target     = request.data.get('target', 'all'),
            created_by = request.user,
        )
        return Response({'message': 'Notification sent.', 'id': n.id}, status=201)

class AdminNotificationDeleteView(APIView):
    permission_classes = [IsAdmin]
    throttle_classes = [AdminThrottle]

    def delete(self, request, notif_id=None):
        from users.models import Notification
        if notif_id:
            try:
                Notification.objects.get(id=notif_id).delete()
                return Response({'message': 'Deleted.'})
            except Notification.DoesNotExist:
                return Response({'error': 'Not found.'}, status=404)
        return Response({'error': 'notif_id required.'}, status=400)