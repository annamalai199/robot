# Tasks: Humanoid AI Robot Assistant

## Phase 1: Core Infrastructure

### Task 1.1: Project Setup & Configuration
**Status:** ✅ completed
**Estimated Effort:** 1 hour
**Description:** Set up project structure, create config module with all tunable parameters, and initialize data directories.

**Acceptance Criteria:**
- [x] Directory structure matches architecture (config/, events/, decision_engine/, etc.)
- [x] `config/config.py` contains all parameters from design doc
- [x] `data/` directory exists with subdirs: vector_index/
- [x] `requirements.txt` created with initial dependencies
- [x] `.gitignore` excludes data files (vector_index/, memory.db)
- [x] `README.md` has initial project description
- [x] Database initialization script with 20 seed facts
- [x] Main entry point placeholder created

**Dependencies:** None

**Completed:** 2026-07-04

---

### Task 1.2: Event Bus & Schemas
**Status:** ✅ completed
**Estimated Effort:** 2 hours
**Description:** Implement in-process pub/sub event bus and TypedDict schemas for all event types.

**Acceptance Criteria:**
- [x] `events/bus.py` implements `publish()` and `subscribe()` functions
- [x] `events/schemas.py` defines all 9 event types as TypedDicts
- [x] `tests/test_bus.py` verifies publish/subscribe fan-out (14 tests)
- [x] `tests/test_schemas.py` validates schema construction (17 tests)
- [x] `tests/test_bus_integration_example.py` demonstrates full event flows (4 tests)
- [x] All 35 tests pass
- [x] Thread-safe implementation with stress test
- [x] Error handling for invalid events and callback exceptions

**Dependencies:** Task 1.1

**Completed:** 2026-07-04

---

### Task 1.3: Deterministic Intent Handler
**Status:** ✅ completed
**Estimated Effort:** 1.5 hours
**Description:** Create fixed lookup table for text intents (hi/bye/help) with canned responses.

**Acceptance Criteria:**
- [x] `decision_engine/intents.py` has `get_intent_response(text: str) -> str | None`
- [x] Handles at least 5 common intents (hi, bye, help, thanks, what can you do)
- [x] Case-insensitive, whitespace-normalized matching
- [x] Returns None for unknown intents (engine falls through to cache/LLM)
- [x] **Does NOT emit ACTION events** (that's gesture_actions.py in Task 1.4)
- [x] **Does NOT call motion planner or SafetyGate directly** (those are downstream components)
- [x] ~~Emits RESPONSE event with path="deterministic" for known intents~~ **Amended in Task 1.7:** Returns text only; Decision Engine publishes RESPONSE
- [x] `tests/decision_engine/test_intents.py` covers known/unknown intents (17 tests)
- [x] ~~Tests verify RESPONSE event is published for known intents~~ **Amended in Task 1.7:** Tests verify text return value; engine.py owns publishing
- [x] Tests verify None return for unknown intents (no event publishing at all)
- [x] Tests verify case-insensitivity and whitespace normalization

**Architecture Note:** Originally, `get_intent_response()` published RESPONSE events directly. During Task 1.7 implementation, this was corrected to follow proper separation of concerns: `intents.py` is now a pure function that returns text, and `decision_engine/engine.py` has sole responsibility for publishing RESPONSE events. This prevents double-publishing and ensures consistent path metadata across all response sources (deterministic/cache/llm).

**Dependencies:** Task 1.2

**Completed:** 2026-07-04

---

### Task 1.4: Gesture-Action Mapping
**Status:** ✅ completed
**Estimated Effort:** 1 hour
**Description:** Create fixed lookup table for gesture-to-action mapping.

**Acceptance Criteria:**
- [x] `decision_engine/gesture_actions.py` has `get_action(gesture: str) -> str | None`
- [x] Maps HAND_RAISED → HANDSHAKE
- [x] Extensible for future gestures (WAVE, THUMBS_UP, etc.)
- [x] Subscribes to GESTURE_DETECTED events and publishes ACTION events
- [x] **Does NOT call motion planner or SafetyGate directly** (downstream components)
- [x] Unknown gestures produce no ACTION event (safe no-op, not error)
- [x] `tests/decision_engine/test_gesture_actions.py` covers known/unknown gestures (17 tests)
- [x] Tests verify ACTION event is published for known gestures
- [x] Tests verify no ACTION event for unknown gestures (critical safety test)
- [x] Tests use synthetic GESTURE_DETECTED events (vision pipeline doesn't exist yet)

**Dependencies:** Task 1.2

**Completed:** 2026-07-04

---

### Task 1.5: SafetyGate Implementation
**Status:** ✅ completed
**Estimated Effort:** 2 hours
**Description:** Implement software safety layer for action execution with distance/sensor checks.

**Acceptance Criteria:**
- [x] `decision_engine/safety_gate.py` implements `safety_gate(action, distance_cm, sensor_ok) -> bool`
- [x] Blocks if `sensor_ok=False` (hard block, highest priority) - does NOT default to allow
- [x] Allows if `distance_cm=None` with logged warning (simulated phase)
- [x] Blocks if distance < 10cm or > 60cm (from config) - publishes ACTION_BLOCKED with reason
- [x] Allows if 10cm ≤ distance ≤ 60cm
- [x] `tests/decision_engine/test_safety_gate.py` covers all 5 cases + edge cases (19 tests)
- [x] Latency < 5ms (simple conditionals, no I/O) - measured <0.01ms average
- [x] **Does NOT call motion planner directly** (event-driven architecture)
- [x] Publishes ACTION_BLOCKED with correct reason field (sensor_fault, target_too_close, target_too_far)

**Dependencies:** Task 1.1

**Completed:** 2026-07-04

---

### Task 1.6: Session State Store
**Status:** pending
**Estimated Effort:** 2.5 hours
**Description:** Implement per-identity state machine (NEW/GREETED/AWAY/RETURNED) keyed by embedding_id.

**Acceptance Criteria:**
- [ ] `session_state/store.py` has `update_identity_state(embedding_id, event) -> str`
- [ ] Has `get_state(embedding_id) -> dict` accessor
- [ ] In-memory dict, no persistence needed
- [ ] State machine transitions: NEW→GREETED, GREETED→AWAY, AWAY→RETURNED
- [ ] `tests/session_state/test_store.py` walks full state machine
- [ ] Test confirms two different track_ids with same embedding_id share state

**Dependencies:** Task 1.2

---

### Task 1.7: Decision Engine Router
**Status:** pending
**Estimated Effort:** 3 hours
**Description:** Main router implementing 3-way branch (A: deterministic, B: cache, C: LLM).

**Acceptance Criteria:**
- [ ] `decision_engine/engine.py` subscribes to GESTURE_DETECTED and text input events
- [ ] Routes to Path A (intents/gesture_actions) for deterministic matches
- [ ] Routes to Path B (cache_manager) for questions with cache hits
- [ ] Routes to Path C (LangGraph) for cache misses
- [ ] Calls SafetyGate before emitting ACTION events
- [ ] Publishes SESSION_STATE events based on session store state
- [ ] `tests/decision_engine/test_engine.py` verifies correct path selection
- [ ] Test mocks LLM client, asserts zero calls for Paths A/B

**Dependencies:** Tasks 1.3, 1.4, 1.5, 1.6

---

### Task 1.8: Exact-Match Cache
**Status:** pending
**Estimated Effort:** 2 hours
**Description:** Hash-based cache for exact question text matches with data_version tagging.

**Acceptance Criteria:**
- [ ] `qa_cache/exact_cache.py` has `get(question) -> dict | None` and `put(question, answer, data_version)`
- [ ] Normalizes question text (lowercase, strip whitespace)
- [ ] Returns None if data_version doesn't match current version
- [ ] In-memory dict (pickle persistence optional for demo)
- [ ] `tests/qa_cache/test_exact_cache.py` tests exact match, normalization, version mismatch
- [ ] Latency < 5ms

**Dependencies:** Task 1.1

---

### Task 1.9: Entity Extractor
**Status:** pending
**Estimated Effort:** 3 hours
**Description:** Extract date/subject/person entities from questions for cache gating.

**Acceptance Criteria:**
- [ ] `qa_cache/entity_extractor.py` has `extract_entities(question) -> dict`
- [ ] Returns dict with keys: subject, person (both optional, None if not found)
- [ ] Subject extraction: regex for common topics (hod, library, canteen, placement, hostel, lab, etc.)
- [ ] Person extraction: capitalized words not in stopword list  
- [ ] `tests/qa_cache/test_entity_extractor.py` tests different subject/person extraction
- [ ] Returns None values (not errors) for missing entities
- [ ] No date extraction (no dateparser dependency) - all data is non-temporal

**Dependencies:** None (pure NLP, no other modules)

---

### Task 1.10: Semantic Cache
**Status:** pending
**Estimated Effort:** 3 hours
**Description:** FAISS-backed similarity search over question embeddings.

**Acceptance Criteria:**
- [ ] `qa_cache/semantic_cache.py` has `search(question_embedding, threshold) -> list[dict]`
- [ ] Uses sentence-transformers `all-MiniLM-L6-v2` (384-dim)
- [ ] FAISS IndexFlatIP (cosine similarity)
- [ ] Returns candidates above threshold (0.92 from config)
- [ ] Stores original question text + answer + data_version alongside embeddings
- [ ] `tests/qa_cache/test_semantic_cache.py` tests near-duplicate phrasing hits, unrelated misses
- [ ] Latency < 20ms on laptop

**Dependencies:** Task 1.1

---

### Task 1.11: Cache Manager (Orchestrator)
**Status:** pending
**Estimated Effort:** 2.5 hours
**Description:** Orchestrate exact → semantic → entity gate → miss flow.

**Acceptance Criteria:**
- [ ] `qa_cache/cache_manager.py` has `check_cache(question) -> dict | None`
- [ ] Has `write_cache(question, answer)` for write-back after LLM generation
- [ ] Checks exact cache first (fast path)
- [ ] On miss, embeds question and checks semantic cache
- [ ] On semantic candidate, extracts entities from both questions
- [ ] Returns hit only if entities match AND data_version matches
- [ ] `tests/qa_cache/test_cache_manager.py` includes critical regression test:
  - [ ] "Who is the HOD?" cached, then "Who is the placement officer?" asked → MISS (entity gate prevents wrong-person answer)
- [ ] Test also verifies old data_version treated as miss

**Dependencies:** Tasks 1.8, 1.9, 1.10

---

### Task 1.12: LLM Client
**Status:** pending
**Estimated Effort:** 2 hours
**Description:** Thin wrapper around Ollama API for local LLM calls.

**Acceptance Criteria:**
- [ ] `reasoning/llm_client.py` has `generate(prompt, context) -> str`
- [ ] Connects to Ollama on localhost:11434
- [ ] Uses Gemma3:1b or Llama3:1b (configurable)
- [ ] Timeout: 30s hard limit, raises TimeoutError
- [ ] Streaming support (returns generator)
- [ ] `tests/reasoning/test_llm_client.py` mocks Ollama endpoint
- [ ] Test verifies request shape and timeout behavior

**Dependencies:** Task 1.1

---

### Task 1.13: MCP Memory Server
**Status:** pending
**Estimated Effort:** 2.5 hours
**Description:** Single MCP tool for querying stored memories/facts.

**Acceptance Criteria:**
- [ ] `reasoning/mcp_memory_server.py` implements `query_memory(query: str) -> dict`
- [ ] Tool has LLM-readable docstring (one-line + Args/Returns)
- [ ] Reads from SQLite `data/memory.db` (simple key-value facts table)
- [ ] Returns `{"answer": str, "confidence": float}` or error dict
- [ ] Seed script creates memory.db with 10+ sample facts (HOD name, lab hours, etc.)
- [ ] `tests/reasoning/test_mcp_memory_server.py` tests valid query, timeout handling
- [ ] Test uses mocked DB for speed

**Dependencies:** Task 1.1

---

### Task 1.14: LangGraph Reasoning Graph
**Status:** pending
**Estimated Effort:** 3 hours
**Description:** Linear graph: retrieve → MCP tool → generate → cache write-back.

**Acceptance Criteria:**
- [ ] `reasoning/graph.py` defines LangGraph with 4 nodes: retrieve, tool_call, generate, write_cache
- [ ] Retrieve node: stub for now (will be vector search in Phase 5)
- [ ] Tool call node: conditionally calls MCP memory server
- [ ] Generate node: calls LLM client with context
- [ ] Write-cache node: calls cache_manager.write_cache()
- [ ] Timeout edge: 10s on tool_call → fallback message
- [ ] `tests/reasoning/test_graph.py` verifies full pass writes to cache
- [ ] Test verifies timeout triggers fallback, not hang

**Dependencies:** Tasks 1.11, 1.12, 1.13

---

## Phase 2: Voice I/O

### Task 2.1: Audio I/O
**Status:** pending
**Estimated Effort:** 2 hours
**Description:** Laptop mic/speaker capture using PyAudio.

**Acceptance Criteria:**
- [ ] `voice/audio_io.py` has `capture_audio() -> generator[bytes]` for mic
- [ ] Has `play_audio(audio_bytes)` for speaker
- [ ] 16kHz, mono, 16-bit PCM format
- [ ] Chunk size: 1024 frames
- [ ] Handles device selection (default mic/speaker)
- [ ] No dedicated test (covered by STT/TTS tests)

**Dependencies:** Task 1.1

---

### Task 2.2: Speech-to-Text (STT)
**Status:** pending
**Estimated Effort:** 3 hours
**Description:** Local STT using faster-whisper.

**Acceptance Criteria:**
- [ ] `voice/stt.py` has `transcribe_stream(audio_generator) -> str`
- [ ] Uses faster-whisper `base` model (CPU)
- [ ] Streaming transcription (chunk-based)
- [ ] Returns final transcript when silence detected (VAD)
- [ ] `tests/voice/test_stt.py` feeds short test audio clip
- [ ] Test asserts non-empty transcript and latency < 2s for 5s clip
- [ ] Not exact transcript matching (too flaky)

**Dependencies:** Task 2.1

---

### Task 2.3: Text-to-Speech (TTS)
**Status:** pending
**Estimated Effort:** 2.5 hours
**Description:** Local TTS using Piper.

**Acceptance Criteria:**
- [ ] `voice/tts.py` has `synthesize(text) -> bytes`
- [ ] Uses Piper with `en_US-lessac-medium` voice
- [ ] Streaming synthesis (start playback before full render)
- [ ] Returns audio bytes in same format as audio_io (16kHz mono PCM)
- [ ] `tests/voice/test_tts.py` synthesizes short text ("Hello world")
- [ ] Test asserts non-empty audio and first chunk latency < 500ms

**Dependencies:** Task 2.1

---

## Phase 3: Vision Pipeline

### Task 3.1: Video Capture
**Status:** pending
**Estimated Effort:** 1.5 hours
**Description:** Webcam capture with OpenCV, Pi camera swap ready.

**Acceptance Criteria:**
- [ ] `vision/capture.py` has `get_frame_generator() -> generator[np.ndarray]`
- [ ] Uses OpenCV `VideoCapture(0)` for laptop webcam
- [ ] Returns BGR frames at camera's native resolution
- [ ] Frame rate: as fast as camera provides (no throttling here, motion gate handles it)
- [ ] Interface documented for future Pi camera swap (same generator signature)
- [ ] No dedicated test (covered by bench_latency.py)

**Dependencies:** Task 1.1

---

### Task 3.2: Motion Gate
**Status:** pending
**Estimated Effort:** 2 hours
**Description:** Frame difference filter to skip YOLO on static frames.

**Acceptance Criteria:**
- [ ] `vision/motion_gate.py` has `has_motion(frame, prev_frame) -> bool`
- [ ] Grayscale conversion + absolute difference
- [ ] Threshold: mean diff > 5.0 (from config)
- [ ] Returns True if motion detected, False otherwise
- [ ] `tests/vision/test_motion_gate.py` uses synthetic frames (static vs. shifted)
- [ ] Test asserts latency < 5ms
- [ ] Test verifies True/False for motion/no-motion cases

**Dependencies:** Task 3.1

---

### Task 3.3: YOLO Pose Detector
**Status:** pending
**Estimated Effort:** 3 hours
**Description:** YOLOv8n-pose person detection with every-Kth-frame processing.

**Acceptance Criteria:**
- [ ] `vision/detector.py` has `detect_poses(frame) -> list[dict]`
- [ ] Loads YOLOv8n-pose from ultralytics
- [ ] Filters results: `cls == 0` (person only)
- [ ] Returns list of dicts: `{bbox, keypoints, confidence}`
- [ ] Keypoints: 17-point COCO format (nose, eyes, shoulders, elbows, wrists, hips, knees, ankles)
- [ ] `tests/vision/test_detector.py` mocks YOLO output
- [ ] Test asserts person-only filtering
- [ ] Actual inference covered by bench_latency.py

**Dependencies:** Task 1.1

---

### Task 3.4: ByteTrack Tracker
**Status:** pending
**Estimated Effort:** 3 hours
**Description:** Multi-person tracking with stable IDs across frames.

**Acceptance Criteria:**
- [ ] `vision/tracker.py` has `update(detections) -> list[dict]`
- [ ] Uses ByteTrack algorithm
- [ ] Returns list of tracked objects: `{track_id, bbox, keypoints}`
- [ ] Maintains stable track_id across occlusion (up to 30 frames)
- [ ] New detections get new track_ids
- [ ] Emits TRACK_LOST event when track disappears for >30 frames
- [ ] `tests/vision/test_tracker.py` feeds sequence of detections
- [ ] Test asserts stable IDs and re-identification after brief occlusion
- [ ] Test asserts latency < 5ms per update

**Dependencies:** Task 3.3

---

### Task 3.5: Gesture Recognition
**Status:** pending
**Estimated Effort:** 2 hours
**Description:** Pure geometry check for HAND_RAISED gesture.

**Acceptance Criteria:**
- [ ] `vision/gesture.py` has `check_gesture(keypoints) -> str | None`
- [ ] HAND_RAISED: wrist_y < shoulder_y (either wrist)
- [ ] Returns "HAND_RAISED" or None
- [ ] Publishes GESTURE_DETECTED event to bus
- [ ] `tests/vision/test_gesture.py` uses synthetic keypoints
- [ ] Test covers: wrist above shoulder, wrist below shoulder, wrist equal
- [ ] Test asserts latency < 1ms (pure arithmetic)

**Dependencies:** Task 3.4

---

### Task 3.6: Face Identification
**Status:** pending
**Estimated Effort:** 4 hours
**Description:** Face embedding + FAISS matching, only on new track_ids.

**Acceptance Criteria:**
- [ ] `vision/face_id.py` has `identify_face(frame, bbox, track_id) -> dict`
- [ ] Uses InsightFace buffalo_s for embeddings
- [ ] FAISS IndexFlatL2 for known faces (starts empty)
- [ ] Only runs if track_id not seen before (cache track_ids in memory)
- [ ] On match (distance < 0.6): returns `{embedding_id, status="known", name, confidence}`
- [ ] On no match: generates new embedding_id, adds to FAISS, returns `{embedding_id, status="new"}`
- [ ] Publishes IDENTITY_RESOLVED event
- [ ] On track lost: publishes TRACK_LOST event (calls session_state.update_identity_state)
- [ ] `tests/vision/test_face_id.py` tests same face twice → match, new face → register
- [ ] Test asserts latency < 200ms (one-time cost per identity)

**Dependencies:** Tasks 1.6, 3.4

---

### Task 3.7: Vision Pipeline Integration
**Status:** pending
**Estimated Effort:** 2.5 hours
**Description:** Wire all 5 vision stages into a single processing loop.

**Acceptance Criteria:**
- [ ] Main vision loop in `vision/capture.py` or new `vision/pipeline.py`
- [ ] Flow: frame → motion_gate → (if motion) YOLO every Kth frame → tracker every frame → gesture → face_id (new tracks only)
- [ ] Publishes events: GESTURE_DETECTED, IDENTITY_RESOLVED, TRACK_LOST
- [ ] Runs in separate thread/async task (non-blocking)
- [ ] No test (covered by integration tests)

**Dependencies:** Tasks 3.2, 3.3, 3.4, 3.5, 3.6

---

### Task 3.8: Vision Latency Benchmark
**Status:** pending
**Estimated Effort:** 3 hours
**Description:** Measure per-stage latency on recorded test video.

**Acceptance Criteria:**
- [ ] `tests/vision/bench_latency.py` runs full cascade on 60s test video
- [ ] Logs p50/p95 for: motion_gate, YOLO, tracker, gesture, face_id
- [ ] Outputs CSV with per-frame timings
- [ ] Fails build if any stage's p95 > laptop budget (Section 8 of design)
- [ ] Test video: 1-2 people, hand raise, face clearly visible

**Dependencies:** Task 3.7

---

## Phase 4: Integration

### Task 4.1: E2E Gesture Handshake Test
**Status:** pending
**Estimated Effort:** 2 hours
**Description:** End-to-end test of gesture → action flow with zero LLM calls.

**Acceptance Criteria:**
- [ ] `tests/integration/test_e2e_gesture_handshake.py` creates synthetic GESTURE_DETECTED event
- [ ] Publishes event to bus, asserts Decision Engine emits ACTION event
- [ ] Asserts SafetyGate passes (distance_cm=None in simulated phase)
- [ ] Asserts ACTION event logged (no actual servo movement)
- [ ] Mocks LLM client, asserts zero calls (Path A, deterministic)
- [ ] Test runs in <100ms

**Dependencies:** Tasks 1.7, 1.5

---

### Task 4.2: E2E Greeting Flow Test
**Status:** pending
**Estimated Effort:** 2.5 hours
**Description:** Test identity state machine through full cycle.

**Acceptance Criteria:**
- [ ] `tests/integration/test_e2e_greeting_flow.py` simulates new face detection
- [ ] Publishes IDENTITY_RESOLVED (status="new")
- [ ] Asserts session state transitions: NEW → GREETED
- [ ] Asserts greeting message generated (generic, no name)
- [ ] Simulates TRACK_LOST → asserts AWAY state
- [ ] Simulates re-detection → asserts RETURNED state
- [ ] Asserts "welcome back" message, NOT a new greeting
- [ ] Verifies two different track_ids with same embedding_id share state

**Dependencies:** Tasks 1.7, 1.6

---

### Task 4.3: E2E Cache Hit Test
**Status:** pending
**Estimated Effort:** 2.5 hours
**Description:** Test question caching with exact, semantic, and entity-gated hits.

**Acceptance Criteria:**
- [ ] `tests/integration/test_e2e_repeated_question_cache.py` asks novel question
- [ ] Asserts LLM called (Path C)
- [ ] Asks exact same question → asserts cache hit, zero additional LLM calls
- [ ] Asks paraphrase → asserts semantic cache hit
- [ ] **Critical regression:** asks "Who is the HOD?", then "Who is the placement officer?"
  - [ ] Asserts both answered separately (no cache collision)
  - [ ] Asserts entity gate prevented wrong-person cache hit (semantically similar but different person)
- [ ] All cache hits < 35ms

**Dependencies:** Tasks 1.7, 1.11, 1.14

---

### Task 4.4: E2E Latency Budget Test
**Status:** pending
**Estimated Effort:** 3 hours
**Description:** Run full pipeline N times, validate every stage within budget.

**Acceptance Criteria:**
- [ ] `tests/integration/test_e2e_latency_budget.py` runs 50 iterations
- [ ] Measures: Path A, Path B (exact), Path B (semantic), Path C, SafetyGate, vision stages
- [ ] Calculates p50/p95 for each stage
- [ ] Asserts p95 ≤ laptop targets from design Section 8
- [ ] Outputs CSV with full timing breakdown
- [ ] Fails build if any stage violates budget

**Dependencies:** Tasks 1.7, 1.11, 1.14, 3.7

---

### Task 4.5: Main Application Entry Point
**Status:** pending
**Estimated Effort:** 2 hours
**Description:** Wire all modules into runnable application.

**Acceptance Criteria:**
- [ ] `main.py` initializes all modules (vision, voice, decision engine, cache, LLM)
- [ ] Starts vision pipeline in background thread
- [ ] Starts voice input loop (STT)
- [ ] Decision engine subscribes to all events
- [ ] **Main loop calls `session_state.check_timeouts()` ~1x/second** (Task 1.6 requirement)
- [ ] **Main loop calls `exact_cache.reload_data_version()` ~1x/minute** (Task 1.8 requirement)
- [ ] Graceful shutdown on Ctrl+C
- [ ] Logs key events to console (IDENTITY_RESOLVED, ACTION, cache hits/misses)
- [ ] No test (manual demo script validates this)

**Critical Notes:**
- `check_timeouts()`: Enforces 5-second greeting timeout (NEW → GREETED if TTS fails)
- `reload_data_version()`: Detects CrewAI nightly refresh file updates (invalidates stale cache)
- Without these periodic calls, greeting timeout and cache staleness won't work correctly

**Dependencies:** Tasks 1.7, 2.2, 2.3, 3.7

---

### Task 4.6: Manual Demo Script
**Status:** pending
**Estimated Effort:** 3 hours
**Description:** Walkthrough demo covering all major flows.

**Acceptance Criteria:**
- [ ] Demo script documented in README.md
- [ ] Steps:
  1. Sit in frame (unknown face) → robot greets generically
  2. Raise hand → "HANDSHAKE" action logged
  3. Leave frame → AWAY state
  4. Re-enter frame → "welcome back" message
  5. Ask novel question → answered via LLM (1-3s)
  6. Ask same question → instant cache hit
  7. Ask today/yesterday pair → both answered fresh
- [ ] Run 5 times consecutively without failure
- [ ] All flows logged clearly in console

**Dependencies:** Task 4.5

---

### Task 4.7: README Documentation
**Status:** pending
**Estimated Effort:** 2 hours
**Description:** Complete user-facing documentation.

**Acceptance Criteria:**
- [ ] README.md includes:
  - [ ] Project description (one paragraph)
  - [ ] How to install dependencies (`pip install -r requirements.txt`)
  - [ ] How to download models (YOLO, InsightFace, Ollama)
  - [ ] How to run (`python main.py`)
  - [ ] How to add a known face (SQLite insert + FAISS add, with example SQL)
  - [ ] How to reset caches (delete files, bump data_version)
  - [ ] Manual demo script
  - [ ] Section 10 scope notes (biometric consent, authz assumption, multi-person limits)
  - [ ] Latency budget table
  - [ ] Known limitations (Section 10)
  - [ ] Future work (Pi migration, MQTT, real servos)

**Dependencies:** Task 4.6

---

### Task 4.8: Requirements Freeze
**Status:** pending
**Estimated Effort:** 0.5 hours
**Description:** Lock dependency versions after all tests pass.

**Acceptance Criteria:**
- [ ] All tests passing on development machine
- [ ] Run `pip freeze > requirements.txt`
- [ ] Verify clean install in fresh venv: `pip install -r requirements.txt && pytest`
- [ ] Commit frozen requirements.txt

**Dependencies:** Task 4.4

---

## Phase 5: Pi Migration (Deferred)

### Task 5.1: Pi Camera Integration
**Status:** deferred
**Description:** Swap webcam for Pi Camera Module 3, same interface.

---

### Task 5.2: HC-SR04 Distance Sensor
**Status:** deferred
**Description:** Wire ultrasonic sensor to GPIO, integrate with SafetyGate.

---

### Task 5.3: Motion Planner with Real Servos
**Status:** deferred
**Description:** Drive actual servos with preset angles, real-time thread priority.

---

### Task 5.4: Hardware E-stop Wiring
**Status:** deferred
**Description:** Physical button in servo power line (wiring task, not code).

---

### Task 5.5: MQTT Transport Layer
**Status:** deferred
**Description:** Replace in-process bus with MQTT broker for laptop ↔ Pi communication.

---

## Phase 6: Optimization (Deferred)

### Task 6.1: CrewAI Nightly Refresh Job
**Status:** deferred
**Description:** Offline job to refresh vector DB and bump data_version.

---

### Task 6.2: Cloud LLM Migration (If Needed)
**Status:** deferred
**Description:** Move LLM to cloud API if Pi 5 CPU insufficient for target latency.

---

### Task 6.3: Cloud STT/TTS Migration (If Needed)
**Status:** deferred
**Description:** Move voice processing to cloud if Pi 5 CPU committed to vision.

---

## Summary

**Total Tasks:** 43 (28 current phase, 15 deferred)
**Estimated Effort (Current Phase):** ~60-70 hours
**Critical Path:** 1.1 → 1.2 → 1.7 → 3.7 → 4.5 → 4.6

**Phases:**
1. Core Infrastructure (14 tasks, ~32 hours)
2. Voice I/O (3 tasks, ~7.5 hours)
3. Vision Pipeline (8 tasks, ~21 hours)
4. Integration (8 tasks, ~17.5 hours)
5. Pi Migration (5 tasks, deferred)
6. Optimization (3 tasks, deferred)

**Next Action:** Start with Task 1.1 (Project Setup & Configuration)
