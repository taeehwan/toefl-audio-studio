import os
import pandas as pd
from elevenlabs.client import ElevenLabs
from elevenlabs import save
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
API_KEY = os.getenv("ELEVENLABS_API_KEY")
print(f"API Key status: {'Loaded' if API_KEY else 'Not Loaded'}")
INPUT_FILE = "input_data.csv"
OUTPUT_DIR = "output"
DEFAULT_VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"  # George

if not API_KEY:
    print("Error: ELEVENLABS_API_KEY not found in .env file.")
    print("Please create a .env file with: ELEVENLABS_API_KEY=your_key")
    exit(1)

if API_KEY == "your_elevenlabs_api_key_here":
    print("Error: You are using the default placeholder API key.")
    print("Please open the .env file and paste your actual ElevenLabs API key.")
    exit(1)

# Initialize client
client = ElevenLabs(api_key=API_KEY)

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

def generate_audio(text, voice_id, output_path):
    try:
        audio = client.text_to_speech.convert(
            text=text,
            voice_id=voice_id,
            model_id="eleven_multilingual_v2"
        )
        save(audio, output_path)
        print(f"Successfully generated: {output_path}")
    except Exception as e:
        print(f"Error generating {output_path}: {e}")

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"Error: {INPUT_FILE} not found.")
        return

    df = pd.read_csv(INPUT_FILE)
    
    # Fill missing voice_ids with default
    if 'voice_id' not in df.columns:
        df['voice_id'] = DEFAULT_VOICE_ID
    else:
        df['voice_id'] = df['voice_id'].fillna(DEFAULT_VOICE_ID)

    print(f"Found {len(df)} items to process.")

    for index, row in df.iterrows():
        filename = row['filename']
        text = row['text']
        voice_id = row['voice_id']
        
        # Add extension if missing
        if not str(filename).endswith('.mp3'):
            filename = f"{filename}.mp3"
            
        output_path = os.path.join(OUTPUT_DIR, filename)
        
        print(f"Processing [{index+1}/{len(df)}]: {filename}")
        generate_audio(text, voice_id, output_path)

    print("All done!")

if __name__ == "__main__":
    main()
