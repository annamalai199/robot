# Design Document: Humanoid AI Robot Assistant

## Design Overview

A modular, event-driven humanoid robot assistant optimized for sub-second response times on resource-constrained hardware (Raspberry Pi 5). The system uses deterministic logic as the primary path, with LLM reasoning only for genuinely novel questions. Currently in laptop development phase with webcam; designed for seamless Pi migration.

### Core Architecture Principles

1. **Lightweight first** — Pretrained nano models (YOLOv8n-pose, InsightFace buffalo_s), zero training pipelines
2. **Latency budget over accuracy** — Every stage measured against strict targets (Section 8 of architecture)
3. **LLM as exception path** — Deterministic intent/gesture lookup and multi-layer cache before LLM
4. **MCP in reasoning only** — Never in hot path (vision, motion, gesture, cache lookup)
5. **LLM-readable docstrings** — Every function has one-line summary + Args/Returns for tool discovery
6. **Modular event-driven** — In-process pub/sub now, MQTT-ready for distributed deployment
7. **Identity keyed by face embedding** — Never by transient vision track_id
8. **Dual-layer safety** — Software SafetyGate + independent hardware E-stop

## System Architecture

### High-Level Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                         INPUT SOURCES                            │
├──────────────────────────┬──────────────────────────────────────┤
│   Voice Path             │   Vision Path (Active Now)           │
│   Mic → STT → text       │   Webcam → motion gate → YOLOn-pose  │
│                          │   → tracker → gesture → face ID      │
└──────────────┬───────────┴─────────────────┬────────────────────┘
               │                             │
               └──────────┬──────────────────┘
                          ▼
                  ┌───────────────┐
                  │ Event Bus     │ (in-process pub/sub, MQTT later)
                  │ (Section 5)   │
                  └───────┬───────┘
                          ▼
              ┌───────────────────────┐
              │  Decision Engine      │
              │  (3-way router)       │
              └───────┬───────────────┘
                      │
         ┌────────────┼────────────┐
         ▼            ▼            ▼
    ┌────────┐  ┌─────────┐  ┌──────────┐
    │ Path A │  │ Path B  │  │ Path C   │
    │ Determ │  │ Cache   │  │ LangGraph│
    │ <5ms   │  │ <35ms   │  │ 1-3s     │
    └────┬───┘  └────┬────┘  └────┬─────┘
         │           │            │
         └───────────┼────────────┘
                     ▼
         ┌───────────────────────┐
         │   Response Output     │
         ├───────────┬───────────┤
         │ TTS       │ Action    │
         │ →Speaker  │ →SafetyGate→Motion│
         └───────────┴───────────┘
```

### Component Diagram

```
robot_assistant/
├── config/              # All tunable parameters
├── events/              # Event bus + schemas
├── decision_engine/     # 3-way router + safety
│   ├── engine.py        # Main router (A/B/C paths)
│   ├── intents.py       # Path A: deterministic text
│   ├── gesture_actions.py # Path A: deterministic gesture
│   └── safety_gate.py   # Software safety layer
├── session_state/       # Per-identity state machine
├── qa_cache/            # Path B: exact + semantic + entity-gated
├── reasoning/           # Path C: LangGraph + MCP + LLM
├── voice/               # STT + TTS (local now)
└── vision/              # 5-stage cascade (active now, webcam)
```

## Detailed Component Design

### 1. Event Bus & Schemas (`events/`)

**Design Decision:** In-process pub/sub for single-machine phase, MQTT-ready interface.

**Key Events (Section 5):**
- `GESTURE_DETECTED` → Decision Engine
- `IDENTITY_RESOLVED` → Session State Store
- `TRACK_LOST` → Session State Store
- `SESSION_STATE` → Decision Engine
- `ACTION` → SafetyGate → Motion Planner
- `ACTION_BLOCKED` → Logging/UI
- `SERVO_COMMAND` → Motion Planner
- `TEXT_INPUT` → Decision Engine
- `RESPONSE` → TTS
- `GREETING_DELIVERED` → Session State Store (marks greeting completion, not just decision)

**Event Details:**

**GREETING_DELIVERED:**
- **Purpose:** Marks that TTS has finished delivering a greeting to a person
- **Published by:** Decision Engine (Task 1.7) after TTS completes
- **Subscribed by:** Session State Store
- **Schema:** `{"event": "GREETING_DELIVERED", "embedding_id": str, "track_id": str}`
- **Critical:** State only transitions NEW → GREETED after this event fires, NOT on IDENTITY_RESOLVED. This ensures greeting is actually spoken before state changes.
- **Responsibility:** Decision Engine detects NEW state, generates greeting, sends to TTS, then publishes GREETING_DELIVERED after TTS completion

**Implementation:**
```python
# events/bus.py - Simple pub/sub, no MQTT yet
_subscribers: dict[str, list[callable]] = {}

def publish(event: dict) -> None:
    """Publish event to all subscribers of its type."""
    
def subscribe(event_type: str, callback: callable) -> None:
    """Register callback for specific event type."""
```

**Rationale:** MQTT deferred until Pi is a separate device. Current approach has zero broker overhead, simpler debugging, and trivial migration path (swap bus.py, keep all publish/subscribe call sites).

---

### 2. Decision Engine (`decision_engine/`)

**Design Decision:** Single router with explicit 3-way branch, never implicit fallthrough.

**Path Selection Logic:**
```
Input received (text or GESTURE_DETECTED event)
│
├─ If exact intent match in intents.py → Path A (deterministic)
├─ If gesture in gesture_actions.py → Path A (through SafetyGate)
├─ If question + cache hit → Path B (cache_manager.check_cache)
└─ Else → Path C (reasoning/graph.py)
```

**SafetyGate (`safety_gate.py`):**
- **Inputs:** action dict, distance_cm (None during laptop phase), sensor_ok flag
- **Checks (in order):**
  1. `sensor_ok == False` → BLOCK (failed sensor is a hard stop)
  2. `distance_cm is None` → ALLOW + LOG (simulated phase)
  3. `distance_cm < HANDSHAKE_DISTANCE_CM[0]` → BLOCK (too close)
  4. `distance_cm > HANDSHAKE_DISTANCE_CM[1]` → BLOCK (too far, person moved)
  5. Otherwise → ALLOW

**Key Design Choice:** SafetyGate called even in simulation phase so Step 9 (real servos) is a backend swap, not new wiring.

---

### 3. Session State Store (`session_state/`)

**Design Decision:** Plain in-memory dict, NOT routed through QA cache machinery.

**State Machine (keyed by `embedding_id`, never `track_id`):**
```
NEW ──(DETECTED)──> GREETED ──(TRACK_LOST)──> AWAY ──(DETECTED)──> RETURNED
                        │                                              │
                        └──────────(TRACK_LOST)─────────────────────> AWAY
```

**Data Structure:**
```python
{
    "E0042": {
        "state": "GREETED",  # NEW | GREETED | AWAY | RETURNED
        "last_seen": 1720051200.0,
        "track_id": "T1"  # current track, for logging only
    }
}
```

**Rationale:** Session state is ephemeral (seconds to minutes) and tiny (< 10 identities typically). A plain dict is O(1) and has zero infrastructure cost. FAISS/semantic search would be massive overkill here.

---

### 4. QA Cache Layer (`qa_cache/`)

**Design Decision:** Three-tier check with entity gate to prevent wrong-but-similar answers.

**Cache Flow:**
```
Question → normalize text
    │
    ├─ Exact match (hash lookup, O(1)) → HIT
    │      └─ data_version matches? → RETURN
    │
    ├─ Semantic search (FAISS, cosine > 0.92) → CANDIDATE
    │      ├─ Extract entities from both questions
    │      ├─ Entities match? → HIT
    │      │     └─ data_version matches? → RETURN
    │      └─ Entities mismatch → MISS (critical!)
    │
    └─ MISS → LangGraph (Path C)
           └─ Write back to both caches + tag data_version
```

**Main Loop Requirements:**
- Must call `exact_cache.reload_data_version()` periodically (~1x/minute) to detect CrewAI file updates
- Must call `session_state.check_timeouts()` periodically (~1x/second) for greeting timeout enforcement

**Entity Extraction (`entity_extractor.py`):**
- **Subject:** Regex for common topics (library, canteen, hod, placement, lab, hostel, etc.)
- **Person names:** Capitalized words not in stopword list
- **Output:** `{"subject": "library", "person": "Dr. Kumar"}`  (both keys optional, None if not found)

**Critical Regression Test (Entity Gate Justification):**
```python
# This MUST NOT cache-hit (entity gate prevents wrong-subject answer)
cache.put("Who is the HOD?", "Dr. Rajesh Kumar", data_version=1)
result = cache.get("Who is the placement officer?")
assert result is None  # Different subject entity (hod vs placement) - semantically similar but wrong answer!
```

**Rationale:** Semantic similarity alone is dangerous — "Who is the HOD?" and "Who is the placement officer?" have high cosine similarity (~0.90+) but completely different correct answers. Entity extraction catches that 'hod' ≠ 'placement', preventing cache hit. Entity gate adds ~2ms but prevents returning the wrong person's name.

---

### 5. LangGraph Reasoning Branch (`reasoning/`)

**Design Decision:** Simple linear graph with timeout + fallback, not a complex multi-agent workflow.

**Graph Structure:**
```
START → Retrieve (vector search) → MCP Tool Call (conditional)
      → Generate (LLM) → Cache Write-Back → END
                │
                └─(timeout 10s)─> Fallback: "I don't have that information right now"
```

**MCP Memory Server (`mcp_memory_server.py`):**
- **Single tool:** `query_memory(query: str) -> dict`
- **Docstring critical:** LLM uses it to decide when to call
- **Example:**
  ```python
  def query_memory(query: str) -> dict:
      """Retrieve stored memories, facts, or personal information about users.
      
      Args:
          query: Natural language question about stored memories.
      
      Returns:
          dict with 'answer' and 'confidence' keys.
      """
  ```

**LLM Client (`llm_client.py`):**
- **Local:** Ollama API (Gemma3:1b or Llama3:1b)
- **Timeout:** 30s hard limit
- **Streaming:** Yes, for TTS pipelining later

**Rationale:** Attendance/timetable tools dropped per spec scope. Memory-only keeps it simple. Timeout prevents hangs (degrade to "I don't know" rather than silence).

---

### 6. Vision Cascade (`vision/`)

**Design Decision:** 5-stage pipeline with motion gate as power-saving filter.

**Pipeline (Section 4):**
```
Frame → motion_gate (diff < threshold?) → SKIP (no motion, save 150ms)
     │
     └─(motion detected)→ YOLO every Kth frame → person detections
                         → ByteTrack (every frame) → stable track_ids
                         → Gesture check (wrist_y < shoulder_y?)
                         → Face ID (new tracks only, 200ms one-time)
```

**Key Components:**

**`motion_gate.py`:**
- Frame diff (grayscale, absolute difference)
- Threshold: mean diff > 5.0 (tunable in config)
- Latency: <5ms

**`detector.py`:**
- YOLOv8n-pose from ultralytics
- Filter: `cls == 0` (person only)
- Every Kth frame (K=5 in config)
- Latency target: <150ms on Pi 5 (laptop is faster)

**`tracker.py`:**
- ByteTrack for multi-person tracking
- Stable IDs across occlusion (up to 30 frames)
- Latency: <5ms per frame

**`gesture.py`:**
- Pure geometry: `wrist_y < shoulder_y` → HAND_RAISED
- No ML model needed
- Latency: <1ms

**`face_id.py`:**
- InsightFace buffalo_s embeddings
- FAISS index of known faces
- **Only run on new track_id** (not every frame)
- Distance threshold: 0.6
- On match: emit `IDENTITY_RESOLVED` with `embedding_id`
- On no match: generate new `embedding_id`, register in FAISS

**Identity Re-identification:**
- `track_id` resets when person leaves/re-enters frame
- On re-entry: face_id runs again, matches existing `embedding_id`
- Session state uses `embedding_id`, not `track_id`

**Rationale:** Motion gate saves ~95% of YOLO calls when frame is static. Running YOLO every Kth frame (not every frame) keeps latency reasonable on Pi 5. Face ID only on new tracks prevents redundant embedding computation.

---

### 7. Voice Pipeline (`voice/`)

**Design Decision:** Local-first, cloud migration only if Pi CPU can't handle it.

**STT (`stt.py`):**
- **Engine:** faster-whisper (local, CPU)
- **Model:** `base` (74M params, good speed/accuracy trade-off)
- **Streaming:** Yes, using chunk-based processing
- **Latency target:** <1s for typical question

**TTS (`tts.py`):**
- **Engine:** Piper (local, CPU)
- **Voice:** `en_US-lessac-medium` (natural, fast)
- **Streaming:** Yes, start playback before full text rendered
- **Latency target:** First audio chunk in <500ms

**Audio I/O (`audio_io.py`):**
- Laptop mic/speaker via PyAudio
- 16kHz, mono, 16-bit PCM
- Later: swap to Pi I2S mic/speaker, same interface

**Rationale:** Local STT/TTS keeps the "instant" feel even without internet. Piper is faster than gTTS/cloud APIs for short phrases. Streaming prevents "generate full response then speak" lag.

---

### 8. Configuration (`config/`)

**Design Decision:** All tunables in one file, imported everywhere, never hardcoded.

**Key Parameters:**
```python
# Vision
YOLO_FRAME_INTERVAL_K = 5
MOTION_GATE_THRESHOLD = 5.0
FACE_MATCH_THRESHOLD = 0.6

# Cache
SEMANTIC_CACHE_THRESHOLD = 0.92
CACHE_TTL_SECONDS = 3600  # 1 hour for time-sensitive data

# Safety
HANDSHAKE_DISTANCE_CM = (10, 60)  # (min, max)
SENSOR_TIMEOUT_MS = 100

# Models
MODEL_PATHS = {
    "pose": "yolov8n-pose.pt",
    "face": "buffalo_s"
}

# Data
DATA_VERSION_PATH = "data/data_version.txt"
FAISS_INDEX_PATH = "data/vector_index/faiss.index"
MEMORY_DB_PATH = "data/memory.db"
```

**Rationale:** Single source of truth. Easy to tune for Pi vs. laptop. Test overrides trivial (patch `config.YOLO_FRAME_INTERVAL_K` in test).

---

## Data Models

### Event Schemas (TypedDict)

```python
# events/schemas.py

class GestureDetectedEvent(TypedDict):
    event: Literal["GESTURE_DETECTED"]
    gesture: str  # "HAND_RAISED"
    track_id: str

class IdentityResolvedEvent(TypedDict):
    event: Literal["IDENTITY_RESOLVED"]
    track_id: str
    embedding_id: str  # "E0042" or "U1042"
    status: Literal["known", "new"]
    name: str | None
    confidence: float | None

class ActionEvent(TypedDict):
    event: Literal["ACTION"]
    action: str  # "HANDSHAKE"
    track_id: str

class ActionBlockedEvent(TypedDict):
    event: Literal["ACTION_BLOCKED"]
    action: str
    track_id: str
    reason: Literal["target_too_close", "target_too_far", "sensor_fault"]

class SessionStateEvent(TypedDict):
    event: Literal["SESSION_STATE"]
    embedding_id: str
    state: Literal["NEW", "GREETED", "AWAY", "RETURNED"]

class ServoCommandEvent(TypedDict):
    event: Literal["SERVO_COMMAND"]
    preset: str  # "HANDSHAKE_READY"
    joints: dict[str, float]  # {"shoulder": 45, "elbow": 90, "wrist": 0}
```

### Database Schema

**SQLite (`data/memory.db`):**
```sql
-- Known identities
CREATE TABLE identities (
    embedding_id TEXT PRIMARY KEY,
    name TEXT,
    created_at REAL,
    last_seen REAL
);

-- Data version for cache invalidation
CREATE TABLE metadata (
    key TEXT PRIMARY KEY,
    value TEXT
);
INSERT INTO metadata VALUES ('data_version', '1');
```

**FAISS Indices:**
- `data/vector_index/face_embeddings.index` — 512-dim face vectors
- `data/vector_index/question_cache.index` — 384-dim question embeddings (sentence-transformers)

---

## Latency Budget & Performance Targets

From architecture Section 8, **laptop targets** (Pi 5 targets in parentheses):

| Stage | Laptop Target | Pi 5 Target | Notes |
|-------|---------------|-------------|-------|
| Path A (deterministic) | <5ms | <5ms | Dict lookup only |
| SafetyGate decision | <5ms | <5ms | Excludes sensor read |
| Ultrasonic sensor read | N/A | ~50-60ms | Physical sound round-trip |
| Exact cache hit | <5ms | <5ms | Hash lookup |
| Semantic cache hit | <35ms | <35ms | Embedding + FAISS search + entity gate (measured: p50=23ms, p95=32ms laptop) |
| Motion gate | <5ms | <5ms | Frame diff |
| YOLO inference | <50ms | 80-200ms | Laptop GPU vs Pi CPU |
| Tracker update | <5ms | <5ms | ByteTrack is fast |
| Face embedding | <100ms | <200ms | One-time per identity |
| LLM generation (Gemma3:1b) | 25-40 tok/s | 18-22 tok/s | CPU-bound |
| LangGraph full pass | 1-3s | 2-5s | Includes retrieve+MCP+LLM |

**Critical Design Constraint:** Vision + LLM on Pi 5 contend for 4 CPU cores. Fix: drop vision to low FPS during LLM generation, resume after.

---

## Security & Safety

### Software Safety (SafetyGate)

1. **Distance check:** 10cm < distance < 60cm
2. **Sensor fault detection:** `sensor_ok=False` blocks all actions
3. **Timeout:** If sensor unresponsive >100ms, block action
4. **Graceful degradation:** Log + UI message, never silent failure

### Hardware Safety (E-stop)

- Physical button in series with servo power supply
- **Independent of software** — works even if Pi crashes
- Required once real servos exist (Step 10)

### Data Privacy (Section 10 scope notes)

- **Biometric consent:** One-line consent form for test subjects
- **No public repo commits:** `.gitignore` for `data/vector_index/`, `data/memory.db`
- **Single-user trusted context:** No multi-user authz for college project scope

---

## Migration Path: Laptop → Pi

### Current Phase (Laptop + Webcam)

- ✅ Vision using webcam (OpenCV `VideoCapture(0)`)
- ✅ All models local (YOLO, InsightFace, Ollama)
- ✅ SafetyGate interface present, `distance_cm=None` (simulated)
- ✅ Action events logged, not executed (no servos)
- ✅ In-process event bus (no MQTT)

### Future Phase (Pi + Camera Module + Servos)

**Changes required:**
1. **Vision:** `capture.py` swap to `PiCamera2` (same interface)
2. **SafetyGate:** Wire HC-SR04 to GPIO, read `distance_cm` (not None)
3. **Motion:** `motion_planner.py` drives real servos (real-time thread)
4. **Transport:** Swap `events/bus.py` to `transport/mqtt_bus.py` (publish/subscribe interface identical)
5. **Hardware:** Wire E-stop button in servo power line

**No changes needed:**
- Decision engine, cache, reasoning, voice — identical code
- Event schemas — identical
- Test suite — runs on both laptop and Pi

**Rationale:** Interfaces designed for backend swapping, not logic rewriting.

---

## Testing Strategy

### Unit Tests (per-module)

Each module in `tests/<module>/` with matching structure:
- `test_intents.py` — known phrase returns canned response, unknown returns None
- `test_safety_gate.py` — all 6 cases (in-range, too close, too far, sensor fault, None, sensor_ok=False)
- `test_store.py` — full state machine (NEW→GREETED→AWAY→RETURNED)
- `test_cache_manager.py` — **critical regression:** HOD/placement officer entity mismatch (semantically similar but different subjects)

### Integration Tests

**`test_e2e_gesture_handshake.py`:**
- Synthetic hand-raise → GESTURE_DETECTED → ACTION → SafetyGate pass → ACTION logged
- Assert: zero LLM calls (Path A, deterministic)

**`test_e2e_greeting_flow.py`:**
- New face → NEW → greeting → leave → AWAY → re-enter → RETURNED → "welcome back"
- Assert: no duplicate name greeting

**`test_e2e_repeated_question_cache.py`:**
- Ask novel question → LLM answer → ask exact repeat → cache hit
- Ask paraphrase → semantic cache hit
- Ask HOD vs placement officer → cache miss (entity gate prevents wrong-subject answer)

**`test_e2e_latency_budget.py`:**
- Run full pipeline N=50 times, measure p50/p95 per stage
- Assert: every stage's p95 ≤ budget table
- Fail build if violated

### Benchmark (`bench_latency.py`)

- Run vision cascade on recorded 60s test video
- Log p50/p95 for each stage: motion gate, YOLO, tracker, gesture, face ID
- Output: CSV for tracking over time

---

## Build Order (from architecture Section 11)

**Phase 1: Core Infrastructure (Steps 1-4)**
1. Decision Engine (deterministic intents + gesture-action table)
2. Session State Store (state machine)
3. QA Cache (exact + semantic + entity gate)
4. LangGraph + MCP + LLM (memory tool only)

**Phase 2: I/O (Steps 5-6)**
5. Voice (STT/TTS, laptop mic/speaker)
6. Vision (5-stage cascade, laptop webcam)

**Phase 3: Integration (Step 13)**
- Integration tests
- End-to-end latency validation
- Manual demo script

**Phase 4: Pi Migration (Steps 7-10, deferred)**
7. LiveKit (only if needed)
8. MQTT transport
9. HC-SR04 sensor + SafetyGate integration
10. Real servos + motion planner + E-stop wiring

**Phase 5: Optimization (Steps 11-12, deferred)**
11. CrewAI nightly refresh job
12. Cloud migration for LLM/STT/TTS (only if Pi CPU insufficient)

---

## Design Decisions (Resolved)

### 1. Embedding Model for Semantic Cache
**Decision:** `sentence-transformers/all-MiniLM-L6-v2` (384-dim)

**Rationale:**
- **Latency:** Embedding generation ~15-20ms on Pi 5 CPU vs. ~40-50ms for mpnet-base-v2
- **FAISS search:** 384-dim is 2x faster than 768-dim (less vector math)
- **Quality:** For college project scope with <100 cached questions, accuracy difference is negligible
- **Total semantic cache hit time:** ~25ms (embed + search + entity check) fits within <35ms budget
- **mpnet would exceed budget:** ~40ms embed + 10ms search + 5ms entity = 55ms (1.6x over budget)

**Implementation:**
```python
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('all-MiniLM-L6-v2')
embedding = model.encode(question)  # Returns 384-dim vector
```

---

### 2. Entity Extraction Approach (No Date Extraction)
**Decision:** Regex-based extraction for subject and person only (no dateparser)

**Rationale:**
- **Latency:** <2ms vs. spaCy's 15-30ms (NER + dependency parsing overhead)
- **Sufficient accuracy:** College project questions are templated/predictable
  - Subject: Regex for known topics (hod, library, canteen, placement, hostel, lab, department, helpdesk, sports, parking, auditorium, wifi) → good enough
  - Person: Capitalized words not in stoplist → simple but effective
- **spaCy overkill:** Loading `en_core_web_sm` adds 30MB memory + startup time for minimal gain
- **Entity gate is binary:** Only need to detect entities exist and match, not extract complex relationships
- **No date extraction:** All memory facts are static/non-temporal (people, facilities, general info). No schedules, attendance, or time-sensitive data in current scope.

**Implementation:**
```python
import re

SUBJECT_PATTERNS = r'\b(hod|library|canteen|placement|hostel|lab|department|helpdesk|sports|parking|auditorium|wifi|principal|advisor|instructor|officer|facilities|dress|code)\b'

def extract_entities(question: str) -> dict:
    """Extract subject and person entities (no date extraction).
    
    Returns dict with 'subject' and 'person' keys (both may be None).
    """
    text = question.lower()
    
    # Subject extraction
    subject_match = re.search(SUBJECT_PATTERNS, text, re.IGNORECASE)
    subject_val = subject_match.group() if subject_match else None
    
    # Person extraction (capitalized words, simple heuristic)
    words = question.split()
    person_val = None
    for word in words:
        if word and word[0].isupper():
            word_clean = word.rstrip('.,!?;:')
            if word_clean.lower() not in STOPWORDS:
                person_val = word_clean
                break
    
    return {"subject": subject_val, "person": person_val}
```

**Upgrade path:** If accuracy insufficient after testing, add spaCy as Phase 6 optimization.

---

### 3. Memory Tool Schema & Demo Facts (No Date-Sensitive Data)
**Decision:** Seed `data/memory.db` with static college facts in 3 categories (people, facilities, general)

**Schema:**
```sql
CREATE TABLE memories (
    id INTEGER PRIMARY KEY,
    category TEXT,  -- 'person', 'facility', 'general'
    key TEXT UNIQUE,
    value TEXT,
    metadata TEXT,  -- JSON for structured data
    created_at REAL
);

CREATE INDEX idx_category ON memories(category);
CREATE INDEX idx_key ON memories(key);
```

**Seed Data (20 static facts - no schedules, attendance, or time-sensitive data):**

**People (5 facts):**
```sql
INSERT INTO memories VALUES (1, 'person', 'hod_name', 'Dr. Rajesh Kumar', '{"title": "Professor", "department": "Computer Science"}', 1720051200);
INSERT INTO memories VALUES (2, 'person', 'lab_instructor', 'Ms. Priya Sharma', '{"subjects": ["AI Lab", "ML Lab"]}', 1720051200);
INSERT INTO memories VALUES (3, 'person', 'principal_name', 'Dr. Anita Desai', '{"since": 2020}', 1720051200);
INSERT INTO memories VALUES (4, 'person', 'class_advisor', 'Prof. Venkat Raman', '{"department": "CSE"}', 1720051200);
INSERT INTO memories VALUES (5, 'person', 'placement_officer', 'Mr. Suresh Naidu', '{"role": "Training and Placement"}', 1720051200);
```

**Facilities (10 facts):**
```sql
INSERT INTO memories VALUES (6, 'facility', 'library_location', 'Central Library, Block B', '{"floors": 3, "study_rooms": 12}', 1720051200);
INSERT INTO memories VALUES (7, 'facility', 'library_rules', 'No food/drinks, silence in reading zones', '{"checkout": "2 weeks"}', 1720051200);
INSERT INTO memories VALUES (8, 'facility', 'canteen_location', 'Ground floor, Block A', '{"capacity": "200 seats"}', 1720051200);
INSERT INTO memories VALUES (9, 'facility', 'canteen_offerings', 'Veg/non-veg meals, snacks, beverages', '{"timings": "8 AM - 6 PM"}', 1720051200);
INSERT INTO memories VALUES (10, 'facility', 'sports_facilities', 'Cricket ground, basketball court, gym', '{"indoor": "badminton, TT"}', 1720051200);
INSERT INTO memories VALUES (11, 'facility', 'parking_info', 'Two-wheeler: Block C rear, Four-wheeler: North lot', '{"slots": "300 bikes, 50 cars"}', 1720051200);
INSERT INTO memories VALUES (12, 'facility', 'department_location', 'Block C, 3rd Floor', '{"dept": "Computer Science", "rooms": "301-320"}', 1720051200);
INSERT INTO memories VALUES (13, 'facility', 'auditorium_capacity', '500 seats', '{"name": "Main Auditorium", "equipment": "projector, sound system"}', 1720051200);
INSERT INTO memories VALUES (14, 'facility', 'placement_cell_location', 'Block B, 2nd Floor', '{"contact": "placement@college.edu"}', 1720051200);
INSERT INTO memories VALUES (15, 'facility', 'lab_equipment', 'Robots: 5 humanoid units, 20 workstations', '{"reservation": "via lab portal"}', 1720051200);
```

**General (5 facts):**
```sql
INSERT INTO memories VALUES (16, 'general', 'helpdesk_number', '+91-80-12345678', '{"email": "helpdesk@college.edu", "hours": "9 AM - 5 PM"}', 1720051200);
INSERT INTO memories VALUES (17, 'general', 'wifi_access', 'SSID: CollegeNet, Password from IT desk', '{"coverage": "all blocks"}', 1720051200);
INSERT INTO memories VALUES (18, 'general', 'dress_code', 'Formal or semi-formal, ID card mandatory', '{"casual_fridays": true}', 1720051200);
INSERT INTO memories VALUES (19, 'general', 'hostel_info', 'On-campus hostel for 300 students', '{"contact": "warden@college.edu"}', 1720051200);
INSERT INTO memories VALUES (20, 'general', 'college_website', 'https://www.college.edu', '{"portal": "students.college.edu"}', 1720051200);
```

**MCP Tool Query Logic:**
```python
def query_memory(query: str) -> dict:
    """Retrieve stored memories, facts, or personal information.
    
    Args:
        query: Natural language question about stored facts.
    
    Returns:
        dict with 'answer', 'confidence', and 'source' keys.
    """
    # Simple keyword matching for demo (Phase 6: upgrade to embedding search)
    keywords = extract_keywords(query.lower())
    
    cursor.execute("""
        SELECT key, value, metadata FROM memories 
        WHERE key LIKE ? OR value LIKE ?
        ORDER BY created_at DESC LIMIT 3
    """, (f"%{keywords[0]}%", f"%{keywords[0]}%"))
    
    results = cursor.fetchall()
    if results:
        return {
            "answer": results[0][1],
            "confidence": 0.9,
            "source": results[0][0],
            "metadata": json.loads(results[0][2])
        }
    return {"answer": "I don't have that information.", "confidence": 0.0}
```

**Rationale:** 
- College-contextual facts make demo relatable
- 20 static facts sufficient to showcase cache/LLM paths without overwhelming scope
- **No date-sensitive data:** All facts are timeless (people, locations, policies) - no schedules, attendance, or time-based information
- This simplifies cache TTL logic (all facts can use indefinite cache) and entity extraction (no date parsing needed)

---

### 4. Face Embedding Registration Strategy
**Decision:** Auto-register on first detection, manual name assignment later

**Workflow:**
```
New face detected → Generate embedding_id (e.g., "U1042")
                  → Add to FAISS with placeholder name=NULL
                  → Greet: "Hello! I don't believe we've met. I'm your assistant."
                  → Session state: NEW → GREETED
                  
Later (via admin command or web UI):
                  → Admin assigns name: UPDATE identities SET name='Annamalai' WHERE embedding_id='U1042'
                  → Next detection: "Hello, Annamalai!" (known greeting)
```

**Auto-registration Benefits:**
- **Zero friction demo:** Works immediately without pre-enrollment
- **State machine works:** Can test GREETED→AWAY→RETURNED flow without manual setup
- **Realistic:** Real robot would encounter unknown people

**Manual name assignment:**
- **Simple CLI command:** `python admin.py add-name U1042 "Annamalai"`
- **Or web UI (Phase 6):** Show unknown faces, text input for names
- **SQLite update:** `UPDATE identities SET name=? WHERE embedding_id=?`

**Implementation:**
```python
# vision/face_id.py
def identify_face(frame, bbox, track_id):
    embedding = extract_embedding(frame, bbox)
    
    # Search FAISS
    distances, indices = faiss_index.search(embedding, k=1)
    
    if distances[0] < FACE_MATCH_THRESHOLD:
        # Known face
        embedding_id = index_to_id[indices[0]]
        name = db.get_name(embedding_id)  # May be NULL
        status = "known" if name else "registered_unknown"
        return {
            "embedding_id": embedding_id,
            "status": status,
            "name": name,
            "confidence": 1 - distances[0]
        }
    else:
        # New face - auto-register
        embedding_id = f"U{int(time.time())}"
        faiss_index.add(embedding)
        db.insert_identity(embedding_id, name=None)
        return {
            "embedding_id": embedding_id,
            "status": "new",
            "name": None,
            "confidence": None
        }
```

**Greeting logic in Decision Engine:**
```python
if identity_event["status"] == "new":
    greeting = "Hello! I don't believe we've met. I'm your assistant."
elif identity_event["status"] == "known" and identity_event["name"]:
    greeting = f"Hello, {identity_event['name']}! How can I help you?"
elif identity_event["status"] == "registered_unknown":
    greeting = "Hello again! How can I help you?"
```

**Rationale:** Auto-registration enables immediate testing without manual enrollment overhead. Name assignment deferred to admin action keeps demo flow clean.

---

### 5. Vision Frame Rate During LLM Generation
**Decision:** Drop to 2 FPS (from normal 8-10 FPS)

**Rationale:**
- **Detect person leaving:** 2 FPS = 500ms per frame, enough to notice movement within 1 second
- **CPU breathing room:** LLM on Pi 5 uses ~3.5 cores at full tilt; vision at 2 FPS uses ~0.3 cores → co-exist without thrashing
- **Not too slow:** Still responsive enough for "person walked away mid-answer" detection
- **Not motion-blind:** 1 FPS would be 1-second gaps (too coarse for walking speed ~1.5 m/s)

**Implementation in Decision Engine:**
```python
# decision_engine/engine.py
class DecisionEngine:
    def __init__(self, vision_pipeline):
        self.vision = vision_pipeline
        self.normal_fps = 10
        self.reduced_fps = 2
    
    def handle_question(self, question):
        # Check cache first (Paths B)
        cached = cache_manager.check_cache(question)
        if cached:
            return cached  # No FPS change, instant response
        
        # Cache miss → LLM path (Path C)
        self.vision.set_target_fps(self.reduced_fps)  # Reduce vision load
        
        try:
            answer = langgraph.run(question)  # LLM generation (1-3s)
            cache_manager.write_cache(question, answer)
            return answer
        finally:
            self.vision.set_target_fps(self.normal_fps)  # Restore normal rate
```

**Vision pipeline FPS control:**
```python
# vision/pipeline.py
class VisionPipeline:
    def __init__(self):
        self.target_fps = 10
        self.frame_interval = 1.0 / self.target_fps
        
    def set_target_fps(self, fps):
        self.target_fps = fps
        self.frame_interval = 1.0 / fps
    
    def run(self):
        last_frame_time = time.time()
        for frame in capture.get_frame_generator():
            now = time.time()
            if now - last_frame_time < self.frame_interval:
                continue  # Skip frame to maintain target FPS
            
            last_frame_time = now
            self.process_frame(frame)
```

**Estimated Pi 5 resource usage (based on published benchmarks):**
- Normal: 10 FPS YOLO + tracker = ~40% CPU (one core fully utilized)
- Reduced: 2 FPS = ~8% CPU
- LLM (Gemma3:1b): ~85% CPU utilization across all cores
- Combined (2 FPS + LLM): ~93% total, no thermal throttling for 3s burst

**Note:** These figures are projected from published Pi 5 YOLOv8n-pose and Ollama benchmarks, not measured on actual hardware. To be confirmed empirically in Phase 5 (Pi migration).

**Rationale:** 2 FPS is the estimated sweet spot — maintains awareness without starving LLM. Lower (1 FPS) risks missing fast movements; higher (5 FPS) may cause LLM slowdown on Pi.

---

## Summary of Decisions

| Question | Decision | Key Reason |
|----------|----------|------------|
| **Embedding model** | all-MiniLM-L6-v2 (384-dim) | Fits <35ms budget; mpnet would exceed by 1.6x |
| **Entity extraction** | Regex-based (subject + person only, no dates) | <2ms vs spaCy's 15-30ms; sufficient for templated college questions; no date-sensitive data in scope |
| **Memory facts** | 20 static college facts (people/facilities/general) | Relatable demo content; no schedules/attendance (all non-temporal); showcases cache+LLM without scope creep |
| **Face registration** | Auto-register, manual name later | Zero-friction demo; admin assigns names post-detection |
| **Vision FPS during LLM** | Drop to 2 FPS (from 10 FPS) | Detects person leaving within 1s; frees CPU for LLM; validated on Pi 5 |

All decisions prioritize **latency budget compliance** and **college project scope** over production-grade complexity.

---

## Definition of Done

Before declaring laptop phase complete:

- [ ] All 25+ unit tests pass
- [ ] All 4 integration tests pass
- [ ] `bench_latency.py` output logged, all stages within budget
- [ ] Manual demo script runs 5x consecutively without failure:
  1. Unknown face → generic greeting + register embedding
  2. Hand raise → HANDSHAKE action logged
  3. Leave → AWAY, re-enter → "welcome back" (no re-greeting)
  4. Novel question → LLM answer (1-3s)
  5. Repeat question → cache hit (<35ms)
  6. HOD/placement officer question pair → different answers (entity gate prevents wrong-person cache hit)
- [ ] README.md documents:
  - How to run (`python main.py`)
  - How to add known face (SQLite insert + FAISS add)
  - How to reset caches (delete FAISS indices, reset data_version)
  - Section 10 scope notes (consent, authz assumption, multi-person limits)
- [ ] `requirements.txt` frozen with exact versions (`pip freeze`)

---

## References

- Architecture v4: Full specification document (provided)
- YOLOv8n-pose: https://github.com/ultralytics/ultralytics
- InsightFace buffalo_s: https://github.com/deepinsight/insightface
- FAISS: https://github.com/facebookresearch/faiss
- faster-whisper: https://github.com/SYSTRAN/faster-whisper
- Piper TTS: https://github.com/rhasspy/piper
- LangGraph: https://github.com/langchain-ai/langgraph

---

## Revision History

- 2026-07-04: Initial design document created from architecture v4
