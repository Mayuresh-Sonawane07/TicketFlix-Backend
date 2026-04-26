from django.urls import path
from . import views as v

urlpatterns = [
# Dashboard
path('dashboard/',                    v.AdminDashboardView.as_view(),         name='admin-dashboard'),

# Venue Owners
path('venue-owners/',                 v.AdminVenueOwnersView.as_view(),        name='admin-venue-owners'),
path('venue-owners/<int:user_id>/',   v.AdminApproveVenueOwnerView.as_view(),  name='admin-venue-owner-action'),

# Users
path('users/',                        v.AdminUsersView.as_view(),              name='admin-users'),
path('users/<int:user_id>/',          v.AdminUserActionView.as_view(),         name='admin-user-action'),

# Events
path('events/',                       v.AdminEventsView.as_view(),             name='admin-events'),
path('events/<int:event_id>/',        v.AdminEventActionView.as_view(),        name='admin-event-action'),

# Shows
path('shows/',                        v.AdminShowsView.as_view(),              name='admin-shows'),
path('shows/<int:show_id>/',          v.AdminShowActionView.as_view(),         name='admin-show-action'),

# Bookings
path('bookings/',                     v.AdminBookingsView.as_view(),           name='admin-bookings'),
path('bookings/<int:booking_id>/cancel/', v.AdminCancelBookingView.as_view(),  name='admin-cancel-booking'),

# Revenue
path('revenue/',                      v.AdminRevenueView.as_view(),            name='admin-revenue'),

# Fraud
path('fraud/',                        v.AdminFraudView.as_view(),              name='admin-fraud'),

# Notifications
path('notifications/',                v.AdminNotificationsListCreateView.as_view(), name='admin-notifications'),
path('notifications/<int:notif_id>/', v.AdminNotificationDeleteView.as_view(), name='admin-notification-delete'),

# Support Tickets
path('support/tickets/',                         v.AdminSupportTicketListView.as_view(),   name='admin-support-tickets'),
path('support/tickets/<int:ticket_id>/',         v.AdminSupportTicketDetailView.as_view(), name='admin-support-ticket-detail'),
path('support/tickets/<int:ticket_id>/reply/',   v.AdminSupportTicketReplyView.as_view(),  name='admin-support-ticket-reply'),
]