import streamlit as st
import os
import pandas as pd
import subprocess
import io
from dotenv import load_dotenv

import google.generativeai as genai
from elevenlabs.client import ElevenLabs
from elevenlabs import save, VoiceSettings

# Load env variables
load_dotenv()

st.set_page_config(page_title="TOEFL 2026 Audio Studio", layout="wide", initial_sidebar_state="expanded")

# --- Configuration ---
OUTPUT_DIR_RAW = "output_toefl_raw"
OUTPUT_DIR_FINAL = "output_toefl_final"
FINAL_FILENAME = "toefl_master_track.mp3"

for d in [OUTPUT_DIR_RAW, OUTPUT_DIR_FINAL]:
    os.makedirs(d, exist_ok=True)

# --- TOEFL Task Presets (The Core Logic) ---
TOEFL_CONFIGS = {
    "Listening Section": {
        "Academic Lecture": {
            "desc": "Professors delivering an academic talk, possibly with student interaction.",
            "roles": ["Narrator (Intro)", "Professor (Main)", "Student (Optional)"],
            "pause_rule": "Standard (0.5s)",
            "voice_style": {"Professor": "Stable/Authoritative", "Student": "Neutral"},
            "mix_logic": "standard"
        },
        "Campus Conversation": {
            "desc": "A student speaking with a university employee (Librarian, Registrar, etc.).",
            "roles": ["Narrator", "Student", "Service Employee"],
            "pause_rule": "Standard (0.5s)",
            "voice_style": {"Student": "Casual", "Employee": "Professional"},
            "mix_logic": "standard"
        },
        "Peer-to-Peer (New 2026)": {
            "desc": "Two students discussing a project/issue. Needs fast pacing and natural tone.",
            "roles": ["Narrator", "Student A", "Student B"],
            "pause_rule": "Fast (0.1s)",
            "voice_style": {"Student A": "Unstable/Natural", "Student B": "Unstable/Natural"},
            "mix_logic": "p2p"
        }
    },
    "Speaking Section": {
        "Listen & Repeat (New 2026)": {
            "desc": "Short sentences for the student to repeat. Needs silence gaps after each line.",
            "roles": ["Narrator"],
            "pause_rule": "Dynamic (1.5x Audio Length)",
            "voice_style": {"Narrator": "High Clarity"},
            "mix_logic": "listen_repeat"
        },
        "Virtual Interview (New 2026)": {
            "desc": "An interviewer asking 5 sequential questions.",
            "roles": ["Interviewer"],
            "pause_rule": "Dynamic (User Response Time - Default 10s?)", # Usually fixed length in test
            "voice_style": {"Interviewer": "Encouraging"},
            "mix_logic": "interview"
        },
        "Integrated Task (Campus)": {
            "desc": "Two students discussing a reading passage/notice.",
            "roles": ["Narrator", "Man", "Woman"],
            "pause_rule": "Standard (0.5s)",
            "voice_style": {"Man": "Casual", "Woman": "Casual"},
            "mix_logic": "standard"
        },
        "Integrated Task (Academic)": {
            "desc": "A professor lecturing on a topic.",
            "roles": ["Narrator", "Professor"],
            "pause_rule": "Standard (0.5s)",
            "voice_style": {"Professor": "Stable"},
            "mix_logic": "standard"
        }
    }
}

VOICE_REGISTRY = {
    "Narrator": {"id": "cjVigY5qzO86Huf0OWal", "stability": 0.90, "similarity": 0.75}, # Eric
    "Professor": {"id": "iP95p4xoKVk53GoZ742B", "stability": 0.80, "similarity": 0.80}, # Chris
    "Interviewer": {"id": "EXAVITQu4vr4xnSDxMaL", "stability": 0.75, "similarity": 0.75}, # Sarah
    "Service Employee": {"id": "EXAVITQu4vr4xnSDxMaL", "stability": 0.80, "similarity": 0.75}, # Sarah
    "Student (M)": {"id": "CwhRBWXzGAHq8TQ4Fs17", "stability": 0.50, "similarity": 0.75}, # Roger
    "Student (F)": {"id": "FGY2WhTYpPnrIDTdsKH5", "stability": 0.45, "similarity": 0.75}, # Laura
}

# --- Helpers ---
def get_voice_for_role(role_name, task_config):
    """
    Intelligent voice mapping based on role name and task context.
    """
    r = str(role_name).lower()
    
    # Narrator is always narrator
    if "narrator" in r: return VOICE_REGISTRY["Narrator"]
    
    # Check specific task context overrides
    if "interviewer" in r: return VOICE_REGISTRY["Interviewer"]
    if "prof" in r or "lecturer" in r or "teacher" in r: return VOICE_REGISTRY["Professor"]
    
    # Student / Peer / Gender logic
    if "man" in r or "male" in r or "driver" in r: return VOICE_REGISTRY["Student (M)"]
    if "woman" in r or "female" in r or "librarian" in r: return VOICE_REGISTRY["Student (F)"] # Map Librarian to female voice
    
    # Fallback for generic "Student"
    if "student" in r:
        # If it's P2P and we need variety, maybe check if it's A or B?
        # For now default to Female for generic student
        return VOICE_REGISTRY["Student (F)"]

    return VOICE_REGISTRY["Narrator"] # Final Fallback

def parse_with_gemini(text, task_name, task_info, api_key):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    prompt = f"""
    You are a TOEFL Script Formatter.
    Task Type: {task_name}
    Description: {task_info['desc']}
    Expected Roles: {", ".join(task_info['roles'])}
    
    Instructions:
    1. Parse the input text into a CSV with 'role' and 'text'.
    2. Map the speakers to the Expected Roles.
       - "M:" -> "Man" or "Student (M)"
       - "W:" -> "Woman" or "Student (F)"
       - "Narrator:" lines ARE spoken text. Must be included.
       - If there is unlabeled intro text, assign it to "Narrator".
    3. Include ALL spoken lines, especially the introductory Narrator line.
    4. Clean up strictly non-spoken text (like page numbers or '(listening)'), but keep the intro sentence.
    5. CRITICAL: Wrap 'text' in double quotes ("") to handle commas.
    
    Raw Output ONLY (no markdown):
    """
    try:
        response = model.generate_content([prompt, text])
        return pd.read_csv(io.StringIO(response.text), quotechar='"', skipinitialspace=True)
    except Exception as e:
        st.error(f"LLM Error: {e}")
        return None

def get_audio_duration(file_path):
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", file_path]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(res.stdout.strip())
    except: return 0.0

def generate_silence(duration, name):
    path = os.path.join(OUTPUT_DIR_FINAL, name)
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"aevalsrc=0:d={duration}", "-q:a", "2", path], 
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return path

def produce_audio(df, task_config, api_key):
    client = ElevenLabs(api_key=api_key)
    assets = []
    
    # 1. Generate
    prog_bar = st.progress(0, text="Generating Voices...")
    for i, row in df.iterrows():
        role = row['role']
        text = row['text']
        
        # Resolve Voice Settings
        v_config = get_voice_for_role(role, task_config)
        
        # Override stability for P2P mode if needed
        stability = v_config['stability']
        if task_config['mix_logic'] == "p2p" and "Student" in role:
            stability = 0.45 # Force lower stability for P2P students
            
        filename = f"{i:03d}_{role[:5]}.mp3"
        out_path = os.path.join(OUTPUT_DIR_RAW, filename)
        
        try:
            audio = client.text_to_speech.convert(
                text=text,
                voice_id=v_config['id'],
                model_id="eleven_multilingual_v2",
                voice_settings=VoiceSettings(
                    stability=stability,
                    similarity_boost=v_config['similarity'],
                    use_speaker_boost=True
                )
            )
            save(audio, out_path)
            assets.append(out_path)
        except Exception as e:
            st.error(f"Gen Error: {e}")
            return None
        prog_bar.progress((i+1)/len(df))
        
    # 2. Mix
    st.write("Mixing Audio Track...")
    concat_path = os.path.join(OUTPUT_DIR_FINAL, "concat.txt")
    mix_logic = task_config['mix_logic']
    
    with open(concat_path, 'w') as f:
        for i, path in enumerate(assets):
            # Use ABSOLUTE PATHS to avoid FFmpeg directory confusion
            abs_path = os.path.abspath(path)
            f.write(f"file '{abs_path}'\n")
            
            # Silence Logic
            pause = 0.5 # Default
            
            if mix_logic == "p2p":
                pause = 0.1 # Fast
            elif mix_logic == "listen_repeat":
                dur = get_audio_duration(path)
                pause = max(2.0, dur * 1.5)
            elif mix_logic == "interview":
                pause = 5.0 # Fixed gap
                
            # Don't add silence after last clip
            if i < len(assets) - 1:
                sil = generate_silence(pause, f"sil_{i}.mp3")
                sil_abs = os.path.abspath(sil)
                f.write(f"file '{sil_abs}'\n")
                
    final_path = os.path.join(OUTPUT_DIR_FINAL, FINAL_FILENAME)
    
    # Run FFmpeg (capture output to debug if needed)
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_path, "-c", "copy", final_path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True
        )
    except subprocess.CalledProcessError as e:
        st.error(f"FFmpeg Merge Failed: {e.stderr.decode()}")
        return None

    return final_path

# --- UI Interface ---

st.sidebar.header("🔑 API Keys")
key_eleven = st.sidebar.text_input("ElevenLabs Key", value=os.getenv("ELEVENLABS_API_KEY", ""), type="password")
key_gemini = st.sidebar.text_input("Gemini Key", value=os.getenv("GEMINI_API_KEY", ""), type="password")

st.sidebar.divider()

st.sidebar.header("📚 Question Type")
section = st.sidebar.selectbox("Test Section", list(TOEFL_CONFIGS.keys()))
task_name = st.sidebar.radio("Task", list(TOEFL_CONFIGS[section].keys()))
task_config = TOEFL_CONFIGS[section][task_name]

# Main Area
st.title(f"{task_name}")
st.caption(f"Section: {section} | Logic: {task_config['mix_logic'].upper()}")

with st.expander("ℹ️ Task Guidelines & Audio Rules", expanded=True):
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown(f"**Description:**\n{task_config['desc']}")
        st.markdown(f"**Expected Roles:**\n" + "\n".join([f"- {r}" for r in task_config['roles']]))
    with col_b:
        st.markdown(f"**Audio Logic:**\n- Pause: `{task_config['pause_rule']}`")
        st.markdown("**Voice Styles:**")
        st.json(task_config['voice_style'])

st.divider()

col_input, col_preview = st.columns([1, 1])

with col_input:
    st.subheader("1. Script Input")
    raw_text = st.text_area("Paste your script here...", height=400, placeholder="Narrator: Listen to a conversation...\nMan: Hi, how are you?\nWoman: I'm good.")
    
    if st.button("Analyze & Parse Script", type="primary"):
        if not key_gemini:
            st.error("Gemini API Key missing")
        else:
            with st.spinner("Analyzing structure..."):
                df = parse_with_gemini(raw_text, task_name, task_config, key_gemini)
                if df is not None:
                    # Clean columns
                    df.columns = [c.lower().strip() for c in df.columns]
                    
                    # Force normalize columns if we have at least 2
                    if len(df.columns) >= 2:
                        # Rename first two columns to what we expect, regardless of what LLM named them
                        new_cols = list(df.columns)
                        new_cols[0] = 'role'
                        new_cols[1] = 'text'
                        df.columns = new_cols
                    
                    st.session_state['df'] = df
                    st.success("Analysis Complete!")

with col_preview:
    st.subheader("2. Production")
    
    if 'df' in st.session_state:
        edited_df = st.data_editor(st.session_state['df'], num_rows="dynamic", use_container_width=True)
        
        if st.button("🎙️ Generate Audio Track"):
            if not key_eleven:
                st.error("ElevenLabs Key missing")
            else:
                final_file = produce_audio(edited_df, task_config, key_eleven)
                if final_file:
                    st.success("Production Complete!")
                    st.audio(final_file)
                    with open(final_file, "rb") as f:
                        st.download_button("Download MP3", f, "toefl_track.mp3")
    else:
        st.info("Paste your script and click Analyze to begin.")
