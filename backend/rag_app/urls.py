# rag_app/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ThreadViewSet, register, login, logout, current_user

router = DefaultRouter()
router.register(r'threads', ThreadViewSet, basename='thread')

urlpatterns = [
    # Authentication
    path('auth/register/', register, name='register'),
    path('auth/login/', login, name='login'),
    path('auth/logout/', logout, name='logout'),
    path('auth/user/', current_user, name='current_user'),
    
    # Threads and Messages
    path('', include(router.urls)),
]