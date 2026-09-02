# SceneCraft — Architecture & User Flow Diagrams

> Read `00-INDEX.md` first. All diagrams here use Mermaid syntax — they render natively on GitHub, in most editors, and in Claude Code's preview. If your viewer doesn't render Mermaid, the ASCII fallback for the core architecture is in `03-SYSTEM-DESIGN.md`.

---

## 1. System Architecture

```mermaid
flowchart TB
    subgraph Client
        UI[Next.js UI<br/>upload · agent trace · previs preview · chat]
    end

    subgraph Gateway["API Gateway (Cloud Run)"]
        GW[FastAPI<br/>Auth · Validation · Rate Limiting]
    end

    subgraph ControlPlane["Control Plane"]
        PS[Project Service<br/>Cloud SQL + Firestore]
        AO[Agent Orchestrator<br/>ADK / LangGraph]
    end

    subgraph Agents["Agent Pipeline"]
        BA[Script/Shot<br/>Breakdown Agent]
        FA[Storyboard Frame<br/>Generation Agent]
        AB[App-Build Agent<br/>constrained Gemini codegen]
        CA[Critic/Evaluator<br/>Agent]
        IA[Iteration Agent]
    end

    subgraph Data["Data & Messaging"]
        SQL[(Cloud SQL<br/>Postgres)]
        FS[(Firestore<br/>live state)]
        CS[(Cloud Storage<br/>scripts + frames)]
        BQ[(BigQuery<br/>history)]
        PS_BUS{{Pub/Sub}}
    end

    subgraph Obs["Observability"]
        OTEL[OpenTelemetry]
        GRAF[Grafana Dashboards]
    end

    PrevisRoute[["SceneCraft's own /previs route<br/>(served on Replit — replit.app/replit.dev URL)"]]

    UI -->|HTTPS/JWT| GW
    GW --> PS
    GW --> AO
    PS --> SQL
    PS --> FS
    AO --> PS_BUS
    PS_BUS --> BA --> FA --> AB --> CA
    IA --> AB
    BA --> CS
    FA --> CS
    AB --> PrevisRoute
    CA --> PrevisRoute
    AO --> BQ
    Agents -.trace spans.-> OTEL --> GRAF
    UI -.live subscription.-> FS
```

---

## 2. Agent Orchestration Graph (state machine)

```mermaid
stateDiagram-v2
    [*] --> Planning
    Planning --> Breakdown: initial_generation
    Planning --> Iterating: iteration

    Breakdown --> FrameGeneration: shots extracted
    Breakdown --> NeedsReview: validation fails twice

    FrameGeneration --> AppBuild: all frames complete/flagged
    Iterating --> AppBuild: diff applied

    AppBuild --> Critic: generation succeeds
    AppBuild --> NeedsReview: generation fails twice

    Critic --> Complete: verification passes
    Critic --> AppBuild: mismatch found (1 bounded retry)
    Critic --> NeedsReview: still failing after retry

    Complete --> [*]
    NeedsReview --> [*]
```

---

## 3. Sequence Diagram — Initial Generation (script upload → live previs)

```mermaid
sequenceDiagram
    actor Priya as Priya (Director)
    participant UI as Next.js UI
    participant GW as API Gateway
    participant PS as Project Service
    participant Bus as Pub/Sub
    participant Orch as Agent Orchestrator
    participant BA as Breakdown Agent
    participant FA as Frame Agent
    participant AB as App-Build Agent
    participant CA as Critic Agent

    Priya->>UI: Upload script.pdf
    UI->>GW: POST /projects/{id}/scripts
    GW->>PS: validate + store script
    PS->>Bus: publish initial_generation job
    GW-->>UI: 202 { job_id }
    UI->>UI: subscribe to job trace (Firestore)

    Bus->>Orch: job received
    Orch->>BA: run breakdown
    BA-->>Orch: scenes/shots (structured JSON)
    Orch-->>UI: trace: breakdown complete

    Orch->>FA: generate frames (fan-out per shot)
    FA-->>Orch: frame URLs + alt text
    Orch-->>UI: trace: frames complete

    Orch->>AB: build previs content
    AB->>AB: serialize data file + bounded Gemini customization call
    AB-->>Orch: data file + customization JSON ready
    Orch-->>UI: trace: app-build complete

    Orch->>CA: verify generated content
    CA->>CA: compare data file against expected ProjectState
    CA-->>Orch: verdict: pass
    Orch-->>UI: trace: complete, previs ready

    Priya->>UI: Click "open previs" link
    UI->>UI: navigate to /projects/{id}/previs
```

---

## 4. Sequence Diagram — Natural-Language Iteration

```mermaid
sequenceDiagram
    actor Priya as Priya (Director)
    participant UI as Next.js UI
    participant GW as API Gateway
    participant Orch as Agent Orchestrator
    participant IA as Iteration Agent
    participant AB as App-Build Agent
    participant CA as Critic Agent

    Priya->>UI: "Make scene 4 night-time"
    UI->>GW: POST /projects/{id}/iterate
    GW-->>UI: 202 { job_id }

    Orch->>IA: interpret request against ProjectState
    alt request is clear
        IA-->>Orch: structured diff { shot_id, field, new_value }
        Orch->>AB: incremental rebuild (affected shots only)
        AB-->>Orch: redeployed app URL
        Orch->>CA: verify affected shots only
        CA-->>Orch: verdict: pass
        Orch-->>UI: trace: iteration complete
    else request is ambiguous
        IA-->>Orch: clarification question
        Orch-->>UI: trace: needs clarification
        UI-->>Priya: show clarification prompt
    end
```

---

## 5. User Flow — Priya's End-to-End Journey (primary persona)

```mermaid
flowchart LR
    A([Priya has a script,<br/>no previs budget]) --> B[Sign up / log in]
    B --> C[Create project<br/>+ style reference]
    C --> D[Upload script<br/>PDF or text]
    D --> E{Watches live<br/>agent trace}
    E --> F[Breakdown agent<br/>extracts shots]
    F --> G[Frame agent generates<br/>storyboard images]
    G --> H[App-build agent deploys<br/>interactive previs app]
    H --> I[Critic agent verifies]
    I --> J([Priya opens the<br/>deployed app link])
    J --> K{Happy with it?}
    K -->|No, wants a change| L[Type edit in<br/>plain English]
    L --> M[Iteration agent<br/>+ redeploy]
    M --> J
    K -->|Yes| N([Shares link with<br/>DP / investor])
```

---

## 6. User Flow — Auth

```mermaid
flowchart TD
    Start([Visit app]) --> HasToken{Token in<br/>local storage?}
    HasToken -->|Yes| Dashboard[Dashboard]
    HasToken -->|No| LoginPage[Login / Signup page]
    LoginPage --> ChooseMode{New user?}
    ChooseMode -->|Yes| Signup[POST /auth/signup]
    Signup --> Login[POST /auth/login]
    ChooseMode -->|No| Login
    Login --> StoreToken[Store JWT]
    StoreToken --> Dashboard
    Dashboard --> Protected{Every API call}
    Protected -->|Valid token| Allowed[Request proceeds]
    Protected -->|Invalid/expired| Redirect[Redirect to Login]
```

---

## 7. Entity Relationship Diagram

```mermaid
erDiagram
    USERS ||--o{ PROJECTS : owns
    PROJECTS ||--o{ SCRIPTS : contains
    SCRIPTS ||--o{ SCENES : "parsed into"
    SCENES ||--o{ SHOTS : contains
    SHOTS ||--o{ SHOT_FRAMES : "has"
    SHOTS ||--o{ SHOT_EDITS : "edited via"
    PROJECTS ||--o{ GENERATION_JOBS : tracks
    USERS ||--o{ SHOT_EDITS : requests

    USERS {
        uuid id PK
        string email
        string password_hash
        timestamptz created_at
    }
    PROJECTS {
        uuid id PK
        uuid owner_id FK
        string title
        text style_reference
    }
    SCRIPTS {
        uuid id PK
        uuid project_id FK
        text raw_text
        string source_format
    }
    SCENES {
        uuid id PK
        uuid script_id FK
        int scene_number
        string heading
    }
    SHOTS {
        uuid id PK
        uuid scene_id FK
        int shot_number
        jsonb characters
        string location
    }
    SHOT_FRAMES {
        uuid id PK
        uuid shot_id FK
        text image_url
        text alt_text
    }
    SHOT_EDITS {
        uuid id PK
        uuid shot_id FK
        string field
        uuid requested_by FK
    }
    GENERATION_JOBS {
        uuid id PK
        uuid project_id FK
        string job_type
        string status
    }
```

---

## 8. Deployment / Infrastructure Diagram

```mermaid
flowchart TB
    subgraph GH["GitHub"]
        PR[Pull Request] --> CI[GitHub Actions<br/>lint · typecheck · test · build]
    end
    CI -->|image push| AR[(Artifact Registry)]
    AR -->|Terraform apply| CR1[Cloud Run: API]
    AR -->|Terraform apply| CR2[Cloud Run: Web]
    AR -->|Terraform apply| CR3[Cloud Run: Agent Workers]

    subgraph GCP["Google Cloud Project"]
        CR1
        CR2
        CR3
        SQL[(Cloud SQL)]
        FS[(Firestore)]
        CSB[(Cloud Storage)]
        SM[Secret Manager]
        PUBSUB{{Pub/Sub}}
        BQ[(BigQuery)]
        MON[Cloud Monitoring]
    end

    CR1 --> SQL
    CR1 --> FS
    CR1 --> SM
    CR3 --> PUBSUB
    CR3 --> CSB
    CR3 --> BQ
    CR1 & CR2 & CR3 --> MON
    MON --> Grafana[Grafana Dashboards]
```

---

## 9. Data Flow — Where Each Artifact Lives

```mermaid
flowchart LR
    Script[Raw script text] -->|stored| SQL[(Cloud SQL)]
    Script -->|chunked + embedded| RAG[(pgvector / Vertex AI Search)]
    Shots[Structured shots] -->|stored| SQL
    Frames[Generated images] -->|stored| CS[(Cloud Storage)]
    FrameURL[Frame URL + alt text] -->|referenced| SQL
    JobEvents[Agent job step events] -->|live| FS[(Firestore)]
    JobHistory[Completed job records] -->|archived| BQ[(BigQuery)]
    Traces[OTel spans] -->|shipped| Grafana
```

---

## Notes for Claude Code

- These diagrams are the **contract**, not decoration — if an implementation detail in a later phase contradicts one of these flows (e.g. the Critic Agent calling App-Build directly instead of going back through the Orchestrator), that's a signal to stop and reconcile the diagram and the code, not to silently drift from the design.
- The state diagram in section 2 maps directly to the `generation_jobs.status` enum in `05-DATABASE-DESIGN.md` — keep them in sync if either changes.
- The two sequence diagrams (sections 3 and 4) are the two flows every end-to-end test in `08-IMPLEMENTATION-PLAN.md` should exercise.
