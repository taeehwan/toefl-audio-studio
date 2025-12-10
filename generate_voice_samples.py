import os
from elevenlabs.client import ElevenLabs
from elevenlabs import save
from dotenv import load_dotenv

load_dotenv()
client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))
OUTPUT_DIR = "output_voicesample"

def generate_samples():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"Created {OUTPUT_DIR}")

    response = client.voices.get_all()
    voices = response.voices
    print(f"Found {len(voices)} voices. Starting generation...")

    for i, voice in enumerate(voices):
        # customized text for each voice
        text = f"Hello, my name is {voice.name}. This is a sample of my voice for your project."
        filename = f"{voice.name}_{voice.voice_id}.mp3"
        output_path = os.path.join(OUTPUT_DIR, filename)

        try:
            print(f"[{i+1}/{len(voices)}] Generating sample for {voice.name}...")
            # Using the updated method call from previous fix
            audio = client.text_to_speech.convert(
                text=text,
                voice_id=voice.voice_id,
                model_id="eleven_multilingual_v2"
            )
            save(audio, output_path)
        except Exception as e:
            print(f"Failed to generate {voice.name}: {e}")

    print("All samples generated!")

if __name__ == "__main__":
    generate_samples()
