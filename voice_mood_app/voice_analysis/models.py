from django.db import models

class VoiceSession(models.Model):
    session_id = models.CharField(max_length=50, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Session {self.session_id} - {self.created_at}"

class VoiceAnalysis(models.Model):
    session = models.ForeignKey(VoiceSession, on_delete=models.CASCADE, related_name='analyses')
    audio_file = models.FileField(upload_to='voice_recordings/')
    transcribed_text = models.TextField(blank=True, null=True)
    detected_mood = models.CharField(max_length=100, blank=True, null=True)
    energy_level = models.CharField(max_length=50, blank=True, null=True)
    therapeutic_response = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Analysis for {self.session} - {self.detected_mood}"
