import os
import subprocess

INPUT_DIR = "output"
OUTPUT_DIR = "output2"
SPEED_FACTOR = 0.9  # 10% slower

def slow_down_audio():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"Created {OUTPUT_DIR}")

    files = [f for f in os.listdir(INPUT_DIR) if f.endswith(".mp3")]
    total = len(files)
    
    print(f"Found {total} files to process.")

    for i, filename in enumerate(files):
        input_path = os.path.join(INPUT_DIR, filename)
        output_path = os.path.join(OUTPUT_DIR, filename)
        
        # ffmpeg command to change speed without changing pitch (atempo filter)
        # atempo can range from 0.5 to 2.0.
        cmd = [
            "ffmpeg",
            "-y",  # overwrite
            "-i", input_path,
            "-filter:a", f"atempo={SPEED_FACTOR}",
            "-vn",  # no video
            output_path
        ]
        
        try:
            # Run ffmpeg, suppress verbose output
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(f"[{i+1}/{total}] Processed: {filename}")
        except subprocess.CalledProcessError as e:
            print(f"Error processing {filename}: {e}")

if __name__ == "__main__":
    slow_down_audio()
