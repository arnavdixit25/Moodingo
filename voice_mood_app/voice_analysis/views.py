import os
import uuid
import json
import requests
import tempfile
import librosa
import numpy as np
from django.conf import settings
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser
from .models import VoiceSession, VoiceAnalysis
from .serializers import VoiceSessionSerializer, VoiceAnalysisSerializer

class ProcessAudioView(APIView):
    parser_classes = [MultiPartParser]
    
    def post(self, request, format=None):
        try:
            # Get or create session
            session_id = request.data.get('session_id', str(uuid.uuid4()))
            session, created = VoiceSession.objects.get_or_create(session_id=session_id)
            
            # Get audio file from request
            audio_file = request.FILES.get('audio')
            if not audio_file:
                return Response({'error': 'No audio file provided'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Save the audio file temporarily
            with tempfile.NamedTemporaryFile(suffix='.webm', delete=False) as temp_file:
                for chunk in audio_file.chunks():
                    temp_file.write(chunk)
                temp_file_path = temp_file.name
            
            # Create a new voice analysis record
            voice_analysis = VoiceAnalysis(session=session)
            voice_analysis.audio_file.save(f"{uuid.uuid4()}.webm", audio_file)
            
            # Analyze audio features using librosa
            energy_level = self.analyze_audio_energy(temp_file_path)
            voice_analysis.energy_level = energy_level
            
            # Transcribe audio using AssemblyAI
            transcribed_text = self.transcribe_audio(temp_file_path)
            voice_analysis.transcribed_text = transcribed_text
            
            # Analyze mood using Akash Chat API
            detected_mood = self.analyze_mood(transcribed_text, energy_level)
            voice_analysis.detected_mood = detected_mood
            
            # Generate therapeutic response
            therapeutic_response = self.generate_therapeutic_response(transcribed_text, detected_mood, energy_level)
            voice_analysis.therapeutic_response = therapeutic_response
            
            # Save the analysis
            voice_analysis.save()
            
            # Clean up temporary file
            os.unlink(temp_file_path)
            
            return Response({
                'session_id': session_id,
                'transcribed_text': transcribed_text,
                'detected_mood': detected_mood,
                'energy_level': energy_level,
                'therapeutic_response': therapeutic_response
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def analyze_audio_energy(self, audio_path):
        """Analyze the energy level of the audio."""
        try:
            # Load audio file with librosa
            y, sr = librosa.load(audio_path, sr=None)
            
            # Calculate energy (RMS)
            rms = librosa.feature.rms(y=y).mean()
            
            # Categorize energy level
            if rms < 0.05:
                return "very low"
            elif rms < 0.1:
                return "low"
            elif rms < 0.2:
                return "medium"
            elif rms < 0.3:
                return "high"
            else:
                return "very high"
        except Exception as e:
            print(f"Error analyzing audio energy: {e}")
            return "unknown"
    
    def transcribe_audio(self, audio_path):
        """Transcribe audio using AssemblyAI API."""
        try:
            # Upload audio file
            upload_url = self.upload_audio_to_assemblyai(audio_path)
            if not upload_url:
                return "Transcription failed: Unable to upload audio"
            
            # Request transcription
            transcript_id = self.request_assemblyai_transcription(upload_url)
            if not transcript_id:
                return "Transcription failed: Unable to start transcription"
            
            # Poll for results
            transcribed_text = self.poll_assemblyai_transcription(transcript_id)
            return transcribed_text or "Transcription failed: No result received"
            
        except Exception as e:
            print(f"Error transcribing audio: {e}")
            return f"Transcription error: {str(e)}"
    
    def upload_audio_to_assemblyai(self, audio_path):
        """Upload audio file to AssemblyAI."""
        headers = {
            "authorization": settings.ASSEMBLYAI_API_KEY
        }
        
        with open(audio_path, "rb") as f:
            response = requests.post(
                "https://api.assemblyai.com/v2/upload",
                headers=headers,
                data=f
            )
        
        if response.status_code == 200:
            return response.json()["upload_url"]
        return None
    
    def request_assemblyai_transcription(self, audio_url):
        """Request transcription from AssemblyAI."""
        headers = {
            "authorization": settings.ASSEMBLYAI_API_KEY,
            "content-type": "application/json"
        }
        
        response = requests.post(
            "https://api.assemblyai.com/v2/transcript",
            headers=headers,
            json={"audio_url": audio_url, "speech_model": "universal"}
        )
        
        if response.status_code == 200:
            return response.json()["id"]
        return None
    
    def poll_assemblyai_transcription(self, transcript_id):
        """Poll for transcription results."""
        headers = {
            "authorization": settings.ASSEMBLYAI_API_KEY
        }
        
        polling_endpoint = f"https://api.assemblyai.com/v2/transcript/{transcript_id}"
        
        # Poll until transcription is complete (with timeout)
        max_polls = 30
        for _ in range(max_polls):
            response = requests.get(polling_endpoint, headers=headers)
            result = response.json()
            
            if result["status"] == "completed":
                return result["text"]
            elif result["status"] == "error":
                return None
            
            import time
            time.sleep(3)
        
        return None
    
    def analyze_mood(self, text, energy_level):
        """Analyze mood using Akash Chat API."""
        if not text or text.strip() == '':
            return "No speech detected"
        
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {settings.AKASH_API_KEY}"
            }
            
            # Create a richer prompt that includes voice energy data
            prompt = f"""
            Analyze the emotional state of a person based on:
            
            1. Their transcribed text: "{text}"
            2. Voice energy level detected: {energy_level}
            
            Respond with a single word that best describes their dominant emotion.
            Examples: happy, sad, angry, anxious, excited, frustrated, neutral, etc.
            """
            
            data = {
                "model": "Meta-Llama-3-1-8B-Instruct-FP8",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an emotion analysis assistant specialized in detecting emotions from voice transcripts and audio features."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            }
            
            response = requests.post(
                "https://chatapi.akash.network/api/v1/chat/completions",
                headers=headers,
                json=data
            )
            
            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"].strip()
            else:
                print(f"Error from Akash API: {response.text}")
                return "Mood analysis failed"
                
        except Exception as e:
            print(f"Error analyzing mood: {e}")
            return "Mood analysis error"
    
    def generate_therapeutic_response(self, text, mood, energy_level):
        """Generate therapeutic response using Akash Chat API."""
        if not text or text.strip() == '':
            return "I didn't catch what you said. Could you please speak again?"
        
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {settings.AKASH_API_KEY}"
            }
            
            prompt = f"""
            Act as a supportive, empathetic AI therapist or friend. 
            
            The person said: "{text}"
            
            Their detected emotional state is: {mood}
            Their voice energy level is: {energy_level}
            
            Provide a thoughtful, caring response (2-4 sentences) that:
            1. Acknowledges their emotional state
            2. Shows empathy and understanding
            3. Offers gentle support or perspective
            4. If appropriate, asks an open-ended follow-up question
            
            Keep your response conversational and natural, as if a supportive friend or therapist were speaking.
            """
            
            data = {
                "model": "Meta-Llama-3-1-8B-Instruct-FP8",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an empathetic AI therapeutic assistant that provides supportive responses to help people process their emotions."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            }
            
            response = requests.post(
                "https://chatapi.akash.network/api/v1/chat/completions",
                headers=headers,
                json=data
            )
            
            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"].strip()
            else:
                print(f"Error from Akash API: {response.text}")
                return "I'm having trouble processing your response right now. How are you feeling today?"
                
        except Exception as e:
            print(f"Error generating therapeutic response: {e}")
            return "I'm here to listen if you'd like to share more about how you're feeling."

class SessionHistoryView(APIView):
    def get(self, request, session_id, format=None):
        try:
            session = VoiceSession.objects.get(session_id=session_id)
            serializer = VoiceSessionSerializer(session)
            return Response(serializer.data)
        except VoiceSession.DoesNotExist:
            return Response({'error': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)