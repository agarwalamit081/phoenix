**PHOENIX**

AI Travel Companion

Technical Architecture Document

Version 1.0

Powered by Speechmatics \| LiveKit \| LangGraph \| OpenAI

1\. Executive Summary 3

> 1.1 Core Capabilities 3

2\. System Architecture Overview 4

> 2.1 Architecture Principles 5

3\. Component Architecture 6

> 3.1 Core Components 6

4\. Database Architecture 10

> 4.1 PostgreSQL Schema Design 10
>
> 4.2 Neo4j Knowledge Graph Schema 12
>
> 4.3 Entity-Relationship Diagram 14
>
> 4.4 Redis Cache Architecture 15

5\. LangGraph Workflow Architecture 16

> 5.1 Preference Collection Workflow 16
>
> 5.2 Route Planning Workflow 18
>
> 5.3 Guided Tour Workflow 19

6\. Pipeline Architecture 20

> 6.1 RAG Pipeline 20
>
> 6.2 Social Intelligence Pipeline 22
>
> 6.3 Voice Processing Pipeline 23

7\. API Specifications 25

> 7.1 REST API Endpoints 25
>
> 7.2 WebSocket Endpoints 26

8\. Security & Compliance 27

> 8.1 Authentication & Authorization 27
>
> 8.2 Data Privacy Architecture 28

9\. Deployment Architecture 29

> 9.1 Scaling Strategy 30

10\. Implementation Roadmap 31

11\. Technology Stack Summary 32

*Note: Right-click the TOC and select \"Update Field\" to refresh page numbers.*

**1. Executive Summary**

Phoenix is an advanced AI-powered travel companion application designed to transform how travelers explore new destinations. The system leverages cutting-edge artificial intelligence technologies to provide personalized, real-time guidance that adapts to individual preferences, learning from user interactions to continuously improve recommendations. Phoenix represents a paradigm shift from static travel guides to dynamic, context-aware companions that understand the nuances of human travel preferences.

The application integrates multiple AI modalities including natural language processing, speech recognition, semantic search, and knowledge graph reasoning to deliver a seamless travel experience. By combining real-time data sources such as Reddit discussions, Google Maps reviews, and social media trends with historical travel patterns and individual preferences stored in a persistent knowledge graph, Phoenix creates truly personalized itineraries that evolve with each interaction.

Key differentiators of Phoenix include its ability to understand and remember user preferences over time, proactively adjusting recommendations based on expressed dislikes or changing interests. The system supports real-time voice interactions in multiple languages, enabling travelers to communicate with locals through instant translation capabilities. Furthermore, Phoenix maintains awareness of the user\'s current location and context, providing just-in-time information about nearby points of interest without requiring explicit queries.

**1.1 Core Capabilities**

1.  Smart Chat & User Interest Collection: Natural voice or text interactions that extract structured preferences from casual conversation, building comprehensive user profiles without tedious form-filling.

2.  Personalized Route Planning: AI-generated itineraries that combine user preferences, real-time social data, and location intelligence to create optimal travel routes.

3.  Voice-Corrected Navigation: Real-time navigation with voice interaction capabilities, allowing hands-free route modifications and information requests.

4.  Guided Explanation: Context-aware information delivery that provides relevant details about points of interest based on user interests and current context.

5.  Multilingual Commentary: Support for Chinese, English, Japanese, Korean, Hindi, and French with real-time translation for local communication.

**2. System Architecture Overview**

Phoenix employs a sophisticated microservices architecture designed for scalability, resilience, and real-time performance. The system is organized into distinct layers, each responsible for specific functionality while maintaining loose coupling through well-defined interfaces. This architectural approach enables independent scaling of components based on demand, facilitates continuous deployment without service disruption, and allows technology choices to be optimized for each layer\'s specific requirements.

The architecture follows a event-driven paradigm where components communicate through asynchronous message passing, ensuring that the system remains responsive even under high load. Real-time communication is handled through LiveKit for voice interactions, while Redis serves as both a message broker and caching layer to minimize latency for frequently accessed data. The separation of concerns between stateless services and stateful databases enables horizontal scaling of compute resources while maintaining data consistency.

**Figure 1: Phoenix High-Level System Architecture**

> graph TB
>
> subgraph \"Client Layer\"
>
> WEB\[Web Application\]
>
> MOB\[Mobile App\]
>
> VOICE\[Voice Interface\]
>
> end
>
> subgraph \"API Gateway Layer\"
>
> GW\[API Gateway\]
>
> WS\[WebSocket Handler\]
>
> AUTH\[Authentication Service\]
>
> end
>
> subgraph \"Service Layer\"
>
> CHAT\[Chat Service\]
>
> VOICE_SVC\[Voice Service\]
>
> ROUTE\[Route Planning Service\]
>
> GUIDE\[Guided Tour Service\]
>
> TRANS\[Translation Service\]
>
> PREF\[Preference Service\]
>
> end
>
> subgraph \"AI/ML Layer\"
>
> LLM\[LLM Orchestrator\]
>
> STT\[Speech-to-Text Engine\]
>
> TTS\[Text-to-Speech Engine\]
>
> EMB\[Embedding Service\]
>
> RAG\[RAG Pipeline\]
>
> end
>
> subgraph \"Data Layer\"
>
> PG\[(PostgreSQL + pgvector)\]
>
> NEO\[(Neo4j Knowledge Graph)\]
>
> REDIS\[(Redis Cache)\]
>
> S3\[Object Storage\]
>
> end
>
> subgraph \"External Services\"
>
> SPEECH\[Speechmatics API\]
>
> LIVEKIT\[LiveKit Rooms\]
>
> MAPS\[Mapbox/Google Maps\]
>
> SOCIAL\[Reddit/Social APIs\]
>
> end
>
> WEB \--\> GW
>
> MOB \--\> GW
>
> VOICE \--\> WS
>
> GW \--\> AUTH
>
> GW \--\> CHAT
>
> WS \--\> VOICE_SVC
>
> CHAT \--\> LLM
>
> VOICE_SVC \--\> STT
>
> VOICE_SVC \--\> TTS
>
> ROUTE \--\> RAG
>
> GUIDE \--\> LLM
>
> TRANS \--\> LLM
>
> PREF \--\> NEO
>
> LLM \--\> RAG
>
> RAG \--\> PG
>
> RAG \--\> NEO
>
> STT \--\> SPEECH
>
> TTS \--\> SPEECH
>
> VOICE_SVC \--\> LIVEKIT
>
> ROUTE \--\> MAPS

**2.1 Architecture Principles**

The Phoenix architecture adheres to several foundational principles that guide design decisions across all system components. These principles ensure that the system can evolve to meet future requirements while maintaining stability and performance. The principle of event sourcing ensures that all state changes are captured as immutable events, enabling complete audit trails and the ability to reconstruct system state at any point in time.

-   Event-Driven Communication: All inter-service communication occurs through well-defined events, enabling loose coupling and asynchronous processing patterns.

-   Separation of Concerns: Each microservice has a single, well-defined responsibility, making the system easier to understand, test, and maintain.

-   API-First Design: All functionality is exposed through versioned APIs, ensuring backward compatibility and enabling independent client development.

-   Stateless Services: Application services maintain no client-specific state between requests, enabling horizontal scaling and simplified failover.

-   Polyglot Persistence: Different data storage technologies are used based on specific requirements---relational, graph, and cache stores coexist.

**3. Component Architecture**

The Phoenix system is decomposed into several major components, each responsible for a specific domain of functionality. This decomposition enables independent development, testing, and deployment of features while maintaining system-wide coherence through well-defined interfaces and shared data contracts.

**3.1 Core Components**

**3.1.1 Voice Interaction Engine**

The Voice Interaction Engine represents Phoenix\'s primary interface for hands-free traveler engagement. Built on LiveKit\'s real-time communication infrastructure and Speechmatics\' advanced speech recognition, this component enables natural voice-based conversations with the AI companion. The engine handles audio stream processing, voice activity detection, speaker diarization for multi-party conversations, and seamless switching between voice and text interaction modes.

The component implements sophisticated audio processing pipelines including noise cancellation, echo suppression, and automatic gain control to ensure reliable voice recognition in diverse acoustic environments---from quiet museum corridors to bustling street markets. Real-time transcription supports multiple languages with automatic language detection, enabling travelers to seamlessly switch between languages mid-conversation.

**Figure 2: Voice Interaction Sequence Flow**

> sequenceDiagram
>
> participant U as User
>
> participant LK as LiveKit Room
>
> participant VS as Voice Service
>
> participant SM as Speechmatics
>
> participant LLM as LLM
>
> participant TTS as TTS Engine
>
> U-\>\>LK: Voice Input
>
> LK-\>\>VS: Audio Stream
>
> VS-\>\>SM: Transcribe Request
>
> SM\--\>\>VS: Transcription + Confidence
>
> VS-\>\>LLM: Process Intent
>
> LLM\--\>\>VS: Response Text
>
> VS-\>\>TTS: Synthesize Speech
>
> TTS\--\>\>VS: Audio Data
>
> VS-\>\>LK: Audio Response
>
> LK-\>\>U: Voice Output

**3.1.2 Preference Collection & Knowledge Graph**

The Preference Collection system transforms casual conversation into structured user profiles without requiring explicit form submissions. Through sophisticated entity extraction and intent recognition, the system identifies preferences across multiple dimensions including cuisine preferences, activity interests, mobility constraints, budget considerations, and temporal preferences. This information is persisted in Neo4j as a knowledge graph that captures relationships between preferences and enables sophisticated reasoning about user intent.

The Knowledge Graph architecture enables the system to understand that a user who expresses dislike for \"churches\" may still appreciate \"Gothic architecture\" in secular contexts, or that a preference for \"street food\" implies certain budget and ambiance expectations. The graph structure supports both explicit preferences stated by the user and implicit preferences inferred from behavior patterns, creating a comprehensive model of each traveler\'s unique profile.

**Figure 3: User Knowledge Graph Structure**

> graph LR
>
> subgraph \"User Profile Knowledge Graph\"
>
> USER((User))
>
> USER \--\> AGE\[Age Group: 25-35\]
>
> USER \--\> OCC\[Occupation: Designer\]
>
> USER \--\> HOBBY\[Hobby: Photography\]
>
> USER \--\> LIKE1\[Likes: Modern Art\]
>
> USER \--\> LIKE2\[Likes: Coffee\]
>
> USER \--\> LIKE3\[Likes: Hidden Gems\]
>
> USER \--\> DISLIKE1\[Dislikes: Crowds\]
>
> USER \--\> DISLIKE2\[Dislikes: Churches\]
>
> USER \--\> DISLIKE3\[Dislikes: Tourist Traps\]
>
> LIKE1 \--\> PREF1\[Preference: Contemporary Museums\]
>
> LIKE3 \--\> PREF2\[Preference: Local Recommendations\]
>
> DISLIKE1 \--\> ADJ1\[Adjustment: Skip Peak Hours\]
>
> DISLIKE2 \--\> ADJ2\[Adjustment: Substitute Cathedrals\]
>
> end

**3.1.3 Route Planning Engine**

The Route Planning Engine synthesizes multiple data sources to generate personalized travel itineraries. The engine employs a constraint-satisfaction approach that balances user preferences, logistical constraints (travel time, opening hours, physical distance), and real-time factors such as weather conditions and crowd levels. Routes are generated using a modified Traveling Salesman Problem algorithm optimized for tourist satisfaction rather than pure distance minimization.

A distinguishing feature of the Route Planning Engine is its integration with real-time social data sources. By monitoring Reddit discussions, Twitter mentions, and Google Maps reviews, the system can identify trending locations, temporary closures, and hidden gems that may not appear in traditional travel guides. This social intelligence enables Phoenix to provide recommendations that reflect current conditions rather than outdated database entries.

**3.1.4 Guided Tour Orchestrator**

Once a route is confirmed, the Guided Tour Orchestrator manages the execution of the travel plan, providing context-aware information delivery as the user progresses through their journey. The component maintains continuous awareness of the user\'s location through GPS tracking and proactively delivers relevant information as points of interest are approached. Users can interrupt guided tours with questions, request additional detail, or modify the route mid-journey.

The Orchestrator implements sophisticated state management to handle tour interruptions gracefully. If a user stops to explore an unplanned location, the system automatically adjusts timing estimates for remaining itinerary items and can suggest route modifications to accommodate the delay. This adaptive behavior ensures that guided tours remain useful even when travelers deviate from their planned routes.

**3.2 Component Interaction Matrix**

  ---------------------------------------------------------------------------------------------
  **Component**        **Input Sources**       **Output Targets**       **Key Dependencies**
  -------------------- ----------------------- ------------------------ -----------------------
  Voice Engine         Audio Streams           Transcriptions, Intent   Speechmatics, LiveKit

  Preference Service   Chat, Voice Input       Knowledge Graph          Neo4j, LLM

  Route Planner        Preferences, Location   Itineraries, Routes      Map APIs, Redis Cache

  Tour Guide           Routes, GPS Location    Audio/Text Content       RAG Pipeline, TTS

  Translation          Voice/Text Input        Translated Content       Speechmatics, LLM
  ---------------------------------------------------------------------------------------------

*Table 1: Component Interaction Matrix*

**4. Database Architecture**

Phoenix employs a polyglot persistence strategy, utilizing multiple database technologies optimized for different data access patterns and query requirements. This approach ensures that each type of data is stored in the most appropriate system, optimizing for both performance and functionality. The primary data stores include PostgreSQL with the pgvector extension for structured data and vector similarity search, Neo4j for the knowledge graph, and Redis for caching and real-time state management.

**4.1 PostgreSQL Schema Design**

PostgreSQL serves as the primary relational data store, managing user accounts, itinerary records, point-of-interest data, and audit logs. The pgvector extension enables efficient semantic search capabilities, allowing the system to find similar locations based on natural language descriptions rather than exact keyword matches. All tables include timestamps for auditing and soft-delete capabilities for data recovery.

**4.1.1 Users Table**

> CREATE TABLE users (
>
> id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
>
> email VARCHAR(255) UNIQUE NOT NULL,
>
> password_hash VARCHAR(255) NOT NULL,
>
> display_name VARCHAR(100),
>
> preferred_language VARCHAR(10) DEFAULT \'en\',
>
> created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
>
> updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
>
> last_active_at TIMESTAMP WITH TIME ZONE,
>
> is_active BOOLEAN DEFAULT true
>
> );
>
> CREATE INDEX idx_users_email ON users(email);
>
> CREATE INDEX idx_users_language ON users(preferred_language);

**4.1.2 User Preferences Vector Store**

> CREATE TABLE user_preferences (
>
> id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
>
> user_id UUID REFERENCES users(id) ON DELETE CASCADE,
>
> preference_type VARCHAR(50) NOT NULL, \-- \'like\', \'dislike\', \'neutral\'
>
> category VARCHAR(100) NOT NULL, \-- \'cuisine\', \'activity\', \'art_style\'
>
> value TEXT NOT NULL, \-- Natural language description
>
> embedding vector(1536), \-- OpenAI embedding for semantic search
>
> confidence_score FLOAT DEFAULT 1.0, \-- Confidence in preference extraction
>
> source VARCHAR(50), \-- \'explicit\', \'inferred\', \'behavioral\'
>
> created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
>
> expires_at TIMESTAMP WITH TIME ZONE \-- Optional expiration for temporary preferences
>
> );
>
> CREATE INDEX idx_prefs_user ON user_preferences(user_id);
>
> CREATE INDEX idx_prefs_type ON user_preferences(preference_type, category);
>
> CREATE INDEX idx_prefs_embedding ON user_preferences
>
> USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

**4.1.3 Points of Interest Table**

> CREATE TABLE points_of_interest (
>
> id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
>
> external_id VARCHAR(255), \-- Google Maps Place ID
>
> name VARCHAR(255) NOT NULL,
>
> description TEXT,
>
> category VARCHAR(100)\[\] DEFAULT \'{}\', \-- Array of categories
>
> address TEXT,
>
> latitude DECIMAL(10, 8) NOT NULL,
>
> longitude DECIMAL(11, 8) NOT NULL,
>
> embedding vector(1536), \-- Semantic embedding for similarity
>
> rating DECIMAL(3, 2),
>
> price_level INTEGER,
>
> opening_hours JSONB,
>
> contact_info JSONB,
>
> images JSONB DEFAULT \'\[\]\',
>
> social_signals JSONB DEFAULT \'{}\', \-- Reddit mentions, trending status
>
> created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
>
> updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
>
> is_active BOOLEAN DEFAULT true
>
> );
>
> CREATE INDEX idx_poi_location ON points_of_interest
>
> USING gist (ll_to_earth(latitude, longitude));
>
> CREATE INDEX idx_poi_category ON points_of_interest USING gin(category);
>
> CREATE INDEX idx_poi_embedding ON points_of_interest
>
> USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

**4.1.4 Itineraries and Route Items**

> CREATE TABLE itineraries (
>
> id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
>
> user_id UUID REFERENCES users(id) ON DELETE CASCADE,
>
> title VARCHAR(255),
>
> description TEXT,
>
> status VARCHAR(50) DEFAULT \'draft\', \-- \'draft\', \'confirmed\', \'active\', \'completed\'
>
> start_time TIMESTAMP WITH TIME ZONE,
>
> end_time TIMESTAMP WITH TIME ZONE,
>
> total_duration_minutes INTEGER,
>
> created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
>
> updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
>
> );
>
> CREATE TABLE itinerary_items (
>
> id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
>
> itinerary_id UUID REFERENCES itineraries(id) ON DELETE CASCADE,
>
> poi_id UUID REFERENCES points_of_interest(id),
>
> sequence_order INTEGER NOT NULL,
>
> estimated_duration_minutes INTEGER,
>
> actual_arrival_time TIMESTAMP WITH TIME ZONE,
>
> actual_departure_time TIMESTAMP WITH TIME ZONE,
>
> notes TEXT,
>
> status VARCHAR(50) DEFAULT \'planned\', \-- \'planned\', \'visited\', \'skipped\', \'modified\'
>
> created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
>
> );
>
> CREATE INDEX idx_itinerary_user ON itineraries(user_id);
>
> CREATE INDEX idx_itinerary_status ON itineraries(status);
>
> CREATE INDEX idx_items_itinerary ON itinerary_items(itinerary_id, sequence_order);

**4.2 Neo4j Knowledge Graph Schema**

The Neo4j graph database stores the user preference knowledge graph, enabling sophisticated reasoning about user interests and their interrelationships. The graph structure captures hierarchical relationships between concepts (e.g., \"Italian cuisine\" is-a \"European cuisine\"), implication rules (e.g., \"dislikes crowds\" implies \"prefer off-peak hours\"), and temporal patterns in user behavior. This rich semantic model enables the system to make intelligent inferences about user preferences that go beyond simple keyword matching.

**4.2.1 Node Types and Properties**

  ---------------------------------------------------------------------------------------------
  **Node Label**    **Properties**                      **Description**
  ----------------- ----------------------------------- ---------------------------------------
  User              user_id, created_at, last_active    Represents a registered user

  Preference        type, category, value, confidence   User\'s stated or inferred preference

  Concept           name, category, aliases\[\]         Travel-related concept or category

  Location          poi_id, name, categories\[\]        Point of interest reference

  Behavior          action, timestamp, context          Recorded user behavior event
  ---------------------------------------------------------------------------------------------

*Table 2: Neo4j Node Types*

**4.2.2 Relationship Types**

> // Neo4j Cypher Schema Definition
>
> // User-Preference Relationships
>
> (:User)-\[:HAS_PREFERENCE {
>
> since: datetime(),
>
> confidence: float,
>
> source: string // \'explicit\', \'inferred\', \'behavioral\'
>
> }\]-\>(:Preference)
>
> // Preference Hierarchy
>
> (:Preference)-\[:IMPLIES {
>
> strength: float // 0.0 to 1.0
>
> }\]-\>(:Preference)
>
> (:Preference)-\[:CONFLICTS_WITH\]-\>(:Preference)
>
> // Concept Relationships
>
> (:Concept)-\[:IS_A\]-\>(:Concept)
>
> (:Concept)-\[:RELATED_TO {
>
> similarity: float
>
> }\]-\>(:Concept)
>
> (:Concept)-\[:OPPOSITE_OF\]-\>(:Concept)
>
> // Location Relationships
>
> (:Location)-\[:BELONGS_TO_CATEGORY\]-\>(:Concept)
>
> (:Location)-\[:NEAR {
>
> distance_meters: float,
>
> walk_time_minutes: integer
>
> }\]-\>(:Location)
>
> // User Behavior
>
> (:User)-\[:VISITED {
>
> timestamp: datetime(),
>
> duration_minutes: integer,
>
> rating: integer
>
> }\]-\>(:Location)
>
> (:User)-\[:SKIPPED {
>
> timestamp: datetime(),
>
> reason: string
>
> }\]-\>(:Location)
>
> // Adaptive Learning
>
> (:Preference)-\[:DERIVED_FROM {
>
> weight: float
>
> }\]-\>(:Behavior)

**4.3 Entity-Relationship Diagram**

**Figure 4: Entity-Relationship Diagram**

> erDiagram
>
> USER \|\|\--o{ ITINERARY : creates
>
> USER \|\|\--o{ USER_PREFERENCE : has
>
> USER \|\|\--o{ BEHAVIOR_EVENT : generates
>
> ITINERARY \|\|\--\|{ ITINERARY_ITEM : contains
>
> ITINERARY_ITEM }o\--\|\| POI : references
>
> POI \|\|\--o{ POI_CATEGORY : has
>
> POI \|\|\--o{ POI_IMAGE : contains
>
> POI \|\|\--o{ SOCIAL_SIGNAL : receives
>
> USER_PREFERENCE \|\|\--\|\| PREFERENCE_TYPE : typed_as
>
> USER_PREFERENCE \|\|\--\|\| PREFERENCE_SOURCE : sourced_from
>
> BEHAVIOR_EVENT }o\--\|\| POI : targets
>
> BEHAVIOR_EVENT \|\|\--\|\| BEHAVIOR_TYPE : typed_as
>
> USER {
>
> uuid id PK
>
> string email
>
> string display_name
>
> string preferred_language
>
> timestamp created_at
>
> timestamp last_active_at
>
> }
>
> ITINERARY {
>
> uuid id PK
>
> uuid user_id FK
>
> string title
>
> string status
>
> timestamp start_time
>
> timestamp end_time
>
> }
>
> ITINERARY_ITEM {
>
> uuid id PK
>
> uuid itinerary_id FK
>
> uuid poi_id FK
>
> int sequence_order
>
> int estimated_duration_minutes
>
> string status
>
> }
>
> POI {
>
> uuid id PK
>
> string external_id
>
> string name
>
> text description
>
> decimal latitude
>
> decimal longitude
>
> vector embedding
>
> decimal rating
>
> }
>
> USER_PREFERENCE {
>
> uuid id PK
>
> uuid user_id FK
>
> string preference_type
>
> string category
>
> text value
>
> vector embedding
>
> float confidence_score
>
> }
>
> BEHAVIOR_EVENT {
>
> uuid id PK
>
> uuid user_id FK
>
> uuid poi_id FK
>
> string action
>
> jsonb context
>
> timestamp created_at
>
> }

**4.4 Redis Cache Architecture**

Redis serves multiple purposes in the Phoenix architecture: as a high-performance cache for frequently accessed data, as a message broker for real-time notifications, and as a session store for maintaining user state across services. The cache is organized into logical namespaces with appropriate TTL values based on data volatility and access patterns.

> \# Redis Key Naming Convention and TTL Strategy
>
> \# User Session Data (TTL: 24 hours)
>
> session:{user_id}:token -\> JWT token
>
> session:{user_id}:preferences -\> Cached preference summary
>
> session:{user_id}:location -\> Last known GPS coordinates
>
> \# Active Tour State (TTL: Duration of tour)
>
> tour:{tour_id}:state -\> Current tour progress
>
> tour:{tour_id}:items -\> Itinerary items cache
>
> tour:{user_id}:active_tour -\> Active tour reference
>
> \# Location-Based Cache (TTL: 1 hour)
>
> poi:nearby:{lat}:{lng}:{radius} -\> Nearby POIs by location
>
> poi:category:{category}:{city} -\> POIs by category
>
> poi:details:{poi_id} -\> Individual POI details
>
> \# Social Signals Cache (TTL: 15 minutes)
>
> social:trending:{city} -\> Trending locations
>
> social:reddit:{city} -\> Recent Reddit mentions
>
> social:reviews:{poi_id} -\> Aggregated reviews
>
> \# Real-Time Events (TTL: 5 minutes)
>
> events:user:{user_id} -\> User-specific events
>
> events:global -\> System-wide notifications
>
> events:location:{poi_id} -\> Location-specific alerts
>
> \# Rate Limiting (TTL: Variable)
>
> ratelimit:{user_id}:{endpoint} -\> API rate limit counter
>
> ratelimit:voice:{user_id} -\> Voice API usage

**5. LangGraph Workflow Architecture**

LangGraph provides the orchestration framework for Phoenix\'s multi-step AI workflows. Each workflow is modeled as a state machine with clearly defined nodes, edges, and conditional transitions. The graph-based approach enables complex branching logic, parallel execution paths, and human-in-the-loop interventions while maintaining traceability and debuggability. State persistence allows workflows to be paused and resumed, essential for long-running interactions like multi-day travel planning.

**5.1 Preference Collection Workflow**

The Preference Collection workflow orchestrates the extraction of structured preferences from natural language input. The workflow begins with entity extraction, proceeds through validation and conflict resolution, and concludes with knowledge graph updates. Each stage can branch based on confidence scores and user feedback, enabling iterative refinement of the preference model.

**Figure 5: Preference Collection State Machine**

> stateDiagram-v2
>
> \[\*\] \--\> InputProcessing
>
> InputProcessing \--\> EntityExtraction: Text/Voice Input
>
> EntityExtraction \--\> ConfidenceCheck
>
> ConfidenceCheck \--\> Validation: confidence \> 0.7
>
> ConfidenceCheck \--\> Clarification: confidence \<= 0.7
>
> Clarification \--\> EntityExtraction: User Response
>
> Validation \--\> ConflictDetection: Valid
>
> Validation \--\> Rejection: Invalid
>
> ConflictDetection \--\> Resolution: Conflicts Found
>
> ConflictDetection \--\> GraphUpdate: No Conflicts
>
> Resolution \--\> GraphUpdate: Resolved
>
> GraphUpdate \--\> \[\*\]: Success
>
> Rejection \--\> \[\*\]: Failed

**5.1.1 LangGraph Implementation**

> from langgraph.graph import StateGraph, END
>
> from langgraph.checkpoint.postgres import PostgresCheckpoint
>
> from typing import TypedDict, Annotated, List
>
> import operator
>
> class PreferenceState(TypedDict):
>
> user_id: str
>
> input_text: str
>
> extracted_entities: List\[dict\]
>
> confidence_scores: Annotated\[List\[float\], operator.add\]
>
> conflicts: List\[dict\]
>
> validation_errors: List\[str\]
>
> current_node: str
>
> def create_preference_workflow():
>
> workflow = StateGraph(PreferenceState)
>
> \# Define nodes
>
> workflow.add_node(\"entity_extraction\", extract_entities)
>
> workflow.add_node(\"confidence_check\", check_confidence)
>
> workflow.add_node(\"validation\", validate_entities)
>
> workflow.add_node(\"conflict_detection\", detect_conflicts)
>
> workflow.add_node(\"resolution\", resolve_conflicts)
>
> workflow.add_node(\"graph_update\", update_knowledge_graph)
>
> workflow.add_node(\"clarification\", request_clarification)
>
> \# Define edges
>
> workflow.set_entry_point(\"entity_extraction\")
>
> workflow.add_edge(\"entity_extraction\", \"confidence_check\")
>
> workflow.add_conditional_edges(
>
> \"confidence_check\",
>
> route_by_confidence,
>
> {
>
> \"high\": \"validation\",
>
> \"low\": \"clarification\"
>
> }
>
> )
>
> workflow.add_edge(\"clarification\", \"entity_extraction\")
>
> workflow.add_conditional_edges(
>
> \"validation\",
>
> route_by_validation,
>
> {
>
> \"valid\": \"conflict_detection\",
>
> \"invalid\": END
>
> }
>
> )
>
> workflow.add_conditional_edges(
>
> \"conflict_detection\",
>
> route_by_conflicts,
>
> {
>
> \"conflicts\": \"resolution\",
>
> \"none\": \"graph_update\"
>
> }
>
> )
>
> workflow.add_edge(\"resolution\", \"graph_update\")
>
> workflow.add_edge(\"graph_update\", END)
>
> return workflow.compile(checkpointer=PostgresCheckpoint(conn_string))

**5.2 Route Planning Workflow**

The Route Planning workflow synthesizes user preferences, location constraints, and real-time data to generate personalized itineraries. The workflow operates in parallel branches that gather data from multiple sources (knowledge graph, external APIs, social signals) before merging results for optimization. The final stage generates multiple route options ranked by predicted user satisfaction.

**Figure 6: Route Planning Workflow**

> graph TB
>
> subgraph \"Data Gathering Phase\"
>
> START(\[Start\]) \--\> PREF\[Fetch Preferences\]
>
> START \--\> LOC\[Fetch Location Data\]
>
> START \--\> SOC\[Fetch Social Signals\]
>
> PREF \--\> PG\[(PostgreSQL)\]
>
> LOC \--\> MAPS\[Map APIs\]
>
> SOC \--\> REDDIT\[Reddit API\]
>
> SOC \--\> REVIEWS\[Review APIs\]
>
> end
>
> subgraph \"Analysis Phase\"
>
> PG \--\> MERGE\[Merge Data\]
>
> MAPS \--\> MERGE
>
> REDDIT \--\> MERGE
>
> REVIEWS \--\> MERGE
>
> MERGE \--\> FILTER\[Filter by Preferences\]
>
> FILTER \--\> RANK\[Rank by Relevance\]
>
> end
>
> subgraph \"Optimization Phase\"
>
> RANK \--\> TSP\[Route Optimization\]
>
> TSP \--\> CONSTRAINT\[Apply Constraints\]
>
> CONSTRAINT \--\> VALIDATE\[Validate Route\]
>
> end
>
> subgraph \"Output Phase\"
>
> VALIDATE \--\> OPTION1\[Route Option 1\]
>
> VALIDATE \--\> OPTION2\[Route Option 2\]
>
> VALIDATE \--\> OPTION3\[Route Option 3\]
>
> OPTION1 \--\> END2(\[Return Options\])
>
> OPTION2 \--\> END2
>
> OPTION3 \--\> END2
>
> end

**5.3 Guided Tour Workflow**

The Guided Tour workflow manages real-time tour execution, handling location-triggered content delivery, user interruptions, and dynamic route modifications. The workflow maintains continuous state awareness through Redis-backed checkpointing, enabling instant recovery from network interruptions or application restarts.

> class TourState(TypedDict):
>
> tour_id: str
>
> user_id: str
>
> current_location: tuple\[float, float\] \# (lat, lng)
>
> current_item_index: int
>
> items: List\[dict\]
>
> status: str \# \'active\', \'paused\', \'interrupted\'
>
> pending_questions: List\[str\]
>
> modifications: List\[dict\]
>
> elapsed_time_minutes: int
>
> def create_tour_workflow():
>
> workflow = StateGraph(TourState)
>
> \# Core tour nodes
>
> workflow.add_node(\"location_monitor\", monitor_location)
>
> workflow.add_node(\"proximity_check\", check_proximity)
>
> workflow.add_node(\"content_delivery\", deliver_content)
>
> workflow.add_node(\"interruption_handler\", handle_interruption)
>
> workflow.add_node(\"route_adjustment\", adjust_route)
>
> workflow.add_node(\"progress_update\", update_progress)
>
> \# Monitoring loop
>
> workflow.set_entry_point(\"location_monitor\")
>
> workflow.add_edge(\"location_monitor\", \"proximity_check\")
>
> workflow.add_conditional_edges(
>
> \"proximity_check\",
>
> route_by_proximity,
>
> {
>
> \"arrived\": \"content_delivery\",
>
> \"approaching\": \"content_delivery\",
>
> \"far\": \"location_monitor\",
>
> \"off_route\": \"route_adjustment\"
>
> }
>
> )
>
> workflow.add_edge(\"content_delivery\", \"progress_update\")
>
> workflow.add_edge(\"progress_update\", \"location_monitor\")
>
> workflow.add_edge(\"route_adjustment\", \"location_monitor\")
>
> \# Interruption handling (parallel branch)
>
> workflow.add_edge(\"interruption_handler\", \"content_delivery\")
>
> return workflow.compile(
>
> checkpointer=RedisCheckpoint(redis_url),
>
> interrupt_before=\[\"interruption_handler\"\]
>
> )

**6. Pipeline Architecture**

Phoenix implements several specialized data processing pipelines that transform raw inputs into actionable intelligence. These pipelines operate continuously, processing streaming data from voice interactions, location updates, and external API feeds. Each pipeline is designed for fault tolerance with automatic retry mechanisms and dead-letter queues for failed processing attempts.

**6.1 RAG (Retrieval-Augmented Generation) Pipeline**

The RAG pipeline combines user-specific context from the knowledge graph with relevant external information to ground LLM responses in accurate, personalized data. The pipeline implements a multi-stage retrieval process that first identifies relevant user preferences, then retrieves location-specific information, and finally merges these contexts with the user\'s query for response generation.

**Figure 7: RAG Pipeline Architecture**

> flowchart LR
>
> subgraph \"Query Processing\"
>
> Q\[User Query\] \--\> EMB\[Embed Query\]
>
> EMB \--\> VEC\[Vector Search\]
>
> end
>
> subgraph \"Retrieval\"
>
> VEC \--\> PG\[(PostgreSQL)\]
>
> VEC \--\> NEO\[(Neo4j)\]
>
> VEC \--\> REDIS\[(Redis Cache)\]
>
> PG \--\> POI\[POI Data\]
>
> NEO \--\> PREF\[User Preferences\]
>
> REDIS \--\> CACHE\[Cached Context\]
>
> end
>
> subgraph \"Context Assembly\"
>
> POI \--\> MERGE\[Context Merger\]
>
> PREF \--\> MERGE
>
> CACHE \--\> MERGE
>
> MERGE \--\> RANK\[Relevance Ranking\]
>
> end
>
> subgraph \"Generation\"
>
> RANK \--\> LLM\[LLM Generation\]
>
> Q \--\> LLM
>
> LLM \--\> RESPONSE\[Response\]
>
> RESPONSE \--\> CACHE_UPDATE\[Update Cache\]
>
> end

**6.1.1 RAG Implementation**

> from langchain.retrievers import EnsembleRetriever
>
> from langchain.vectorstores.pgvector import PGVector
>
> from langchain.embeddings import OpenAIEmbeddings
>
> from neo4j import GraphDatabase
>
> class PhoenixRAGPipeline:
>
> def \_\_init\_\_(self, config):
>
> self.embeddings = OpenAIEmbeddings(model=\"text-embedding-3-small\")
>
> self.pgvector = PGVector(
>
> connection_string=config.postgres_url,
>
> embedding_function=self.embeddings,
>
> collection_name=\"poi_embeddings\"
>
> )
>
> self.neo4j = GraphDatabase.driver(config.neo4j_url)
>
> self.redis = redis.Redis.from_url(config.redis_url)
>
> async def retrieve_context(self, query: str, user_id: str) -\> dict:
>
> \# Generate query embedding
>
> query_embedding = await self.embeddings.aembed_query(query)
>
> \# Parallel retrieval
>
> poi_results = await self.\_retrieve_pois(query_embedding)
>
> preferences = await self.\_retrieve_preferences(user_id)
>
> cached_context = await self.\_get_cached_context(user_id)
>
> \# Merge and rank
>
> context = self.\_merge_context(
>
> query=query,
>
> pois=poi_results,
>
> preferences=preferences,
>
> cached=cached_context
>
> )
>
> return context
>
> async def \_retrieve_preferences(self, user_id: str) -\> list:
>
> with self.neo4j.session() as session:
>
> result = session.run(\"\"\"
>
> MATCH (u:User {user_id: \$user_id})-\[:HAS_PREFERENCE\]-\>(p:Preference)
>
> WHERE p.confidence \> 0.5
>
> RETURN p.type as type, p.category as category,
>
> p.value as value, p.confidence as confidence
>
> ORDER BY p.confidence DESC
>
> LIMIT 10
>
> \"\"\", user_id=user_id)
>
> return \[dict(record) for record in result\]
>
> def \_merge_context(self, query, pois, preferences, cached) -\> dict:
>
> \# Weighted combination of retrieved contexts
>
> merged = {
>
> \"query\": query,
>
> \"relevant_pois\": pois\[:5\],
>
> \"user_preferences\": preferences,
>
> \"historical_context\": cached,
>
> \"timestamp\": datetime.utcnow().isoformat()
>
> }
>
> return merged

**6.2 Social Intelligence Pipeline**

The Social Intelligence pipeline continuously monitors external data sources including Reddit, Twitter, and Google Maps to identify trending locations, temporary events, and emerging recommendations. This pipeline ensures that Phoenix\'s recommendations reflect current conditions rather than stale database entries. The pipeline implements sophisticated filtering to distinguish genuine recommendations from promotional content or low-quality reviews.

> import asyncio
>
> from tavily import TavilyClient
>
> from serpapi import GoogleSearch
>
> class SocialIntelligencePipeline:
>
> def \_\_init\_\_(self, config):
>
> self.tavily = TavilyClient(api_key=config.tavily_key)
>
> self.serp_key = config.serp_key
>
> self.redis = redis.Redis.from_url(config.redis_url)
>
> async def gather_social_signals(self, city: str) -\> dict:
>
> \# Run searches in parallel
>
> tasks = \[
>
> self.\_search_reddit(city),
>
> self.\_search_google_reviews(city),
>
> self.\_search_twitter(city),
>
> self.\_search_local_blogs(city)
>
> \]
>
> results = await asyncio.gather(\*tasks, return_exceptions=True)
>
> \# Aggregate and deduplicate
>
> signals = self.\_aggregate_signals(results)
>
> \# Cache results
>
> await self.\_cache_signals(city, signals)
>
> return signals
>
> async def \_search_reddit(self, city: str) -\> list:
>
> query = f\"hidden gems {city} travel recommendations\"
>
> response = await self.tavily.search(
>
> query=query,
>
> search_depth=\"advanced\",
>
> include_domains=\[\"reddit.com\"\],
>
> max_results=20
>
> )
>
> \# Extract structured data from Reddit posts
>
> extracted = \[\]
>
> for result in response.get(\"results\", \[\]):
>
> if self.\_is_recent(result.get(\"published_date\"), days=7):
>
> extracted.append({
>
> \"source\": \"reddit\",
>
> \"title\": result.get(\"title\"),
>
> \"url\": result.get(\"url\"),
>
> \"content\": result.get(\"content\"),
>
> \"score\": result.get(\"score\", 0),
>
> \"extracted_at\": datetime.utcnow().isoformat()
>
> })
>
> return extracted
>
> async def \_search_google_reviews(self, city: str) -\> list:
>
> params = {
>
> \"engine\": \"google_maps\",
>
> \"q\": f\"tourist attractions {city}\",
>
> \"type\": \"search\",
>
> \"api_key\": self.serp_key
>
> }
>
> search = GoogleSearch(params)
>
> results = search.get_dict()
>
> \# Filter high-rated places with recent reviews
>
> filtered = \[\]
>
> for place in results.get(\"local_results\", \[\]):
>
> if place.get(\"rating\", 0) \>= 4.0:
>
> filtered.append({
>
> \"source\": \"google_maps\",
>
> \"name\": place.get(\"title\"),
>
> \"place_id\": place.get(\"place_id\"),
>
> \"rating\": place.get(\"rating\"),
>
> \"reviews\": place.get(\"reviews\"),
>
> \"address\": place.get(\"address\")
>
> })
>
> return filtered

**6.3 Voice Processing Pipeline**

The Voice Processing pipeline handles the complete flow from audio capture to semantic understanding. Leveraging Speechmatics\' advanced recognition capabilities, the pipeline supports real-time transcription, speaker diarization, language identification, and confidence scoring. The pipeline is optimized for the unique challenges of travel scenarios: noisy environments, multilingual input, and domain-specific vocabulary (place names, local terminology).

**Figure 8: Voice Processing Pipeline**

> flowchart TB
>
> subgraph \"Audio Capture\"
>
> MIC\[Microphone\] \--\> STREAM\[Audio Stream\]
>
> STREAM \--\> VAD\[Voice Activity Detection\]
>
> end
>
> subgraph \"Speechmatics Processing\"
>
> VAD \--\> STT\[Speech-to-Text\]
>
> STT \--\> DIAR\[Speaker Diarization\]
>
> DIAR \--\> LANG\[Language Detection\]
>
> LANG \--\> CONF\[Confidence Scoring\]
>
> end
>
> subgraph \"Understanding\"
>
> CONF \--\> NLU\[Natural Language Understanding\]
>
> NLU \--\> INTENT\[Intent Classification\]
>
> NLU \--\> ENTITY\[Entity Extraction\]
>
> INTENT \--\> CONTEXT\[Context Assembly\]
>
> ENTITY \--\> CONTEXT
>
> end
>
> subgraph \"Response Generation\"
>
> CONTEXT \--\> LLM\[LLM Processing\]
>
> LLM \--\> TTS\[Text-to-Speech\]
>
> TTS \--\> AUDIO\[Audio Response\]
>
> AUDIO \--\> SPEAKER\[Speaker Output\]
>
> end

**6.3.1 Speechmatics Integration**

> import asyncio
>
> import websockets
>
> from speechmatics.flow import FlowClient, FlowConfig
>
> class SpeechmaticsVoicePipeline:
>
> def \_\_init\_\_(self, config):
>
> self.api_key = config.speechmatics_key
>
> self.language = \"en\" \# Auto-detect
>
> self.ws_url = \"wss://flow.speechmatics.com/v1\"
>
> async def transcribe_stream(self, audio_stream, on_transcript):
>
> config = FlowConfig(
>
> language_config={
>
> \"languages\": \[\"en\", \"zh\", \"ja\", \"ko\", \"hi\", \"fr\"\],
>
> \"auto_detect\": True
>
> },
>
> transcription_config={
>
> \"operating_point\": \"enhanced\",
>
> \"enable_partials\": True,
>
> \"enable_entities\": True,
>
> \"speaker_diarization\": True
>
> },
>
> translation_config={
>
> \"target_languages\": \[\"en\"\],
>
> \"enable_translation\": True
>
> }
>
> )
>
> async with websockets.connect(
>
> f\"{self.ws_url}?jwt={self.api_key}\"
>
> ) as ws:
>
> \# Send configuration
>
> await ws.send(config.to_json())
>
> \# Process audio stream
>
> async for audio_chunk in audio_stream:
>
> await ws.send(audio_chunk)
>
> \# Receive transcriptions
>
> result = await ws.recv()
>
> data = json.loads(result)
>
> if data.get(\"message\") == \"AddTranscript\":
>
> await on_transcript({
>
> \"text\": data\[\"transcript\"\],
>
> \"language\": data.get(\"language\", \"en\"),
>
> \"confidence\": data.get(\"confidence\", 0),
>
> \"speaker\": data.get(\"speaker\"),
>
> \"entities\": data.get(\"entities\", \[\]),
>
> \"is_final\": data.get(\"is_final\", False)
>
> })
>
> async def translate_to_local(
>
> self,
>
> text: str,
>
> target_language: str
>
> ) -\> str:
>
> \# Use Speechmatics translation for local communication
>
> async with websockets.connect(
>
> f\"{self.ws_url}/translate?jwt={self.api_key}\"
>
> ) as ws:
>
> translation_request = {
>
> \"message\": \"Translate\",
>
> \"text\": text,
>
> \"source_language\": \"en\",
>
> \"target_language\": target_language
>
> }
>
> await ws.send(json.dumps(translation_request))
>
> result = await ws.recv()
>
> return json.loads(result).get(\"translation\")

**7. API Specifications**

Phoenix exposes its functionality through a comprehensive RESTful API and WebSocket endpoints for real-time communication. The API follows OpenAPI 3.0 specifications with complete documentation for all endpoints, request/response schemas, and authentication requirements. All endpoints implement rate limiting and return structured error responses with actionable guidance.

**7.1 REST API Endpoints**

  ------------------------------------------------------------------------------------
  **Method**    **Endpoint**              **Description**          **Auth Required**
  ------------- ------------------------- ------------------------ -------------------
  POST          /api/v1/chat              Send chat message        Yes

  POST          /api/v1/routes/generate   Generate route options   Yes

  GET           /api/v1/routes/{id}       Get route details        Yes

  PATCH         /api/v1/routes/{id}       Modify route             Yes

  POST          /api/v1/tours/start       Start guided tour        Yes

  POST          /api/v1/translate         Translate text           Yes

  GET           /api/v1/poi/nearby        Find nearby POIs         Yes

  GET           /api/v1/preferences       Get user preferences     Yes
  ------------------------------------------------------------------------------------

*Table 3: Core REST API Endpoints*

**7.2 WebSocket Endpoints**

Real-time communication is handled through WebSocket connections that support bidirectional streaming for voice interactions and live updates. The WebSocket infrastructure is built on LiveKit, providing automatic reconnection, message queuing during network interruptions, and efficient binary protocol support for audio streams.

> \# WebSocket Connection Endpoints
>
> \# Voice Interaction Channel
>
> wss://api.phoenix.travel/v1/ws/voice
>
> \- Audio streaming for real-time transcription
>
> \- Bidirectional voice communication
>
> \- Automatic language detection
>
> \# Tour Updates Channel
>
> wss://api.phoenix.travel/v1/ws/tour/{tour_id}
>
> \- Real-time location tracking
>
> \- Proximity alerts
>
> \- Dynamic route updates
>
> \- Tour state synchronization
>
> \# Chat Stream Channel
>
> wss://api.phoenix.travel/v1/ws/chat
>
> \- Streaming LLM responses
>
> \- Real-time preference updates
>
> \- Multi-turn conversation support
>
> \# Message Format (JSON)
>
> {
>
> \"type\": \"transcript\" \| \"response\" \| \"alert\" \| \"update\",
>
> \"timestamp\": \"2024-01-15T10:30:00Z\",
>
> \"payload\": { \... },
>
> \"metadata\": {
>
> \"confidence\": 0.95,
>
> \"language\": \"en\",
>
> \"speaker_id\": \"user_001\"
>
> }
>
> }

**8. Security & Compliance**

Phoenix implements a comprehensive security framework designed to protect user data while enabling the personalized experiences that define the application. The security architecture encompasses authentication and authorization, data encryption at rest and in transit, privacy-preserving processing techniques, and compliance with international data protection regulations including GDPR and CCPA.

**8.1 Authentication & Authorization**

The authentication system uses JWT (JSON Web Tokens) with refresh token rotation for secure session management. OAuth 2.0 integration enables social login through Google and Apple, reducing friction for new users while maintaining security standards. Role-based access control (RBAC) governs access to sensitive operations, with fine-grained permissions for user data access and modification.

1.  JWT-based authentication with 15-minute access tokens and 7-day refresh tokens

2.  OAuth 2.0 integration for Google and Apple Sign-In

3.  Device fingerprinting for anomaly detection

4.  Rate limiting: 100 requests/minute for authenticated users

5.  API key rotation for service-to-service authentication

**8.2 Data Privacy Architecture**

User privacy is protected through a combination of data minimization, anonymization, and user-controlled sharing preferences. Personal data is stored in isolated tenant containers, and analytics are performed on anonymized aggregates. Users can export, review, and delete their data through self-service privacy controls in the application settings.

-   Data encryption at rest using AES-256, in transit using TLS 1.3

-   User-controlled data retention policies (30 days to permanent)

-   Automated PII detection and classification in all data stores

-   Right to erasure implementation with cascading deletes

-   Privacy-preserving analytics using differential privacy techniques

**9. Deployment Architecture**

Phoenix is designed for cloud-native deployment on Kubernetes, enabling horizontal scaling, automated failover, and efficient resource utilization. The architecture supports deployment across multiple cloud providers (AWS, GCP, Azure) through infrastructure-as-code templates, ensuring portability and avoiding vendor lock-in. Production deployments implement blue-green releases for zero-downtime updates.

**Figure 9: Kubernetes Deployment Architecture**

> graph TB
>
> subgraph \"Production Environment\"
>
> subgraph \"Kubernetes Cluster\"
>
> ING\[Ingress Controller\]
>
> subgraph \"Frontend Services\"
>
> WEB\[Web App Pod\]
>
> MOB\[Mobile API Pod\]
>
> end
>
> subgraph \"Core Services\"
>
> CHAT\[Chat Service\]
>
> ROUTE\[Route Service\]
>
> TOUR\[Tour Service\]
>
> VOICE\[Voice Service\]
>
> PREF\[Preference Service\]
>
> end
>
> subgraph \"AI/ML Services\"
>
> LLM\[LLM Orchestrator\]
>
> EMB\[Embedding Service\]
>
> RAG\[RAG Pipeline\]
>
> end
>
> subgraph \"Workers\"
>
> SOCIAL\[Social Intelligence\]
>
> NOTIFY\[Notification Worker\]
>
> end
>
> end
>
> subgraph \"Data Tier\"
>
> PG\[(PostgreSQL Cluster)\]
>
> NEO\[(Neo4j Cluster)\]
>
> REDIS\[(Redis Cluster)\]
>
> S3\[Object Storage\]
>
> end
>
> subgraph \"External Services\"
>
> SPEECH\[Speechmatics\]
>
> LIVEKIT\[LiveKit Cloud\]
>
> MAPS\[Map APIs\]
>
> end
>
> ING \--\> WEB
>
> ING \--\> MOB
>
> WEB \--\> CHAT
>
> MOB \--\> ROUTE
>
> CHAT \--\> LLM
>
> ROUTE \--\> RAG
>
> VOICE \--\> SPEECH
>
> VOICE \--\> LIVEKIT
>
> LLM \--\> PG
>
> PREF \--\> NEO
>
> SOCIAL \--\> PG
>
> NOTIFY \--\> REDIS
>
> end

**9.1 Scaling Strategy**

The system implements intelligent auto-scaling based on multiple metrics including CPU utilization, memory consumption, request latency, and queue depth. Horizontal Pod Autoscalers (HPA) automatically adjust replica counts for each service based on real-time demand, while Vertical Pod Autoscalers (VPAs) optimize resource requests for efficiency. Database tier scaling uses read replicas for PostgreSQL and Redis Cluster for distributed caching.

1.  HPA configured for 70% CPU threshold, scale up to 20 replicas

2.  VPA for right-sizing pod resource requests

3.  PostgreSQL read replicas for query distribution

4.  Redis Cluster with 3 masters, 3 replicas for HA

5.  CDN for static assets and API response caching

**10. Implementation Roadmap**

The Phoenix implementation follows a phased approach that delivers incremental value while managing technical risk. Each phase builds upon the previous, establishing stable foundations before introducing advanced capabilities. The roadmap is designed for a 12-week initial development cycle, with subsequent phases extending functionality based on user feedback.

  ----------------------------------------------------------------------------------------------------------------
  **Phase**   **Duration**      **Deliverables**
  ----------- ----------------- ----------------------------------------------------------------------------------
  Phase 1     Weeks 1-3         Core infrastructure, database setup, basic chat interface, preference extraction

  Phase 2     Weeks 4-6         Voice integration (Speechmatics, LiveKit), knowledge graph population

  Phase 3     Weeks 7-9         Route planning engine, map integration, POI database, RAG pipeline

  Phase 4     Weeks 10-12       Guided tour mode, social intelligence, translation, testing, deployment
  ----------------------------------------------------------------------------------------------------------------

*Table 4: Implementation Roadmap*

**11. Technology Stack Summary**

  -----------------------------------------------------------------------------------------------------
  **Layer**                **Technology**          **Purpose**
  ------------------------ ----------------------- ----------------------------------------------------
  Speech Processing        Speechmatics            Real-time STT, translation, speaker diarization

  Real-Time Comms          LiveKit                 WebRTC infrastructure for voice/video

  LLM Provider             OpenAI                  GPT-4o-mini for chat, GPT-4o for complex reasoning

  Workflow Orchestration   LangGraph               State machine orchestration for AI workflows

  Relational DB            PostgreSQL + pgvector   Primary data store with vector similarity search

  Knowledge Graph          Neo4j                   User preference graph and semantic relationships

  Cache/Message Broker     Redis                   Session storage, caching, pub/sub messaging

  Data Validation          Pydantic                Schema validation and serialization

  Logging                  Loguru                  Structured logging with context

  Async DB Driver          asyncpg                 Async PostgreSQL driver for high concurrency
  -----------------------------------------------------------------------------------------------------

*Table 5: Technology Stack Summary*
