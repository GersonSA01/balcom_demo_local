from django.contrib import admin
from .models import RagDocument, BusinessProcess

@admin.register(RagDocument)
class RagDocumentAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'is_indexed', 'doc_id_pgpt', 'fecha_creacion')
    list_filter = ('is_indexed', 'roles')
    search_fields = ('nombre', 'doc_id_pgpt')

@admin.register(BusinessProcess)
class BusinessProcessAdmin(admin.ModelAdmin):
    list_display = ('name', 'status', 'process_type', 'start_date', 'end_date')
    list_filter = ('status', 'process_type')
    search_fields = ('name',)
