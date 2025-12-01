from django.urls import path
from .views import (
    ChatView, health, get_users_list, 
    document_manager, upload_document, delete_document, update_document_role,
    process_manager, create_process, delete_process, edit_process,
    upload_documentation
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

    # --- NUEVAS RUTAS: GESTIÓN DE PROCESOS ---
    path('procesos/', process_manager, name='process_manager'),
    path('procesos/crear/', create_process, name='create_process'),
    path('procesos/eliminar/<int:process_id>/', delete_process, name='delete_process'),
    path('procesos/editar/<int:process_id>/', edit_process, name='edit_process'),
    
    # --- NUEVA RUTA: SUBIDA DE DOCUMENTACIÓN DESDE EL CHAT ---
    path('documentacion/subir/', upload_documentation, name='upload_documentation'),
]


