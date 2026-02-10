# Spot On - Multi-Agent Travel Recommendation System

## Overview

**Spot On** is a fast, parallel multi-agent travel recommendation system that provides curated suggestions for:
1. **Restaurants** - Best dining options (top 7)
2. **Travel Spots** - Must-see attractions (top 7)
3. **Hotels** - Accommodation options with per-night pricing (top 7)
4. **Car Rentals** - Vehicle rental options (top 5)
5. **Flights** - One-way or round-trip flights (top 5)

### Key Features
- ⚡ **Fast**: ~8-10 seconds average response time (parallel agent execution)
- 🤖 **Multi-Agent**: 5 specialized agents working in parallel
- 🔍 **Grounded**: All recommendations from Tavily search (real-time web data)
- 📊 **Enriched**: Automatic extraction of prices, hours, addresses, phone numbers
- 🎯 **Simple**: Clean interface with minimal input required

---

## Documentation

This repository keeps the assignment’s deliverables split intentionally:

- **README (this file)**: project summary, local setup, usage, examples, and repo layout.
- **Technical docs**: `docs/TECHNICAL_DOC.md` (architecture, agent roles, LangGraph flow, MongoDB schema, deployment guide).

If you prefer a single-document approach, you can fold the technical docs into this README, but keeping them in `docs/TECHNICAL_DOC.md` makes staff/lead review and ongoing maintenance easier.

For review: have a staff engineer / engineering lead read `docs/TECHNICAL_DOC.md` and cross-check each section against the referenced code/config files.

---

## Assignment Context

This project was built for the Tavily Engineering Assignment, which requires:
1. Multi-agent system leveraging Tavily Search + Extract APIs
2. Production-ready deployment (AWS Elastic Beanstalk + MongoDB Atlas)
3. Real-time progress streaming and result exports

**Key innovations:**
- **6-agent architecture:** ParseRequest + 4 domain agents (parallel) + WriterAgent (5 parallel LLMs) + EnrichmentAgent
- **Separation of concerns:** Search (I/O bound) separated from normalization (CPU bound)
- **Graceful degradation:** Partial results if agents fail
- **~15s average latency:** Parallel execution at both search and normalization stages

For evaluation criteria alignment, see `docs/ASSIGNMENT_EVALUATION.md`.

---

## Architecture

### Multi-Agent System (MAS)

```
                    ParseRequest (~500ms)
                         │
         ┌───────────────┼───────────────┬───────────────┐
         │               │               │               │
         ▼               ▼               ▼               ▼
  RestaurantAgent  AttractionsAgent  HotelAgent   TransportAgent
   (search only)    (search only)   (search only)  (search only)
      TOP_N=15         TOP_N=15        TOP_N=15    CAR+FLIGHT=15+15
         │               │               │               │
         └───────────────┴───────────────┴───────────────┘
                              ▼
                        WriterAgent (~6s)
                   (5 parallel LLM normalizations)
                     7+7+7+5+5 = 31 top picks
                              ▼
                      EnrichmentAgent (~5s)
                   (Tavily extract + LLM parse)
                              ▼
                      AggregateResults (~100ms)
                              ▼
                            END
```

**Execution Flow:**
1. **ParseRequest** - Validate constraints and derive query context
2. **4 Domain Agents (parallel)** - Search only, return raw results:
   - RestaurantAgent: 15 raw results
   - AttractionsAgent: 15 raw results
   - HotelAgent: 15 raw results
   - TransportAgent: 15 cars + 15 flights
3. **WriterAgent** - 5 parallel LLM normalizations → 31 top picks + references
4. **EnrichmentAgent** - Batch extract webpages (20 at once), parse details
5. **AggregateResults** - Merge enriched data into final output

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
# Edit .env and add:
# - OPENAI_API_KEY=sk-...
# - TAVILY_API_KEY=tvly-...
# - MONGODB_URI=mongodb://localhost:27017
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
MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/travel_planner?retryWrites=true&w=majority
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
```

2. **Start dev server:**
```bash
bun run dev
# Frontend runs on http://localhost:3000
```

---

## Usage

### Web Interface

1. Open http://localhost:3000
2. Fill in the form:
   - **Origin**: e.g., "Tokyo"
   - **Destination**: e.g., "Seoul"
   - **Departing Date**: e.g., "2026-03-15"
   - **Returning Date**: (optional) e.g., "2026-03-18"
3. Click "Find Recommendations"
4. Wait ~8-10 seconds for results

### API Usage

**Create a run:**
```bash
curl -X POST http://localhost:8000/api/runs \
  -H "Content-Type: application/json" \
  -d '{
    "constraints": {
      "origin": "Tokyo",
      "destination": "Seoul",
      "departing_date": "2026-03-15",
      "returning_date": "2026-03-18"
    }
  }'

# Response: {"runId": "run_abc123"}
```

**Check run status:**
```bash
curl http://localhost:8000/api/runs/run_abc123
```

**Response structure:**
```json
{
  "runId": "run_abc123",
  "status": "done",
  "constraints": {
    "origin": "Tokyo (NRT)",
    "destination": "Seoul (ICN)",
    "departing_date": "2026-03-15",
    "returning_date": "2026-03-18"
  },
  "final_output": {
    "restaurants": [...],
    "travel_spots": [...],
    "hotels": [...],
    "car_rentals": [...],
    "flights": [...],
    "references": [...],
    "agent_statuses": {...},
    "warnings": [...]
  },
  "warnings": [],
  "durationMs": 8234
}
```

---

## Testing

### Backend Tests

```bash
cd backend
source .venv/bin/activate

# Unit tests (agents)
pytest tests/test_agents.py -v

# Integration test (full graph)
pytest tests/test_graph_integration.py -v

# Run all tests
pytest tests/ -v
```

### Manual Testing

**Test ParseRequest:**
```bash
curl -X POST http://localhost:8000/api/runs \
  -H "Content-Type: application/json" \
  -d '{
    "constraints": {
      "origin": "Los Angeles",
      "destination": "Paris",
      "departing_date": "2026-04-10",
      "returning_date": "2026-04-17"
    }
  }'
```

**Test with interests:**
```bash
curl -X POST http://localhost:8000/api/runs \
  -H "Content-Type: application/json" \
  -d '{
    "constraints": {
      "origin": "New York",
      "destination": "London",
      "departing_date": "2026-04-01",
      "returning_date": "2026-04-07",
      "interests": ["food", "museums"],
      "budget": "moderate"
    }
  }'
```

---

## Performance

### Expected Execution Times

| Phase | Duration | Notes |
|-------|----------|-------|
| ParseRequest | ~500ms | Constraint validation |
| Domain Agents | ~3-5s | **Parallel execution** (4 search agents) |
| WriterAgent | ~5-6s | 5 parallel LLM normalizations → 31 top picks |
| EnrichmentAgent | ~4-5s | Tavily extract + LLM parsing |
| AggregateResults | ~100ms | Merge data |
| **Total** | **~13-17s** | vs ~25-30s sequential |

### Timeouts

- RestaurantAgent: 30s
- AttractionsAgent: 30s
- HotelAgent: 30s
- TransportAgent: 40s (two sub-searches)
- EnrichmentAgent: 45s

---

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
    ├── app/                 # Next.js UI + route handlers (proxy)
    └── lib/
```

## Debugging

### Check Logs

Backend logs show parallel execution:
```
Graph node start: ParseRequest
Graph node end: ParseRequest (durationMs=500)
Graph node start: RestaurantAgent
Graph node start: AttractionsAgent    <-- All 4 start simultaneously
Graph node start: HotelAgent
Graph node start: TransportAgent
Graph node end: RestaurantAgent (durationMs=3200)
Graph node end: AttractionsAgent (durationMs=2800)
Graph node end: HotelAgent (durationMs=3500)
Graph node end: TransportAgent (durationMs=4200)
Graph node start: WriterAgent        <-- Starts after all 4 complete
Graph node end: WriterAgent (durationMs=5800)
Graph node start: EnrichmentAgent
Graph node end: EnrichmentAgent (durationMs=4500)
```

### Common Issues

**1. "MongoDB not configured"**
- Check MONGODB_URI in .env
- Ensure MongoDB is running: `docker ps` or `mongod`

**2. "OpenAI not configured"**
- Check OPENAI_API_KEY in .env
- Verify key is valid: `curl https://api.openai.com/v1/models -H "Authorization: Bearer $OPENAI_API_KEY"`

**3. "Tavily not configured"**
- Check TAVILY_API_KEY in .env
- Test Tavily: `curl -X POST https://api.tavily.com/search -d '{"api_key":"YOUR_KEY","query":"test"}'`

**4. Agent timeout**
- Check logs for which agent timed out
- Increase timeout in agent's `TIMEOUT_SECONDS` constant
- Check Tavily rate limits

**5. Empty results**
- Check warnings array in response
- Verify agent_statuses: should be "completed" not "failed"
- Test Tavily search manually to verify results available

**6. WriterAgent normalization failures**
- Check logs for which category failed
- Verify OpenAI API key is valid and has quota
- Check if search results are empty (no raw_* items)

**7. Enrichment returning partial results**
- Check Tavily extract quota
- Some URLs may be inaccessible (403, 404)
- This is expected - system degrades gracefully

---

## Extending

### Add a New Agent

1. **Create agent file:**
```python
# backend/app/agents/my_agent.py
from app.agents.base import BaseAgent
from app.schemas.spot_on import MyOutput

class MyAgent(BaseAgent):
    TIMEOUT_SECONDS = 30

    async def execute(self, state):
        # Your logic here
        return {
            "my_results": [...],
            "agent_statuses": {self.agent_id: "completed"}
        }
```

2. **Add to state:**
```python
# backend/app/graph/state.py
class SpotOnState(TypedDict, total=False):
    ...
    my_results: list[dict[str, Any]]
```

3. **Add to graph:**
```python
# backend/app/graph/graph.py
from app.agents.my_agent import MyAgent

def build_graph(deps):
    my_agent = MyAgent("my_agent", deps)
    graph.add_node("MyAgent", _wrap("MyAgent", my_agent.execute))
    graph.add_edge("ParseRequest", "MyAgent")
    graph.add_edge("MyAgent", "EnrichmentAgent")
```

4. **Update frontend:**
```tsx
// frontend/components/ResultsView.tsx
const { my_results = [] } = results;
```

### Add Caching

Recommended: Redis cache for common routes
```python
# Pseudo-code
cache_key = f"spot_on:{origin}:{destination}:{date}"
if cached := await redis.get(cache_key):
    return cached
result = await graph.ainvoke(state)
await redis.setex(cache_key, 3600, result)  # 1 hour TTL
```

---

## Production Checklist

- [ ] Set up MongoDB replica set (not standalone)
- [ ] Add Redis for caching
- [ ] Configure rate limiting (per user/IP)
- [ ] Add monitoring (Sentry, Datadog, etc.)
- [ ] Set up CI/CD pipeline
- [ ] Add integration tests with mocked Tavily
- [ ] Configure CORS_ORIGINS for production domain
- [ ] Use production OpenAI model (gpt-4-turbo)
- [ ] Add request ID tracking for debugging
- [ ] Set up CloudWatch/logging infrastructure
- [ ] Add health check endpoint monitoring
- [ ] Configure autoscaling for FastAPI workers

---

## API Reference

### POST /api/runs

Create a new recommendation run.

**Request:**
```json
{
  "constraints": {
    "origin": "string (required)",
    "destination": "string (required)",
    "departing_date": "YYYY-MM-DD (required)",
    "returning_date": "YYYY-MM-DD (optional)",
    "interests": ["string (optional)"],
    "budget": "string (optional)"
  },
  "options": {}
}
```

**Response:**
```json
{
  "runId": "string"
}
```

### GET /api/runs/{runId}

Get run status and results.

**Response:**
```json
{
  "runId": "string",
  "status": "queued|running|done|error",
  "updatedAt": "datetime",
  "constraints": {
    "origin": "string",
    "destination": "string",
    "departing_date": "YYYY-MM-DD",
    "returning_date": "YYYY-MM-DD|null"
  },
  "final_output": {
    "restaurants": [...],
    "travel_spots": [...],
    "hotels": [...],
    "car_rentals": [...],
    "flights": [...],
    "references": [...],
    "agent_statuses": {...},
    "warnings": [...]
  },
  "warnings": ["string"],
  "durationMs": 0,
  "error": null
}
```

### GET /api/runs/{runId}/events

SSE stream of run events.

**Events:**
- `node` - Node execution start/end
- `artifact` - Intermediate results
- `log` - General log messages

---

## License

MIT

---

## Support

For issues or questions:
1. Check logs first
2. Verify environment variables
3. Test Tavily/OpenAI connectivity
4. Review agent timeouts
5. Check MongoDB connection

Happy travels! ✈️
