from rest_framework import serializers
from .models import VoiceSession, VoiceAnalysis

class VoiceAnalysisSerializer(serializers.ModelSerializer):
    class Meta:
        model = VoiceAnalysis
        fields = ['id', 'transcribed_text', 'detected_mood', 'energy_level', 'therapeutic_response', 'created_at']

class VoiceSessionSerializer(serializers.ModelSerializer):
    analyses = VoiceAnalysisSerializer(many=True, read_only=True)
    
    class Meta:
        model = VoiceSession
        fields = ['id', 'session_id', 'created_at', 'analyses']
