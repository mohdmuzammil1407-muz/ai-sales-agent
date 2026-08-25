# AI Sales Agent

> Production-oriented LLM sales and booking assistant with conversational state, retrieval-augmented generation, lead qualification, meeting scheduling, authentication, and an embeddable web chat experience.

## Overview

This repository contains a full-stack AI sales assistant designed to move beyond a simple chatbot. The system combines an LLM with structured conversation state, a knowledge/retrieval layer, business rules, external integrations, and a web dashboard/widget.

The agent is designed to:

- Understand a prospect's business and content requirements
- Guide conversations through discovery, qualification, recommendation, and closing stages
- Maintain structured lead and conversation state across turns
- Retrieve relevant business/package information through a vector-search layer
- Generate context-aware responses with an LLM
- Score and qualify leads
- Support meeting scheduling through Google Calendar integration
- Handle email/SMS OTP verification
- Expose protected admin APIs for leads, conversations, and meetings
- Serve an embeddable chat widget for integration into a website

## Architecture

```text
                         ┌─────────────────────────┐
                         │     Web Chat Widget      │
                         │   / Dashboard (Next.js) │
                         └────────────┬────────────┘
                                      │ HTTP / REST
                                      ▼
                         ┌─────────────────────────┐
                         │      FastAPI Backend     │
                         │                          │
                         │  Chat / Auth / Admin API │
                         └────────────┬────────────┘
                                      │
                 ┌────────────────────┼────────────────────┐
                 │                    │                    │
                 ▼                    ▼                    ▼
        ┌────────────────┐   ┌─────────────────┐   ┌─────────────────┐
        │ Conversation   │   │ Retrieval / RAG │   │ Business Logic  │
        │ State Manager  │   │ LangChain+FAISS │   │ Lead / Sales     │
        └───────┬────────┘   └────────┬────────┘   │ / Objections     │
                │                     │             └────────┬────────┘
                └─────────────────────┼──────────────────────┘
                                      ▼
                            ┌──────────────────┐
                            │    LLM Layer     │
                            │ OpenAI API       │
                            │ GPT-4o-mini      │
                            └────────┬─────────┘
                                     │
                ┌────────────────────┼────────────────────┐
                ▼                    ▼                    ▼
       ┌────────────────┐   ┌────────────────┐   ┌────────────────┐
       │ Google Calendar│   │ Email / SMTP   │   │ Twilio / SMS   │
       └────────────────┘   └────────────────┘   └────────────────┘
                                      │
                                      ▼
                              ┌──────────────┐
                              │ PostgreSQL   │
                              └──────────────┘
```

## Agent Workflow

The application uses structured conversation state rather than relying only on free-form model output. The flow can move through stages such as:

```text
Greeting
   ↓
Discovery
   ↓
Qualification
   ↓
Recommendation
   ↓
Objection Handling
   ↓
Closing / Booking
```

The LLM receives the current conversation state and, when available, retrieved knowledge-base context. This allows the response layer to stay aware of information such as the prospect's business, audience, timeline, budget, recommended package, lead score, and order status.

## Retrieval / RAG

The retrieval layer uses LangChain-compatible OpenAI embeddings and FAISS for local vector search.

The current implementation:

1. Builds a structured knowledge document containing company/service information and package data.
2. Splits the knowledge into chunks.
3. Creates embeddings using OpenAI embeddings.
4. Stores the vectors locally with FAISS.
5. Performs similarity search for incoming queries.
6. Injects the retrieved context into the LLM prompt before response generation.

This helps ground sales responses in application-specific information rather than relying exclusively on the model's general knowledge.

## AI / Agent Components

### LLM response generation

The backend uses the OpenAI API and currently targets `gpt-4o-mini` in the implementation. The LLM receives:

- System instructions
- Current structured conversation state
- Recent conversation history
- Retrieved knowledge-base context when available
- The latest user message

### Structured state

The agent maintains information including:

- Sales stage
- Sales mode
- Name and contact information
- Business name
- Video/content requirements
- Target audience
- Timeline
- Budget
- Recommended package
- Lead score
- Order/confirmation state

### Business services

The backend separates several responsibilities into services, including:

- LLM generation
- RAG/retrieval
- Intent detection
- Lead scoring
- Objection handling
- Sales-mode control
- Calendar scheduling
- Email notifications
- OTP generation/verification
- Authentication

## Integrations

The project includes integration points for:

- **OpenAI API** — LLM generation and embeddings
- **Google Calendar API** — meeting scheduling
- **SMTP** — email OTPs and notifications
- **Twilio** — SMS OTP workflow
- **PostgreSQL** — application and lead data
- **Docker** — containerized deployment

## Backend

The backend is built with:

- Python
- FastAPI
- SQLAlchemy/PostgreSQL
- OpenAI API
- LangChain
- FAISS
- JWT authentication
- Docker

Key areas:

```text
video_agent/
├── app/
│   ├── core/             # prompts, configuration, state management
│   ├── database/         # database setup and initialization
│   ├── models/           # Pydantic / SQLAlchemy models
│   ├── routes/            # chat, auth, admin APIs
│   └── services/         # LLM, RAG, calendar, email, scoring, etc.
├── tests/                # end-to-end and integration tests
├── widget/               # embeddable chat widget
├── Dockerfile
└── requirements.txt
```

## Frontend

The frontend is a Next.js application providing:

- Chat experience
- Login/authentication flow
- Lead dashboard
- Conversation dashboard
- Meeting dashboard
- Email dashboard
- Protected admin routes
- Embeddable widget assets

```text
vide-frontend/
├── app/
│   ├── dashboard/
│   ├── login/
│   └── page.tsx
├── components/
├── lib/
├── public/
└── package.json
```

## API Surface

Examples of the backend endpoints include:

| Endpoint | Purpose |
|---|---|
| `POST /api/v1/chat` | Send a message to the AI sales assistant |
| `POST /api/v1/auth/request-otp` | Start email/SMS verification |
| `POST /api/v1/auth/verify-otp` | Verify an OTP |
| `POST /api/v1/admin/login` | Authenticate an administrator |
| `GET /api/v1/admin/leads` | Retrieve captured leads |
| `GET /api/v1/admin/conversations` | Retrieve conversation data |
| `GET /api/v1/admin/meetings` | Retrieve scheduled meetings |
| `GET /widget/widget.js` | Serve the embeddable chat widget |

## Running Locally

### Backend

```bash
cd video_agent
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
# source venv/bin/activate

pip install -r requirements.txt
```

Create a local `.env` from the example file:

```bash
copy .env.example .env
```

Then configure the required credentials and services.

Start the backend:

```bash
python run.py
```

Or:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd vide-frontend
npm install
npm run dev
```

The frontend normally runs on the Next.js development server while the backend runs on port `8000`.

## Docker

The repository includes Docker configuration for the backend and the overall application workflow. Review `docker-compose.yml` and the service-specific Dockerfiles for the current configuration.

## Configuration and Secrets

Never commit production credentials, API keys, OAuth credentials, database passwords, or `.env` files.

Use the supplied `.env.example` files as templates for local configuration.

For a portfolio/demo deployment, use separate test credentials and a non-production database.

## Testing

The backend includes end-to-end and integration-oriented tests covering areas such as:

- Agent conversations
- Chat flows
- Meeting scheduling
- Email workflows
- Google API integration
- Response guards
- Live conversation scenarios

Run the relevant test suite from `video_agent` after installing dependencies and configuring the required test environment.

## Engineering Focus

The project was built with the principle that an AI feature is not production-ready just because a model can generate a good response. The implementation therefore combines the model with:

- Structured application state
- Retrieval grounding
- Deterministic business logic
- External API integrations
- Authentication and protected admin routes
- Error handling and fallback responses
- Automated tests
- Containerized deployment
- Configurable environment-based secrets

## Portfolio Note

This repository is intended to demonstrate the engineering patterns behind a practical AI business workflow: connecting an LLM to application state, retrieval, APIs, authentication, data persistence, and user-facing software.

> **Note:** This project contains integrations and configuration intended for controlled environments. Do not use the included examples or credentials for production without reviewing security, privacy, access control, and deployment requirements.
