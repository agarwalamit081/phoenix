# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Phoenix is an AI-powered travel companion application designed to provide personalized, real-time travel guidance through voice and text interactions. The project is currently in the architectural planning phase, with comprehensive technical specifications documented in `Phoenix_Technical_Architecture.md`.

**Current Status:** Architecture/design phase. No source code implementation exists yet.

## Architecture Overview

Phoenix employs a microservices architecture with the following layers:

1. **Client Layer**: Web Application, Mobile App, Voice Interface
2. **API Gateway Layer**: API Gateway, WebSocket Handler, Authentication Service
3. **Service Layer**: Chat Service, Voice Service, Route Planning Service, Guided Tour Service, Translation Service, Preference Service
4. **AI/ML Layer**: LLM Orchestrator, STT, TTS, Embedding Service, RAG Pipeline
5. **Data Layer**: PostgreSQL + pgvector, Neo4j Knowledge Graph, Redis Cache, Object Storage

### Key Design Patterns

- **Event-Driven Communication**: All inter-service communication through well-defined events
- **Separation of Concerns**: Each microservice has a single, well-defined responsibility
- **API-First Design**: All functionality exposed through versioned APIs
- **Stateless Services**: No client-specific state between requests
- **Polyglot Persistence**: Different storage technologies (PostgreSQL, Neo4j, Redis) optimized for specific needs

## Core Components

### Voice Interaction Engine
Built on LiveKit (WebRTC infrastructure) and Speechmatics (real-time STT, translation, speaker diarization). Handles audio processing, voice activity detection, and supports multiple languages with automatic detection.

### Preference Collection & Knowledge Graph
Transforms casual conversation into structured user profiles using Neo4j. Enables understanding of complex preference relationships (e.g., "dislikes churches" but may appreciate "Gothic architecture").

### Route Planning Engine
Synthesizes user preferences, location constraints, and real-time social data (Reddit, Twitter, Google Maps) using a modified Traveling Salesman Problem algorithm optimized for tourist satisfaction.

### Guided Tour Orchestrator
Manages real-time tour execution with location-triggered content delivery. Uses Redis-backed checkpointing for state persistence and handles dynamic route modifications.

## Technology Stack

| Component | Technology |
|-----------|------------|
| Speech Processing | Speechmatics (real-time STT, translation, speaker diarization) |
| Real-Time Comms | LiveKit (WebRTC infrastructure) |
| LLM Provider | OpenAI (GPT-4o-mini for chat, GPT-4o for complex reasoning) |
| Workflow Orchestration | LangGraph (state machine orchestration) |
| Relational DB | PostgreSQL + pgvector (primary data store with vector similarity search) |
| Knowledge Graph | Neo4j (user preferences and semantic relationships) |
| Cache/Message Broker | Redis (session storage, caching, pub/sub messaging) |
| Data Validation | Pydantic |
| Logging | Loguru |
| Async DB Driver | asyncpg |

## Database Architecture

### PostgreSQL + pgvector
- **Users**: User accounts, authentication
- **user_preferences**: Preferences with vector embeddings for semantic search (1536-dim OpenAI embeddings)
- **points_of_interest**: POI data with location (PostGIS), embeddings, social signals
- **itineraries/itinerary_items**: Trip plans and execution status

### Neo4j Knowledge Graph
Node types: `User`, `Preference`, `Concept`, `Location`, `Behavior`
Key relationships: `HAS_PREFERENCE`, `IMPLIES`, `CONFLICTS_WITH`, `IS_A`, `RELATED_TO`, `NEAR`

### Redis Cache
- Sessions: 24h TTL
- Tour state: duration-dependent TTL
- Location-based cache: 1h TTL
- Social signals: 15m TTL
- Real-time events: 5m TTL

## LangGraph Workflows

Three main workflows orchestrate AI processes:

1. **Preference Collection Workflow**: Extracts structured preferences from natural language
2. **Route Planning Workflow**: Generates personalized itineraries
3. **Guided Tour Workflow**: Manages real-time tour execution

## API Architecture

### REST API Endpoints
- `POST /api/v1/chat` - Send chat message
- `POST /api/v1/routes/generate` - Generate route options
- `GET /api/v1/routes/{id}` - Get route details
- `PATCH /api/v1/routes/{id}` - Modify route
- `POST /api/v1/tours/start` - Start guided tour
- `POST /api/v1/translate` - Translate text
- `GET /api/v1/poi/nearby` - Find nearby POIs
- `GET /api/v1/preferences` - Get user preferences

### WebSocket Endpoints
- `wss://api.phoenix.travel/v1/ws/voice` - Audio streaming, voice communication
- `wss://api.phoenix.travel/v1/ws/tour/{tour_id}` - Location tracking, proximity alerts
- `wss://api.phoenix.travel/v1/ws/chat` - Streaming LLM responses

## Supported Languages

Chinese, English, Japanese, Korean, Hindi, French with automatic language detection.

## Security

- JWT-based authentication (15min access tokens, 7-day refresh tokens)
- OAuth 2.0 for Google and Apple Sign-In
- AES-256 encryption at rest, TLS 1.3 in transit
- GDPR and CCPA compliance

## Implementation Roadmap (12-week cycle)

| Phase | Duration | Deliverables |
|-------|----------|--------------|
| Phase 1 | Weeks 1-3 | Core infrastructure, database setup, basic chat interface, preference extraction |
| Phase 2 | Weeks 4-6 | Voice integration (Speechmatics, LiveKit), knowledge graph population |
| Phase 3 | Weeks 7-9 | Route planning engine, map integration, POI database, RAG pipeline |
| Phase 4 | Weeks 10-12 | Guided tour mode, social intelligence, translation, testing, deployment |

## Reference Documentation

The complete technical architecture is documented in `Phoenix_Technical_Architecture.md`, which includes:
- Detailed component specifications
- Complete database schemas
- API specifications with examples
- Security and compliance details
- Deployment architecture
- Code examples for key integrations
