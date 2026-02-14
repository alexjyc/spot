# Spot On - Multi-Agent Travel Recommendation System

## Overview

**Spot On** is a fast, parallel multi-agent travel recommendation system that provides curated suggestions for:
1. **Restaurants** - Best dining options
2. **Travel Spots** - Must-see attractions
3. **Hotels** - Accommodations with per-night pricing when available
4. **Car Rentals** - Vehicle rental options
5. **Flights** - One-way or round-trip flights


---

## Architecture

### Multi-Agent System (MAS)

```mermaid
graph TD
   ParseRequest --> RestaurantAgent
   ParseRequest --> AttractionsAgent
   ParseRequest --> HotelAgent
   ParseRequest --> TransportAgent

   RestaurantAgent --> |enrichment| EnrichAgent
   RestaurantAgent --> |skip| QualitySplit
   AttractionsAgent --> |enrichment| EnrichAgent
   AttractionsAgent --> |skip| QualitySplit
   HotelAgent --> |enrichment| EnrichAgent
   HotelAgent --> |skip| QualitySplit
   TransportAgent --> |enrichment| EnrichAgent
   TransportAgent --> |skip| QualitySplit

   EnrichAgent --> |gap>50% & loops<2| EnrichAgent
   EnrichAgent --> QualitySplit

   QualitySplit --> BudgetAgent
   BudgetAgent --> END
```

**Execution Flow:**
1. **ParseRequest** - Validate constraints and derive query context
2. **4 Domain Agents (parallel)** - Tavily search + LLM structured normalization per category
3. **EnrichAgent (optional)** - Tavily extract + targeted follow-up search to fill missing fields (bounded loop)
4. **QualitySplit** - Demotes items missing critical fields (name, url) or all important fields into `references`
5. **BudgetAgent** - Produces `report.total_estimated_budget` and materializes `final_output`



## Folder Structure

```
.
├── README.md
├── docs/
│   └── TECHNICAL_DOC.md
├── backend/
│   ├── app/                 # FastAPI app + LangGraph workflow + agents
│   ├── tests/
│   ├── Dockerfile           # AWS/production container
│   └── .elasticbeanstalk/   # Elastic Beanstalk config (Docker platform)
└── frontend/
    ├── app/                 # Next.js UI
    └── lib/
```

---

## Setup

### Backend Setup

1. **Install dependencies:**
```bash
cd backend
uv venv && source .venv/bin/activate
uv pip install -e .
```

2. **Set environment variables:**
```bash
cp .env.example .env
```

3. **Start MongoDB:**

#### Option 1: Local MongoDB (Development)
```bash
# Using Docker:
docker run -d -p 27017:27017 --name travel-mongo mongo:7

# Or using local MongoDB:
mongod --dbpath /path/to/data
```

#### Option 2: MongoDB Atlas (Production)

1. **Create MongoDB Atlas cluster:**
   - Go to https://cloud.mongodb.com
   - Create free M0 cluster
   - Create database user (username + password)
   - Whitelist your IP (or 0.0.0.0/0 for dev)

2. **Get connection string:**
   - Click "Connect" → "Connect your application"
   - Copy connection string: `mongodb+srv://user:pass@cluster.mongodb.net/`

3. **Update .env:**
```bash
MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/
DB_NAME=YOUR_DB_NAME
```

4. **Start backend:**
```bash
uv run uvicorn app.main:app --reload
# Backend runs on http://localhost:8000
```

### Frontend Setup

1. **Install dependencies:**
```bash
cd frontend
bun install
cp .env.example .env.local  # Set NEXT_PUBLIC_API_URL
```

2. **Start dev server:**
```bash
bun run dev # Frontend runs on http://localhost:3000
```

---

## Usage

### Web Interface

1. Open http://localhost:3000
2. Fill in the form:
   - **Origin**: e.g., "NYC, Osaka, etc"
   - **Departing Date**: e.g., "2026-03-15"
   - **Returning Date**: (optional) e.g., "2026-03-18"
   - **Vibe / Budget / Climate**: used to recommend a destination first
   - **Deep Research**: toggles `skip_enrichment` — when enabled, EnrichAgent runs to fill missing fields
3. Click "Find Recommendations"
4. The UI will:
   - call `POST /recommend` to choose a destination, then
   - call `POST /runs` to execute the LangGraph workflow and stream progress

---

## API Reference

### POST /recommend

**Request:**
```json
{
  "origin": "San Francisco",
  "departing_date": "2026-03-15",
  "returning_date": "2026-03-20",
  "vibe": "cultural and historic",
  "budget": "moderate",
  "climate": "warm"
}
```

**Response:**
```json
{
  "destination": "Kyoto",
  "reasoning": "Rich cultural heritage with temples, traditional districts, and spring weather"
}
```

---

### POST /runs

**Request:**
```json
{
  "constraints": {
    "origin": "San Francisco (SFO)",
    "destination": "Tokyo (NRT)",
    "departing_date": "2026-03-15",
    "returning_date": "2026-03-20"
  },
  "options": {
    "skip_enrichment": false
  }
}
```

**Response:**
```json
{
  "runId": "run_abc123"
}
```

---

### GET /runs/{runId}

**Response:**
```json
{
  "runId": "run_abc123",
  "status": "done",
  "updatedAt": "2026-02-14T10:30:00Z",
  "progress": {
    "nodes": {
      "RestaurantAgent": { "node": "RestaurantAgent", "status": "end" },
      "AttractionsAgent": { "node": "AttractionsAgent", "status": "end" }
    }
  },
  "constraints": {
    "origin": "San Francisco (SFO)",
    "destination": "Tokyo (NRT)",
    "departing_date": "2026-03-15",
    "returning_date": "2026-03-20"
  },
  "final_output": {
    "restaurants": [{ "name": "Sukiyabashi Jiro", "cuisine": "Sushi", "area": "Ginza" }],
    "travel_spots": [{ "name": "Senso-ji Temple", "kind": "Historic", "area": "Asakusa" }],
    "hotels": [{ "name": "Park Hyatt Tokyo", "area": "Shinjuku", "price_per_night": "$450" }],
    "car_rentals": [{ "provider": "Toyota Rent a Car", "vehicle_class": "Compact" }],
    "flights": [{ "airline": "ANA", "route": "SFO-NRT", "price_range": "$800-1200" }],
    "constraints": { "origin": "San Francisco (SFO)", "destination": "Tokyo (NRT)" },
    "references": [],
    "report": { "total_estimated_budget": "$3,200-4,800" }
  },
  "warnings": [],
  "error": null
}
```

---

### GET /runs/{runId}/events

Server-Sent Events stream with real-time updates.

**Event types:**
- `node` — `{ node, status, message? }` per agent lifecycle
- `artifact` — `{ type: "constraints" | "final_output", payload }` materialized data
- `log` — progress messages

---

### POST /runs/{runId}/cancel

Best-effort cancellation of a running workflow.

### GET /runs/{runId}/export/pdf

Export completed run results as a PDF document (`status=done` only).

### GET /runs/{runId}/export/xlsx

Export completed run results as an Excel spreadsheet (`status=done` only).

---

Happy travels! ✈️
