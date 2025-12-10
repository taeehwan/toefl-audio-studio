import os
import pandas as pd
import subprocess

# Configuration
INPUT_CSV = "input_data.csv"
AUDIO_DIR = "output2"  # Using the slower version
OUTPUT_FILE = "full_conversation.mp3"
CONCAT_LIST_FILE = "concat_list.txt"

# Pause durations (seconds)
PAUSE_DEFAULT = 0.5
PAUSE_NARRATOR = 1.5

def generate_silence(duration, output_path):
    # Generate silent audio using lavfi
    # aevalsrc=0 generates silence
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"aevalsrc=0:d={duration}",
        "-map", "0:a",
        "-c:a", "libmp3lame", "-q:a", "2",
        output_path
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def assemble_audio():
    if not os.path.exists(INPUT_CSV):
        print(f"Error: {INPUT_CSV} not found.")
        return

    if not os.path.exists(AUDIO_DIR):
        print(f"Error: Audio directory '{AUDIO_DIR}' not found.")
        return

    # Generate silence files
    silence_default_file = "silence_0.5s.mp3"
    silence_narrator_file = "silence_1.5s.mp3"
    
    print("Generating silence tracks...")
    generate_silence(PAUSE_DEFAULT, silence_default_file)
    generate_silence(PAUSE_NARRATOR, silence_narrator_file)
    
    df = pd.read_csv(INPUT_CSV)
    print(f"Found {len(df)} segments to assemble.")

    with open(CONCAT_LIST_FILE, 'w') as f:
        for index, row in df.iterrows():
            filename = row['filename']
            if not str(filename).endswith('.mp3'):
                filename = f"{filename}.mp3"
            
            # Subpath relative to where we run ffmpeg (cwd)
            # escape special chars in filename for ffmpeg concat list if needed, 
            # but usually just filepath is fine if simple.
            file_path = os.path.join(AUDIO_DIR, filename)
            
            if not os.path.exists(file_path):
                print(f"Warning: File {file_path} not found. Skipping.")
                continue
                
            f.write(f"file '{file_path}'\n")
            
            # Determine pause
            is_last = (index == len(df) - 1)
            
            if not is_last:
                if "Narrator" in filename:
                    f.write(f"file '{silence_narrator_file}'\n")
                else:
                    f.write(f"file '{silence_default_file}'\n")

    print(f"Concatenating files into {OUTPUT_FILE}...")
    # FFmpeg concat command
    # -safe 0 allows handling of relative/absolute paths loosely
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", CONCAT_LIST_FILE,
        "-c", "copy",
        OUTPUT_FILE
    ]
    
    try:
        subprocess.run(cmd, check=True) # Let stdout show to verify
        print("\nSuccess! Full conversation created.")
    except subprocess.CalledProcessError as e:
        print(f"Error during concatenation: {e}")
    finally:
        # Cleanup temp files
        if os.path.exists(CONCAT_LIST_FILE):
           os.remove(CONCAT_LIST_FILE)
        if os.path.exists(silence_default_file):
           os.remove(silence_default_file)
        if os.path.exists(silence_narrator_file):
           os.remove(silence_narrator_file)

if __name__ == "__main__":
    assemble_audio()
