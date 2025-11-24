from django.urls import path
from .views import ChatView, health, get_users_list

app_name = 'chatbot'

urlpatterns = [
    path('chat/', ChatView.as_view(), name='chat'),
    path('health/', health, name='health'),
    path('users/', get_users_list, name='users'),
]

