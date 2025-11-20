from django.urls import path
from . import views

app_name = 'chatbot'

urlpatterns = [
    path('chat/', views.ChatView.as_view(), name='chat'),  # Usar APIView
    path('health/', views.health, name='health'),
]

