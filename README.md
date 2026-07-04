# Humanoid AI Robot Assistant

A lightweight, latency-optimized humanoid robot assistant with vision-based gesture recognition, face identification, voice interaction, and intelligent question caching.

## Project Status

**Current Phase:** Laptop Development (Phase 1-4)
- ✅ Vision using webcam (OpenCV)
- ✅ Local models (YOLO, InsightFace, Ollama)
- ✅ SafetyGate interface (simulated distance sensor)
- ✅ Action events logged (no real servos yet)
- ✅ In-process event bus (MQTT deferred)

**Future Phase:** Raspberry Pi 5 + Camera Module + Servos (Phase 5-6, deferred)

## Architecture Overview

The system uses a 3-path decision engine:
- **Path A (Deterministic):** Instant intent/gesture lookup (<5ms, no LLM)
- **Path B (Cached):** Exact-match or entity-gated semantic cache (<35ms, no LLM)
- **Path C (Novel):** LangGraph → MCP tool → LLM generation (1-3s)

### Core Components

```
Voice (STT) ──┐
              ├──> Event Bus ──> Decision Engine ──┬──> Path A: Deterministic
Vision ───────┘                                    ├──> Path B: Cache
                                                   └──> Path C: LangGraph + LLM
                                                            │
                    ┌───────────────────────────────────────┘
                    │
                    ├──> Response ──> TTS ──> Speaker
                    └──> Action ──> SafetyGate ──> Motion (simulated)
```

## Installation

### Prerequisites

- Python 3.10 or higher
- Webcam (built-in or USB)
- ~4GB RAM minimum
- Ollama installed and running locally

### Setup Steps

1. **Clone repository:**
```bash
git clone <repository-url>
cd robot_assistant
```

2. **Create virtual environment:**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

4. **Download models:**
```bash
# YOLOv8n-pose (auto-downloads on first run)
# InsightFace buffalo_s (auto-downloads on first run)

# Ollama - install from https://ollama.ai
ollama pull gemma2:2b  # Or llama3.2:1b for faster option
```

5. **Initialize database:**
```bash
python scripts/init_memory_db.py  # Creates memory.db with seed facts
```

6. **Run application:**
```bash
python main.py
```

## Configuration

All tunable parameters are in `robot_assistant/config/config.py`:

```python
# Vision
YOLO_FRAME_INTERVAL_K = 5  # Run pose model every Kth frame
NORMAL_VISION_FPS = 10     # Normal tracking rate
REDUCED_VISION_FPS = 2     # During LLM generation

# Cache
SEMANTIC_CACHE_THRESHOLD = 0.92  # Similarity threshold

# Safety
HANDSHAKE_DISTANCE_MIN_CM = 10   # Too close
HANDSHAKE_DISTANCE_MAX_CM = 60   # Too far

# LLM
OLLAMA_MODEL = "gemma2:2b"
LLM_TIMEOUT_SECONDS = 30
```

## Usage

### Running the Demo

1. **Start the application:**
```bash
python main.py
```

2. **Sit in front of webcam** → Robot detects face, greets generically or by name (if known)

3. **Raise hand** → Robot logs "HANDSHAKE" action (simulated, no servo movement yet)

4. **Ask a question** → Robot answers via LLM or cache

5. **Ask same question again** → Instant cache hit (<35ms)

6. **Leave frame** → Session state changes to AWAY

7. **Re-enter frame** → Robot says "Welcome back" (no re-greeting)

### Managing Known Faces

**Add a name to an auto-registered face:**
```bash
python admin.py add-name U1720051234 "Annamalai"
```

Or manually via SQLite:
```sql
sqlite3 robot_assistant/data/memory.db
UPDATE identities SET name='Annamalai' WHERE embedding_id='U1720051234';
```

**List all registered faces:**
```bash
python admin.py list-faces
```

### Resetting Caches

**Clear question cache (after data update):**
```bash
rm robot_assistant/data/vector_index/question_cache.index
rm robot_assistant/data/vector_index/question_cache_mapping.json
echo "2" > robot_assistant/data/data_version.txt  # Bump version
```

**Clear face embeddings (start fresh):**
```bash
rm robot_assistant/data/vector_index/face_embeddings.index
rm robot_assistant/data/vector_index/face_id_mapping.json
```

## Testing

**Run all tests:**
```bash
pytest
```

**Run specific test suite:**
```bash
pytest tests/decision_engine/
pytest tests/vision/
pytest tests/integration/
```

**Run with coverage:**
```bash
pytest --cov=robot_assistant --cov-report=html
```

**Run latency benchmark:**
```bash
pytest tests/vision/bench_latency.py -v
pytest tests/integration/test_e2e_latency_budget.py -v
```

## Latency Budget

Target latencies (laptop phase, Pi 5 estimates in parentheses):

| Stage | Laptop | Pi 5 (est.) |
|-------|--------|-------------|
| Path A (deterministic) | <5ms | <5ms |
| SafetyGate decision | <5ms | <5ms |
| Exact cache hit | <5ms | <5ms |
| Semantic cache hit | <20ms | <35ms |
| Motion gate | <5ms | <5ms |
| YOLO inference | <50ms | 80-200ms |
| Tracker update | <5ms | <5ms |
| Face embedding | <100ms | <200ms |
| LLM generation (Gemma3:1b) | 25-40 tok/s | 18-22 tok/s |
| LangGraph full pass | 1-3s | 2-5s |

## Project Scope & Limitations

This is a college project demonstration. The following are acknowledged limitations:

### In Scope
- Single-user operation in trusted environment
- Read-only MCP tools (no write operations)
- Auto-registration of faces with manual name assignment
- Basic gesture recognition (hand raise only)
- Local execution on laptop/Pi 5

### Out of Scope (Future Work)
- **Biometric data privacy:** One-line consent for test subjects. Face embeddings not committed to public repo.
- **Multi-user authorization:** Single-user trusted context assumed. No MCP authz layer.
- **Multi-person simultaneous gestures:** Only one person tracked for actions at a time.
- **Crash recovery:** No supervisor/restart strategy for Decision Engine.
- **Dense crowd handling:** Simple track-ID switching covered, not dense occlusion scenarios.
- **Production deployment:** No TLS, authentication, or multi-tenant support.

### Hardware Safety Notes

**Software SafetyGate (current):**
- Distance checks (10-60cm range)
- Sensor fault detection
- Timeout protection

**Hardware E-stop (required for real servos):**
- Physical button in servo power line
- Independent of software/Pi state
- Works even if Pi crashes

## Pi Migration Roadmap

**Phase 5 (Deferred until Pi hardware available):**
1. Swap webcam → Pi Camera Module 3 (`vision/capture.py`)
2. Wire HC-SR04 distance sensor → GPIO
3. Integrate sensor readings with SafetyGate
4. Implement motion planner with real servos
5. Wire hardware E-stop button
6. Replace in-process event bus with MQTT

**Phase 6 (Optimization, deferred):**
1. CrewAI nightly data refresh job
2. Cloud migration for LLM/STT/TTS (only if Pi CPU insufficient)
3. Add spaCy for entity extraction (if regex insufficient)

## Contributing

1. Every module needs a paired test file
2. Run tests before committing: `pytest`
3. Run formatter: `black robot_assistant/`
4. Run linter: `flake8 robot_assistant/`
5. Update latency benchmarks if changing core pipeline

## License

[Add your license here]

## Acknowledgments

- **YOLOv8n-pose:** ultralytics/ultralytics
- **InsightFace buffalo_s:** deepinsight/insightface
- **FAISS:** facebookresearch/faiss
- **faster-whisper:** SYSTRAN/faster-whisper
- **Piper TTS:** rhasspy/piper
- **LangGraph:** langchain-ai/langgraph

## Contact

[Add contact information here]
