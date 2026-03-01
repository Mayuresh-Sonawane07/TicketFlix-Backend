from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TheaterViewSet, ScreenViewSet, ShowViewSet, SeatViewSet

router = DefaultRouter()
router.register(r'theaters', TheaterViewSet, basename='theaters')
router.register(r'screens', ScreenViewSet, basename='screens')
router.register(r'shows', ShowViewSet, basename='shows')
router.register(r'seats', SeatViewSet, basename='seats')

urlpatterns = [
    path('', include(router.urls)),
]