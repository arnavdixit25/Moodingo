from django.urls import path
from .views import ProcessAudioView, SessionHistoryView

urlpatterns = [
    path('process-audio/', ProcessAudioView.as_view(), name='process-audio'),
    path('session-history/<str:session_id>/', SessionHistoryView.as_view(), name='session-history'),
]
