from django.urls import path

from plugins.installed.post_purchase import views

app_name = 'post_purchase'

urlpatterns = [
    # `thanks` MUST precede `<str:token>` — `str` matches it too, and Django
    # takes the first match. Registered the other way round, the post-survey
    # redirect to `nps_thanks` resolved back into `nps_form(token='thanks')`,
    # which fails signature verification and renders "link expired" (HTTP 410).
    # Every customer who submitted a score saw that instead of a thank-you.
    path('nps/thanks/', views.nps_thanks, name='nps_thanks'),
    path('nps/<str:token>/', views.nps_form, name='nps_form'),
]
