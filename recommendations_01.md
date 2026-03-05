# Phoenix — AI Travel Companion (Technical Design Doc)

> Goal: Build **Phoenix**, an AI travel companion that captures traveler “vibe” in seconds, generates **numbered (max 5 visible)** route options, supports **voice-corrected navigation**, provides **guided tour explanations**, and offers **multilingual real-world translation**. Preferences persist as a **Knowledge Graph** and update automatically based on user feedback (“tired of churches”) and live events.

---

## 1) System Overview

### Core capabilities

* **Smart Chat & Interest Capture** (voice/text): Extract age group, occupation, hobbies, food/art/history interests, crowd tolerance, walk duration, etc.
* **Personalized Route Planning**: Combine user profile + travel history + live sources (Reddit/forum snippets, Maps reviews).
* **Interactive Route Adjustment**: Voice/text commands to add/remove/swap POIs. **Keep suggestions numbered**, always show **<= 5 visible options**.
* **Guided Tour Mode**: Location-aware “pings”, 20s audio bites, tap POI for deeper info, interruptible Q&A.
* **Multilingual Companion**: Chinese, English, Japanese, Korean, Hindi, French. Speechmatics for STT + translation.
* **“Real-world impact” translation**: Traveler asks local in local language → Phoenix instantly translates to English, explains answer.
* **Mock actions**: “book table” / “hail ride” via mock APIs with **confirmed** state.
* **RAG pipeline**: Mix Blackboard profile + vector store (pgvector) + live web data.

---

## 2) High-Level Architecture

### Components

* **Client apps** (mobile/web):

  * LiveKit audio room (bi-directional)
  * Map view + itinerary panel
  * Route options list (max 5 visible)
  * Push notifications / in-app alerts (near POI, route updates)
* **Phoenix API (Python / FastAPI)**:

  * Session orchestration
  * LangGraph state machines
  * Routing & itinerary engine
  * POI knowledge + RAG
  * LiveKit webhooks + token service
* **Speech layer**:

  * **LiveKit** for real-time streaming (VAD gating, partial transcripts)
  * **Speechmatics** for STT, diarization, translation (and optionally timestamps)
  * **TTS** (e.g., ElevenLabs) for guided narration (streamed back via LiveKit)
* **Memory & data**:

  * **PostgreSQL 18 + asyncpg + pgvector**: events, sessions, routes, embeddings
  * **Neo4j**: persistent **Knowledge Graph** for dynamic preferences
  * **Redis**: session cache, rate limiting, ephemeral context, live itinerary state
* **External sources**:

  * **Tavily / SerpAPI**: web search
  * Reddit ingestion (API or scraping) for last 24h “hidden gems”
  * Google Maps via **Composio MCP** (mcp-config-ejbf90): POIs, reviews, directions, timeline signals (where permitted)
* **Blackboard** (your “Backboard/Blackboard”):

  * Central profile store + preference update service
  * Emits events into LangGraph (preference changed → replan)

### Mermaid: System diagram

```mermaid
flowchart LR
  subgraph Client
    UI[Mobile/Web UI\nMap + Planner + Chat]
    LK[LiveKit SDK\nAudio Room]
  end

  subgraph PhoenixAPI[Phoenix API (FastAPI)]
    ORCH[LangGraph Orchestrator]
    RAG[RAG + Tools Router]
    ROUTE[Itinerary + Routing Engine]
    ACT[Mock Actions\nBook/Ride]
  end

  subgraph Speech
    SM[Speechmatics\nSTT + VAD + Diarization + Translation]
    TTS[TTS (ElevenLabs)\nStreaming Audio]
  end

  subgraph Data
    PG[(PostgreSQL 18\nasyncpg + pgvector)]
    N4J[(Neo4j\nKnowledge Graph)]
    RD[(Redis\nSession/Cache)]
    BB[Blackboard\nProfile + Events]
  end

  subgraph External
    GM[Google Maps (MCP)\nPOIs + Directions + Reviews]
    WEB[Tavily/SerpAPI\nSearch + Forums/Reddit]
    TL[Travel History\nTimeline/Logs]
  end

  UI -->|REST/WebSocket| PhoenixAPI
  LK <--> PhoenixAPI
  LK -->|Audio stream| SM
  SM -->|partials + final\ntranscripts| PhoenixAPI
  PhoenixAPI -->|TTS text| TTS
  TTS -->|audio stream| LK

  ORCH --> RAG
  ORCH --> ROUTE
  ORCH --> ACT

  RAG <--> PG
  RAG <--> WEB
  ROUTE <--> GM
  ROUTE <--> PG
  ORCH <--> RD
  BB <--> N4J
  ORCH <--> BB
  TL --> ORCH
```

---

## 3) Repository Layout (Required)

```
phoenix/
  README.md
  pyproject.toml
  src/
    phoenix/
      __init__.py
      api/
        main.py
        routes/
          chat.py
          itinerary.py
          livekit.py
          actions.py
          health.py
        schemas/
          requests.py
          responses.py
      core/
        config.py
        logging.py
        security.py
        errors.py
        utils.py
      graph/
        state.py
        graphs/
          vibe_capture.py
          itinerary_planner.py
          guided_tour.py
          translation_companion.py
          replanner.py
        nodes/
          stt_ingest.py
          entity_extract.py
          preference_update.py
          travel_history.py
          web_retrieval.py
          poi_retrieval.py
          route_optimize.py
          narration.py
          action_mock.py
        tools/
          maps_tool.py
          search_tool.py
          reddit_tool.py
          blackboard_tool.py
      memory/
        pg/
          models.py
          repo.py
          migrations/
        neo4j/
          driver.py
          kg_repo.py
          ontology.py
        redis/
          client.py
          session_cache.py
      speech/
        livekit_client.py
        speechmatics_client.py
        vad.py
        diarization.py
        tts_client.py
      rag/
        embedder.py
        vector_store.py
        retriever.py
        ranker.py
      routing/
        itinerary.py
        constraints.py
        directions.py
        scoring.py
      monitoring/
        metrics.py
        tracing.py
  tests/
    test_api_chat.py
    test_itinerary_planning.py
    test_replanning.py
    test_rag_retrieval.py
    test_kg_updates.py
    test_translation_flow.py
  docs/
    architecture.md
    api.md
    database.md
    langgraph.md
    speech.md
```

---

## 4) Execution Workflows

## 4.1 Phase 1 — “Vibe Capture” (30 seconds, no onboarding form)

**Prompt**:

> “Hey, I’m Phoenix. I see we’re in Paris. In 30 seconds, tell me what mood you’re in and what you’re craving.”

### Steps

1. LiveKit opens audio room; client streams microphone.
2. VAD gates audio chunks (reduce cost + latency).
3. Speechmatics returns partial and final transcript with timestamps; diarization if multiple speakers.
4. Entity extraction node runs:

   * preferences: “art lover”, “hungry”, “hates crowds”
   * constraints: “2-hour walk”, “budget”, “avoid stairs”
   * language preference + speech rate
5. Blackboard update:

   * store as graph facts (nodes + edges) with weights + recency.
6. Phoenix replies with a short summary + first route options.

### Mermaid: Vibe Capture graph

```mermaid
stateDiagram-v2
  [*] --> Listen
  Listen --> STT: audio frames
  STT --> Extract: transcript (partial/final)
  Extract --> UpdateKG: entities/preferences
  UpdateKG --> Confirm: "Got it..." + ask 1 follow-up max
  Confirm --> [*]
```

---

## 4.2 Phase 2 — “Social-Live Itinerary” (Hidden gems + recent chatter)

### Input signals

* Blackboard preferences (KG)
* Recent travel history (Maps Timeline / travel logs)
* Live web results (Tavily/SerpAPI) + Reddit/forum posts from last 24h
* POI popularity signals (Maps reviews, ratings)
* Real-time constraints: opening hours, weather (optional), crowds (if available)

### Steps

1. Retrieve candidate POIs:

   * Google Maps “nearby search”
   * web/reddit “hidden gem” mentions in last 24h
2. Filter & score:

   * match to preferences (KG)
   * exclude “tired of X” categories
   * time & distance constraints (walk duration)
3. Generate **<= 5 numbered route options**.
4. Each route option has:

   * start/end
   * POI list in order
   * estimated walk time + transit legs
   * “why it matches you” (1–2 lines)

### Important UI rule (voice-friendly)

* Always render options like:

  1. …
  2. …
  3. …
* Keep only 5 visible; “More options” is a separate action.

---

## 4.3 Phase 3 — Guided Tour Mode (location-aware + interruptible)

### Key behaviors

* When user confirms a route:

  * Phoenix creates a tour session and publishes to Redis (live state)
  * Client receives map polyline + POI markers + step-by-step planner
* During walk:

  * If user near POI → Phoenix “pings” with an audio bite (20 seconds)
  * User can interrupt anytime (“Phoenix, what’s that statue on my left?”)
  * Phoenix uses GPS coordinate + maps place lookup + RAG to answer
* Route updates:

  * if the user removes a POI or a new event appears → auto-replan and notify

### Mermaid: Guided Tour flow

```mermaid
sequenceDiagram
  participant U as User
  participant C as Client
  participant LK as LiveKit
  participant P as Phoenix API
  participant GM as Google Maps (MCP)
  participant DB as PG/Redis
  participant KG as Neo4j/Blackboard

  U->>C: Confirm Route #2
  C->>P: POST /itinerary/confirm
  P->>DB: persist itinerary + set live state
  P->>C: return map polyline + planner

  loop Walking
    C->>P: location update
    P->>DB: update last_position
    P->>GM: nearby/poi lookup (if near marker)
    P->>P: generate 20s audio bite
    P->>LK: stream TTS audio
    U->>LK: "What's that statue?"
    LK->>P: transcript event
    P->>GM: reverse place / nearest landmark
    P->>KG: read preferences + avoid list
    P->>LK: answer (interruptible)
  end
```

---

## 5) LangGraph Design

Phoenix is best modeled as **multiple specialized graphs** with a shared state schema and an event bus.

### 5.1 Shared State (Pydantic)

A single `PhoenixState` (stored per session in Redis + checkpointed in Postgres) holds:

* session metadata (user_id, locale, city, device)
* transcript buffers + turn history
* extracted entities + confidence
* active itinerary + route alternatives
* live location + proximity triggers
* tool outputs (maps, web snippets)
* action statuses (booking/ride confirmed)

### 5.2 Graphs

1. **VibeCaptureGraph**

   * Nodes: `stt_ingest → entity_extract → preference_update → response_compose`
2. **ItineraryPlannerGraph**

   * Nodes: `travel_history_fetch → web_retrieval → poi_retrieval → route_optimize → render_options`
3. **ReplannerGraph**

   * Triggered when:

     * user edits POIs
     * preference changes in KG
     * external events change (closures, time constraints)
4. **GuidedTourGraph**

   * Nodes: `proximity_check → narration → interrupt_qa → update_state`
5. **TranslationCompanionGraph**

   * Bidirectional translation:

     * Traveler language ↔ local language ↔ traveler explanation

### Mermaid: ItineraryPlannerGraph (simplified)

```mermaid
flowchart TD
  A[Start: Need route] --> B[Load KG Preferences]
  B --> C[Fetch Travel History]
  C --> D[Retrieve Live Web/Reddit]
  D --> E[Google Maps POI Search]
  E --> F[Filter + Score Candidates]
  F --> G[Build 1..N Routes]
  G --> H[Render <= 5 Numbered Options]
  H --> I[Await User Selection or Edit]
```

---

## 6) Speech Layer Best Practices (LiveKit + Speechmatics + TTS)

### 6.1 LiveKit (real-time transport)

* Use LiveKit rooms for:

  * microphone uplink
  * TTS downlink (Phoenix voice)
  * data messages (transcript partials, route updates, “ping” events)
* Keep latency low by:

  * sending partial transcripts to UI quickly
  * only final transcripts trigger heavy LLM steps
* Use room metadata for:

  * `user_id`, `session_id`, `language`, `city`

### 6.2 VAD (Voice Activity Detection)

* Apply VAD before STT:

  * reduces Speechmatics cost
  * improves responsiveness
* Policy:

  * Start STT stream on speech start
  * End chunk after N ms of silence
  * Keep a rolling buffer for barge-in (interrupt)

### 6.3 Diarization

* Enable diarization when:

  * multiple speakers detected (traveler + local)
  * translation mode (ask local a question)
* Store diarization segments so Phoenix can:

  * label who spoke
  * translate only “local speaker” into English explanation

### 6.4 Translation mode (Speechmatics)

* Flow:

  1. traveler speaks question (English) → translate to local language text
  2. optional: speak translated question via TTS to the local (device speaker)
  3. local answers → Speechmatics STT + diarization → translate to English
  4. Phoenix explains answer to traveler (contextual + cultural notes)

### 6.5 TTS (ElevenLabs)

* Stream TTS audio back through LiveKit
* Short “audio bites” (guided tour) must be:

  * < 20 seconds by design
  * conversational, 1–2 facts max unless user asks follow-up
* Support “barge-in”:

  * if user speaks, stop TTS stream immediately

---

## 7) Data Model

## 7.1 PostgreSQL (asyncpg + pgvector)

### Purpose

* Durable store for sessions, transcripts, itineraries, POIs, embeddings, tool outputs, action confirmations.

### ER Diagram (Postgres)

```mermaid
erDiagram
  users ||--o{ sessions : has
  sessions ||--o{ messages : contains
  sessions ||--o{ itineraries : produces
  itineraries ||--o{ itinerary_items : includes
  pois ||--o{ itinerary_items : references
  messages ||--o{ embeddings : has
  documents ||--o{ embeddings : has
  itineraries ||--o{ route_options : offers
  route_options ||--o{ route_legs : contains
  actions ||--o{ action_events : logs

  users {
    uuid id PK
    text display_name
    text preferred_language
    timestamptz created_at
  }

  sessions {
    uuid id PK
    uuid user_id FK
    text city
    text country
    text locale
    timestamptz started_at
    timestamptz ended_at
  }

  messages {
    uuid id PK
    uuid session_id FK
    text role
    text content
    jsonb meta
    timestamptz created_at
  }

  documents {
    uuid id PK
    text source
    text title
    text url
    jsonb meta
    timestamptz fetched_at
  }

  embeddings {
    uuid id PK
    uuid message_id FK
    uuid document_id FK
    vector embedding
    text model
    timestamptz created_at
  }

  pois {
    uuid id PK
    text provider
    text provider_place_id
    text name
    text category
    double precision lat
    double precision lon
    jsonb details
  }

  itineraries {
    uuid id PK
    uuid session_id FK
    text status
    interval planned_duration
    jsonb constraints
    timestamptz created_at
  }

  route_options {
    uuid id PK
    uuid itinerary_id FK
    int option_number
    text summary
    int est_minutes
    jsonb polyline
    jsonb scoring
  }

  route_legs {
    uuid id PK
    uuid route_option_id FK
    int leg_index
    text mode
    int est_minutes
    jsonb directions
  }

  itinerary_items {
    uuid id PK
    uuid itinerary_id FK
    uuid poi_id FK
    int sort_order
    text notes
  }

  actions {
    uuid id PK
    uuid session_id FK
    text action_type
    text status
    jsonb request
    jsonb response
    timestamptz created_at
  }

  action_events {
    uuid id PK
    uuid action_id FK
    text event_type
    jsonb payload
    timestamptz created_at
  }
```

### Indexing essentials

* `embeddings.embedding` → `ivfflat` / `hnsw` index (pgvector)
* `(pois.provider, pois.provider_place_id)` unique index
* `route_options(itinerary_id, option_number)` unique index
* `messages(session_id, created_at)` for chat replay

---

## 7.2 Neo4j Knowledge Graph (Persistent “Dynamic Preferences”)

### Why Neo4j

You want preference updates like:

* “I’m tired of churches”
* “More street food”
* “Avoid crowds”
  to instantly reweight the planning engine and persist across trips.

### KG Ontology (conceptual)

* **User** node
* **Preference** nodes (category-based: FOOD, ART, HISTORY, CROWD, WALK_PACE, BUDGET)
* **Entity** nodes (e.g., “Church”, “Coffee shop”, “Neo-Expressionism”)
* Relationships:

  * `(User)-[:LIKES {weight, updated_at}]->(Entity)`
  * `(User)-[:DISLIKES {weight, updated_at}]->(Entity)`
  * `(User)-[:PREFERS {value, updated_at}]->(Preference)`
  * `(User)-[:VISITED]->(POI)` optionally mirrored from Postgres

### Mermaid: KG snippet

```mermaid
graph TD
  U[User] -->|LIKES +0.8| E1[Modern Art]
  U -->|LIKES +0.6| E2[Coffee Shops]
  U -->|DISLIKES +0.9| E3[Churches]
  U -->|PREFERS| P1[Low Crowds]
  U -->|PREFERS| P2[2-hour Walk]
```

### Preference update rule (example)

If user says “I’m tired of churches”:

* Add or increase `DISLIKES(Churches)` with high weight + recent timestamp
* Add a short-lived session override in Redis (“avoid churches for next 4 hours”) to prevent oscillations
* Trigger **ReplannerGraph** to swap next cathedral for coffee shop automatically

---

## 7.3 Redis

Use Redis for:

* Session state snapshots (LangGraph checkpoints)
* Live itinerary state (current POI index, last GPS, last ping time)
* Rate limiting / dedupe (avoid repeated proximity pings)
* Temporary preference overrides (“tired of X for this afternoon”)

---

## 8) RAG Pipeline

### Retrieval sources

* **User KG preferences** (Neo4j)
* **Recent trip context** (Postgres messages + travel history)
* **POI documents** (Maps details, reviews)
* **Web snippets** (Tavily/SerpAPI) + Reddit/forum excerpts

### Pipeline

1. **Query builder**:

   * turns user intent + KG facts into retrieval queries
2. **Hybrid retrieval**:

   * Vector similarity (pgvector) over documents/reviews
   * Keyword retrieval for exact terms (names/addresses)
3. **Reranking** (optional if available through providers):

   * keep top K contexts (small, focused)
4. **Answer composer**:

   * short guided narration or detailed explanation depending on mode
   * include “why recommended” tied back to preferences

### Guidance for “hidden gems” freshness

* Web retrieval node must apply recency filters (last 24h where possible)
* Store fetched snippets in `documents` with `fetched_at`
* Prefer diverse sources and dedupe near-identical snippets

---

## 9) Route Planning & Map Output Requirements

### Must output:

* **Map representation**:

  * Polyline for chosen route option
  * POI markers with numbers
* **Planner**:

  * Step-by-step legs: walk/transit
  * ETA + distance
  * “How to get from A to B” instructions (from Maps directions API)

### Constraints engine

* Hard constraints:

  * maximum duration
  * opening hours (when available)
  * avoid categories (churches)
* Soft preferences:

  * food vs art weighting
  * crowd tolerance
  * pace

### Recommendation visibility rule

* Always show <= 5 options at once.
* Provide “Show more” to paginate or regenerate.

---

## 10) Mock Actions (Book table / Hail ride)

### Design goals

* Don’t just say “I can book it” — show a **confirmed** state.

### API behavior

* `POST /actions/book_table`
* `POST /actions/hail_ride`
* Each action:

  * writes row to `actions`
  * appends events to `action_events`
  * returns a structured response:

    * `status: confirmed`
    * `confirmation_code`
    * `eta` (ride)
    * `reservation_time` (table)

### Mermaid: Action state

```mermaid
stateDiagram-v2
  [*] --> Requested
  Requested --> Confirmed: mock provider OK
  Requested --> Failed: mock provider error
  Confirmed --> [*]
  Failed --> [*]
```

---

## 11) API Surface (FastAPI)

### Core endpoints

* `POST /chat` — message turn (text) + optional context; returns assistant response + UI directives
* `POST /speech/events` — transcript events from Speechmatics / LiveKit data channel
* `POST /itinerary/options` — generate route options (<= 5 returned)
* `POST /itinerary/confirm` — confirm selected option
* `POST /itinerary/edit` — add/remove/swap POIs (voice friendly)
* `POST /location/update` — streaming GPS updates
* `POST /translation/ask-local` — translation companion mode
* `POST /actions/book_table` — mock booking
* `POST /actions/hail_ride` — mock ride
* `GET /health` — liveness/readiness

### Response “UI directives”

Every response can include:

* `spoken_text` (for TTS)
* `map_polyline`, `markers`
* `route_options` (numbered, max 5)
* `notifications` (replan occurred, near POI ping)

---

## 12) Observability & Reliability

### Logging (Loguru)

* Correlation IDs: `session_id`, `request_id`
* Structured logs for:

  * tool calls (maps/web)
  * STT/TTS latencies
  * replans + reason

### Metrics

* TTFT for:

  * partial transcript
  * first assistant token
  * first TTS audio frame
* Replan frequency
* VAD hit rate / false triggers
* Tool failure rates

### Failure handling

* Tool timeouts must degrade gracefully:

  * If web retrieval fails → use Maps-only + stored docs
  * If Maps directions fail → fallback to straight-line ordering + warn user
  * If STT partial fails → switch to text input

---

## 13) Testing Strategy (Required)

### Test layers

1. **Unit tests**

   * KG update rules: “tired of churches” swaps POIs category
   * scoring function determinism
   * route option formatting (<= 5; numbered)
2. **Integration tests**

   * Postgres repositories (async)
   * Neo4j KG read/write
   * Redis state checkpointing
3. **API tests**

   * itinerary generation/confirm/edit flows
   * translation flow: traveler→local→traveler
4. **LangGraph tests**

   * state transitions (replanner triggers on preference change)

### Test principles

* Deterministic fixtures for web/maps tool outputs (recorded stubs)
* No external calls in CI: mock tools at the boundary
* Validate Pydantic models for every API request/response

---

## 14) Security & Privacy Notes

* Treat API keys as secrets (env vars only).
* Store only necessary audio metadata; avoid storing raw audio unless user opts in.
* Travel history ingestion should be explicit + permissioned.
* Provide a “Forget this preference” and “Clear trip memory” workflow:

  * delete from Postgres (messages/documents)
  * remove from Neo4j edges for that user
  * clear Redis session keys

---

## 15) Environment Configuration

### Database

* PostgreSQL 18 (asyncpg)
* `DATABASE_URL=postgresql+asyncpg://ai_travel_companion:trainer@localhost:5432/ai_travel_companion`

### Keys (already available)

* LIVEKIT_API_KEY, SPEECHMATICS_API_KEY, BACKBOARD_API_KEY
* OPENAI_API_KEY, GEMINI_API_KEY, DEEPSEEK_API_KEY, GLM_API_KEY
* TAVILY_API_KEY, SERPAPI_API_KEY, ELEVENLABS_API_KEY
* COHERE_API_KEY, VOYAGE_API_KEY
* MCP Google Maps: `mcp-config-ejbf90`

### LLM provider policy

Use only:

* OpenAI: `gpt-4o-mini`, `gpt-4o`
* Anthropic: `claude-sonnet-4.5`, `claude-haiku-4-5`
* Google: `gemini-2.5-flash`, `gemini-2.5-pro`
* DeepSeek: `deepseek-chat`, `deepseek-reasoner`
* Zhipu: `GLM-4.5`

---

## 16) Concrete “Phoenix Behaviors” (Acceptance Criteria)

1. **Vibe capture** completes with a single voice prompt and produces KG updates.
2. Route options:

   * always **numbered**
   * show **<= 5 options**
   * user can say “remove option 3” or “pick 2”
3. “Tired of churches”:

   * immediately updates KG
   * triggers auto-swap to coffee shop
   * replan is communicated to user
4. Guided mode:

   * proximity ping triggers a short audio bite
   * user can interrupt and ask about surroundings
5. Translation companion:

   * traveler asks local question
   * Phoenix translates to local language quickly
   * local answer translated to English + explained
6. Mock actions:

   * booking and ride show **confirmed** state stored in Postgres

---