from elevenlabs.client import ElevenLabs
import os
from dotenv import load_dotenv

load_dotenv()
client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))

response = client.voices.get_all()
print(f"{'Name':<20} | {'Category':<15} | {'Voice ID':<30} | {'Labels'}")
print("-" * 100)
for voice in response.voices:
    labels = voice.labels if voice.labels else {}
    accent = labels.get('accent', 'N/A')
    gender = labels.get('gender', 'N/A')
    desc = labels.get('description', 'N/A')
    use_case = labels.get('use case', 'N/A')
    print(f"{voice.name:<20} | {voice.category:<15} | {voice.voice_id:<30} | {accent}, {gender}, {desc}, {use_case}")
