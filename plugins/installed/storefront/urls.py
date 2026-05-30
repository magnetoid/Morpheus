from django.urls import path
from django.views.generic import TemplateView

from plugins.installed.storefront import sw, views
from plugins.installed.storefront.views import vendor as vendor_views

app_name = 'storefront'
urlpatterns = [
    path(
        'affiliates/terms/',
        TemplateView.as_view(template_name='storefront/affiliate_terms.html'),
        name='affiliate_terms',
    ),
    path('sw.js', sw.service_worker_js, name='service_worker'),
    path('offline/', sw.offline_page, name='offline'),
    path('', views.home, name='home'),
    path('products/', views.product_list, name='product_list'),
    path('products/<slug:slug>/', views.product_detail, name='product_detail'),
    path('cart/', views.cart, name='cart'),
    path('cart/add/<uuid:product_id>/', views.cart_add, name='cart_add'),
    path('checkout/', views.checkout, name='checkout'),
    path('checkout/shipping/', views.checkout_shipping, name='checkout_shipping'),
    path('checkout/review/', views.checkout_review, name='checkout_review'),
    path('checkout/payment/', views.checkout_payment, name='checkout_payment'),
    path(
        'checkout/gift-card/apply/', views.checkout_apply_gift_card, name='checkout_apply_gift_card'
    ),
    path(
        'checkout/gift-card/remove/',
        views.checkout_remove_gift_card,
        name='checkout_remove_gift_card',
    ),
    path('search/', views.search, name='search'),
    path('api/quick-search/', views.quick_search, name='quick_search'),
    # Content / static
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
    path('journal/', views.journal_index, name='journal_index'),
    path('journal/<slug:slug>/', views.journal_detail, name='journal_detail'),
    path('categories/', views.categories, name='categories'),
    path('category/<slug:slug>/', views.category_detail, name='category_detail'),
    path('collection/<slug:slug>/', views.collection_detail, name='collection_detail'),
    path('author/<slug:slug>/', views.author_detail, name='author_detail'),
    path('marketplace/', vendor_views.marketplace_landing, name='marketplace_landing'),
    path('vendors/', views.vendors_directory, name='vendors'),
    path('vendor/<slug:slug>/', views.vendor_detail, name='vendor_detail'),
    path('newsletter/subscribe/', views.newsletter_subscribe, name='newsletter_subscribe'),
    # Customer account
    path('account/', views.account_home, name='account_home'),
    path('account/profile/', views.account_profile, name='account_profile'),
    path('account/orders/', views.account_orders, name='account_orders'),
    path(
        'account/orders/<str:order_number>/',
        views.account_order_detail,
        name='account_order_detail',
    ),
    path(
        'account/orders/<str:order_number>/return/',
        views.account_order_return,
        name='account_order_return',
    ),
    path('account/addresses/', views.account_addresses, name='account_addresses'),
    path('account/addresses/new/', views.account_address_form, name='account_address_new'),
    path(
        'account/addresses/<uuid:address_id>/edit/',
        views.account_address_form,
        name='account_address_edit',
    ),
    path(
        'account/addresses/<uuid:address_id>/delete/',
        views.account_address_delete,
        name='account_address_delete',
    ),
    path('account/returns/', views.account_returns, name='account_returns'),
    path(
        'account/returns/<uuid:rma_id>/', views.account_return_status, name='account_return_status'
    ),
    path('account/credits/', views.account_credits, name='account_credits'),
    path('account/downloads/', views.account_downloads, name='account_downloads'),
    # Order confirmation (post-checkout)
    path(
        'order/confirmation/<str:order_number>/',
        views.order_confirmation,
        name='order_confirmation',
    ),
    # Generic placeholder pages (footer links without first-class content yet)
    path('stockists/', views.coming_soon, {'slug': 'stockists'}, name='stockists'),
    path('staff-picks/', views.staff_picks, name='staff_picks'),
    path('shipping/', views.shipping, name='shipping'),
    path('returns/', views.returns, name='returns'),
]
