from django.urls import path, re_path
from django.views.generic import RedirectView

from plugins.installed.booking_marketplace import account, host, stay_views, views

app_name = 'booking_marketplace'

urlpatterns = [
    # English is unprefixed (i18n_patterns prefix_default_language=False), so any
    # /en/* URL indexed from a past hreflang bug 404s. 301 them to the bare path
    # to recover the international indexing (SEO audit P0, July 2026).
    re_path(
        r'^en/(?P<rest>.*)$',
        RedirectView.as_view(url='/%(rest)s', permanent=True, query_string=True),
        name='en_prefix_redirect',
    ),
    path('bookings/', views.services_list, name='list'),
    path('shop/', views.products_list, name='shop'),
    # Signed-in customer's own bookings (experiences + stays). Booked under the
    # site root so the montenegro theme's account nav can link to it via
    # `{% url 'booking_marketplace:account_bookings' %}`; only exists while this
    # plugin is enabled.
    path('account/bookings/', account.account_bookings, name='account_bookings'),
    path('regions/', views.regions_index, name='regions'),
    path('regions/<slug:region>/', views.region_detail, name='region'),
    path('places/', views.places_index, name='places'),
    path('places/<slug:slug>/', views.place_detail, name='place'),
    path('events/', views.events_index, name='events'),
    path('events/<slug:slug>/', views.event_detail, name='event'),
    # Accommodation (stays) — specific routes before the <slug> detail.
    path('hotels/', stay_views.stays_index, name='stays'),
    path('hotels/<slug:slug>/quote/', stay_views.stay_quote, name='stay_quote'),
    path('hotels/<slug:slug>/book/', stay_views.stay_book, name='stay_book'),
    path('hotels/<slug:slug>/', stay_views.stay_detail, name='stay_detail'),
    # Host self-serve — must precede the <slug> detail route below.
    path('bookings/host/', host.host_services, name='host_services'),
    path('bookings/host/new/', host.host_service_form, name='host_new'),
    path('bookings/host/bookings/', host.host_bookings, name='host_bookings'),
    path('bookings/host/enquiries/', host.host_enquiries, name='host_enquiries'),
    path('bookings/host/earnings/', host.host_earnings, name='host_earnings'),
    path('bookings/host/<slug:slug>/edit/', host.host_service_form, name='host_edit'),
    path('bookings/<slug:slug>/review/', views.post_review, name='review'),
    path('bookings/<slug:slug>/', views.service_detail, name='detail'),
]
