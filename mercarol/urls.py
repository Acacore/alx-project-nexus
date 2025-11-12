from django.urls import path, include
from rest_framework.routers import DefaultRouters
from .views import *

router = DefaultRouters()

rout
urlpatterns = [
    path("home", home, name ='name' ),
    path('api', include(router.urls))
]
