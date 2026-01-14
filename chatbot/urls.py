from django.urls import path
from .views import (
    ChatView, health, get_users_list, 
    document_manager, upload_document, delete_document, update_document_role, 
    bulk_delete_documents, bulk_update_roles,
    process_manager, create_process, delete_process, edit_process,
    create_chatbot_role, delete_chatbot_role, edit_chatbot_role,
    get_users_list, create_process_type, edit_process_type, delete_process_type,
    api_get_servicios_estudiante, api_get_proceso_servicios, api_get_servicios_de_proceso,
    api_get_procesos_por_audiencia, api_get_requisitos_de_servicio
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
    path('gestion/bulk-delete/', bulk_delete_documents, name='bulk_delete_documents'),
    path('gestion/bulk-update-roles/', bulk_update_roles, name='bulk_update_roles'),

    # --- NUEVAS RUTAS: GESTIÓN DE PROCESOS ---
    path('procesos/', process_manager, name='process_manager'),
    path('procesos/crear/', create_process, name='create_process'),
    path('procesos/eliminar/<int:process_id>/', delete_process, name='delete_process'),
    path('procesos/editar/<int:process_id>/', edit_process, name='edit_process'),
    
    # Ruta de upload_documentation eliminada - ya no se usa
    path('gestion/roles/create/', create_chatbot_role, name='create_chatbot_role'),
    path('gestion/roles/edit/<int:role_id>/', edit_chatbot_role, name='edit_chatbot_role'),
    path('gestion/roles/delete/<int:role_id>/', delete_chatbot_role, name='delete_chatbot_role'),
    path('api/mi-status/', get_users_list, name='ver_mi_status'),
    path('api/servicios-estudiante/', api_get_servicios_estudiante, name='api_servicios_estudiante'),

    path('gestion/tipos/crear/', create_process_type, name='create_process_type'),
    path('gestion/tipos/editar/<int:type_id>/', edit_process_type, name='edit_process_type'),
    path('gestion/tipos/eliminar/<int:type_id>/', delete_process_type, name='delete_process_type'),

    path("api/proceso-servicios/", api_get_proceso_servicios),
    path("api/servicios-de-proceso/", api_get_servicios_de_proceso, name="api_servicios_de_proceso"),
    path("api/procesos-por-audiencia/", api_get_procesos_por_audiencia, name="api_procesos_por_audiencia"),
    path("api/requisitos-de-servicio/", api_get_requisitos_de_servicio, name="api_requisitos_de_servicio"),

]


