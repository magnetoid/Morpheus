from django.urls import path
from plugins.installed.storefront import views

app_name = 'storefront'
urlpatterns = [
    path('', views.home, name='home'),
    path('products/', views.product_list, name='product_list'),
    path('products/<slug:slug>/', views.product_detail, name='product_detail'),
    path('cart/', views.cart, name='cart'),
    path('checkout/', views.checkout, name='checkout'),
    path('checkout/shipping/', views.checkout_shipping, name='checkout_shipping'),
    path('checkout/review/', views.checkout_review, name='checkout_review'),
    path('search/', views.search, name='search'),

    # Content / static
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
    path('journal/', views.journal_index, name='journal_index'),
    path('journal/<slug:slug>/', views.journal_detail, name='journal_detail'),
    path('categories/', views.categories, name='categories'),

    # Customer account
    path('account/', views.account_home, name='account_home'),
    path('account/profile/', views.account_profile, name='account_profile'),
    path('account/orders/', views.account_orders, name='account_orders'),
    path('account/orders/<str:order_number>/', views.account_order_detail, name='account_order_detail'),
    path('account/orders/<str:order_number>/return/', views.account_order_return, name='account_order_return'),
    path('account/addresses/', views.account_addresses, name='account_addresses'),
    path('account/addresses/new/', views.account_address_form, name='account_address_new'),
    path('account/addresses/<uuid:address_id>/edit/', views.account_address_form, name='account_address_edit'),
    path('account/addresses/<uuid:address_id>/delete/', views.account_address_delete, name='account_address_delete'),
    path('account/returns/', views.account_returns, name='account_returns'),

    # Order confirmation (post-checkout)
    path('order/confirmation/<str:order_number>/', views.order_confirmation, name='order_confirmation'),

    # Generic placeholder pages (footer links without first-class content yet)
    path('stockists/', views.coming_soon, {'slug': 'stockists'}, name='stockists'),
    path('staff-picks/', views.coming_soon, {'slug': 'staff-picks'}, name='staff_picks'),
    path('shipping/', views.coming_soon, {'slug': 'shipping'}, name='shipping'),
    path('returns/', views.coming_soon, {'slug': 'returns'}, name='returns'),
]
