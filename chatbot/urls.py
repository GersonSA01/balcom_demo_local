from django.urls import path
from .views import ChatView, health, DocumentUploadView

app_name = 'chatbot'

urlpatterns = [
    path('chat/', ChatView.as_view(), name='chat'),
    path('health/', health, name='health'),
    path('upload-documents/', DocumentUploadView.as_view(), name='upload_documents'),
]

