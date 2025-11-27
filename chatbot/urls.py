from django.urls import path
from .views import (
    ChatView, health, get_users_list, 
    document_manager, upload_document, delete_document, update_document_role
)

app_name = 'chatbot'

urlpatterns = [
    path('chat/', ChatView.as_view(), name='chat'),
    path('health/', health, name='health'),
    path('users/', get_users_list, name='users'),
    
    # Gestión Documental
    path('gestion/', document_manager, name='document_manager'),
    path('gestion/upload/', upload_document, name='upload_document'),
    path('gestion/delete/<str:doc_id>/', delete_document, name='delete_document'),
    path('gestion/update-role/<str:doc_id>/', update_document_role, name='update_document_role'),
]


