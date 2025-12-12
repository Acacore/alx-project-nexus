
from django.contrib import admin
from django.urls import path, re_path, include
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView
)
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from mercarol.views import TokenRefreshViewSafe, TokenVerifyViewSafe


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("mercarol.urls")),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshViewSafe.as_view(), name='token_refresh'),
    path('api/token/verify/', TokenVerifyViewSafe.as_view(), name='token_verify'),

    # djoser
    # re_path(r'^auth/', include('djoser.urls')),
    path('auth/', include('djoser.urls.authtoken')),

    path('auth/', include('djoser.urls')),
    path('auth/', include('djoser.urls.jwt')), # If using JWT

    # DRF spectacular
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    # Optional UI:
    path('api/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc')    
]
