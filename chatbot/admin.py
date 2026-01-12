from django.contrib import admin
from .models import ChatbotRol, RagDocument, BusinessProcess

@admin.register(ChatbotRol)
class ChatbotRolAdmin(admin.ModelAdmin):
    # CORRECCIÓN: Usamos 'status' (de ModeloBase) en vez de 'activo'
    list_display = ('nombre', 'campo_sga', 'status', 'fecha_creacion')
    list_filter = ('status',) # <-- Esto arregla el error admin.E116
    search_fields = ('nombre', 'campo_sga')
    filter_horizontal = ('carreras',)

@admin.register(RagDocument)
class RagDocumentAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'status', 'is_indexed')
    list_filter = ('status', 'is_indexed')
    filter_horizontal = ('roles_permitidos',)

@admin.register(BusinessProcess)
class BusinessProcessAdmin(admin.ModelAdmin):
    # CORRECCIÓN: Usamos 'nombre' en vez de 'name'
    list_display = ('nombre', 'process_type', 'status', 'start_date', 'end_date') # <-- Arregla admin.E108
    list_filter = ('status', 'process_type', 'is_infinite')
    search_fields = ('nombre', 'descripcion')
    filter_horizontal = ('roles_permitidos',)