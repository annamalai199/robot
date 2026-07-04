"""Configuration module for Humanoid AI Robot Assistant.

All tunable parameters in one place. No hardcoded values elsewhere.
Import this module in other components to access configuration.
"""

import os
from pathlib import Path

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent.absolute()
DATA_DIR = PROJECT_ROOT / "data"
VECTOR_INDEX_DIR = DATA_DIR / "vector_index"

# =============================================================================
# Vision Configuration
# =============================================================================

# YOLO Pose Detection
YOLO_FRAME_INTERVAL_K = 5  # Run pose model every Kth frame
MOTION_GATE_THRESHOLD = 5.0  # Mean pixel difference threshold for motion detection

# Face Recognition
FACE_MATCH_THRESHOLD = 0.6  # FAISS distance threshold for identity match (lower = stricter)

# Frame Rate Control
NORMAL_VISION_FPS = 10  # Normal tracking frame rate
REDUCED_VISION_FPS = 2  # Reduced FPS during LLM generation

# =============================================================================
# Cache Configuration
# =============================================================================

# Semantic Cache
SEMANTIC_CACHE_THRESHOLD = 0.92  # Cosine similarity threshold for candidate hit
EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # Sentence transformer model (384-dim)
EMBEDDING_DIM = 384  # Dimension of question embeddings

# Cache Time-to-Live
# Note: All current memory facts are static/non-temporal (people, facilities, general info).
# No date-sensitive data (attendance, schedules, exams) in current scope.
# TTL mechanism stays available but unused - all facts can use CACHE_INDEFINITE policy.
CACHE_TTL_SECONDS = 3600  # Reserved for time-sensitive data if added later
CACHE_INDEFINITE = -1  # Use for static facts (current default)

# =============================================================================
# Safety Configuration
# =============================================================================

# SafetyGate Distance Limits (in centimeters)
HANDSHAKE_DISTANCE_MIN_CM = 10  # Too close - block action
HANDSHAKE_DISTANCE_MAX_CM = 60  # Too far - person moved away, block action

# Sensor Configuration
SENSOR_TIMEOUT_MS = 100  # Max time to wait for sensor reading
SENSOR_FAULT_THRESHOLD = 3  # Consecutive failed readings before marking sensor as faulty

# =============================================================================
# Model Paths
# =============================================================================

MODEL_PATHS = {
    "pose": "yolov8n-pose.pt",  # YOLOv8 nano pose model
    "face": "buffalo_s",  # InsightFace model name
}

# =============================================================================
# Data Paths
# =============================================================================

DATA_VERSION_PATH = DATA_DIR / "data_version.txt"
MEMORY_DB_PATH = DATA_DIR / "memory.db"
FAISS_FACE_INDEX_PATH = VECTOR_INDEX_DIR / "face_embeddings.index"
FAISS_QUESTION_INDEX_PATH = VECTOR_INDEX_DIR / "question_cache.index"
FACE_ID_MAPPING_PATH = VECTOR_INDEX_DIR / "face_id_mapping.json"
QUESTION_CACHE_MAPPING_PATH = VECTOR_INDEX_DIR / "question_cache_mapping.json"

# =============================================================================
# LLM Configuration
# =============================================================================

# Ollama Settings
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "gemma2:2b"  # Or "llama3.2:1b" for faster, lighter option
LLM_TIMEOUT_SECONDS = 30  # Hard timeout for LLM generation
LLM_MAX_TOKENS = 256  # Max tokens per response

# =============================================================================
# Voice Configuration
# =============================================================================

# Speech-to-Text (faster-whisper)
STT_MODEL = "base"  # Options: tiny, base, small, medium, large
STT_LANGUAGE = "en"
STT_DEVICE = "cpu"  # Options: cpu, cuda

# Text-to-Speech (Piper)
TTS_VOICE = "en_US-lessac-medium"
TTS_SAMPLE_RATE = 16000

# Audio I/O
AUDIO_SAMPLE_RATE = 16000  # Hz
AUDIO_CHANNELS = 1  # Mono
AUDIO_CHUNK_SIZE = 1024  # Frames per buffer
AUDIO_FORMAT = "int16"  # 16-bit PCM

# =============================================================================
# LangGraph Configuration
# =============================================================================

LANGGRAPH_TIMEOUT_SECONDS = 10  # Timeout for tool calls
LANGGRAPH_FALLBACK_MESSAGE = "I don't have that information right now. Please try asking in a different way."

# =============================================================================
# Intent & Gesture Configuration
# =============================================================================

# Deterministic intents (text -> response)
INTENT_RESPONSES = {
    "hi": "Hello! How can I help you today?",
    "hello": "Hello! How can I help you today?",
    "hey": "Hello! How can I help you today?",
    "bye": "Goodbye! Have a great day!",
    "goodbye": "Goodbye! Have a great day!",
    "thanks": "You're welcome!",
    "thank you": "You're welcome!",
    "help": "I can answer questions about people, facilities, and general college information. I can also respond to gestures like hand raises.",
    "what can you do": "I can answer questions about people, facilities, and general college information. I can also respond to gestures like hand raises.",
}

# Gesture to action mapping
GESTURE_ACTIONS = {
    "HAND_RAISED": "HANDSHAKE",
}

# =============================================================================
# Greeting Messages
# =============================================================================

GREETING_NEW_UNKNOWN = "Hello! I don't believe we've met. I'm your assistant. How can I help you?"
GREETING_NEW_KNOWN = "Hello, {name}! Nice to meet you. How can I help you?"
GREETING_RETURNED = "Welcome back! What can I help you with?"
GREETING_GENERIC = "Hello! How can I help you?"

# =============================================================================
# Servo Configuration (for future Pi hardware phase)
# =============================================================================

# Preset servo angles (degrees) for handshake gesture
SERVO_PRESETS = {
    "HANDSHAKE_READY": {
        "shoulder": 45,
        "elbow": 90,
        "wrist": 0,
    },
    "REST": {
        "shoulder": 0,
        "elbow": 0,
        "wrist": 0,
    },
}

# =============================================================================
# Logging Configuration
# =============================================================================

LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_TO_FILE = False
LOG_FILE_PATH = PROJECT_ROOT / "robot_assistant.log"

# =============================================================================
# Development Flags
# =============================================================================

# Simulated mode (no real hardware)
SIMULATED_DISTANCE_SENSOR = True  # Set to False when HC-SR04 is connected
SIMULATED_SERVOS = True  # Set to False when real servos are connected

# Debug flags
DEBUG_SHOW_VISION_WINDOW = False  # Show OpenCV window with detections
DEBUG_LOG_EVENTS = True  # Log all event bus events
DEBUG_LOG_LATENCY = True  # Log per-stage latency measurements

# =============================================================================
# Helper Functions
# =============================================================================

def ensure_directories():
    """Create necessary data directories if they don't exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    VECTOR_INDEX_DIR.mkdir(parents=True, exist_ok=True)

def get_data_version() -> int:
    """Get current data version for cache invalidation.
    
    Returns:
        Current data version as integer. Returns 1 if file doesn't exist.
    """
    if not DATA_VERSION_PATH.exists():
        return 1
    try:
        return int(DATA_VERSION_PATH.read_text().strip())
    except (ValueError, IOError):
        return 1

def set_data_version(version: int):
    """Set data version for cache invalidation.
    
    Args:
        version: New data version number.
    """
    ensure_directories()
    DATA_VERSION_PATH.write_text(str(version))

# Initialize data version if it doesn't exist
ensure_directories()
if not DATA_VERSION_PATH.exists():
    set_data_version(1)
