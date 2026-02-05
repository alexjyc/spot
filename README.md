# Spot On - Multi-Agent Travel Recommendation System

## Overview

**Spot On** is a fast, parallel multi-agent travel recommendation system that provides curated suggestions for:
1. **Restaurants** - Best dining for first day (top 5)
2. **Travel Spots** - Must-see attractions (exactly 3)
3. **Hotels** - Accommodation options with per-night pricing (3-5)
4. **Car Rentals** - Vehicle rental options (up to 3)
5. **Flights** - One-way or round-trip flights (up to 3)

### Key Features
- ⚡ **Fast**: ~8-10 seconds average response time (parallel agent execution)
- 🤖 **Multi-Agent**: 5 specialized agents working in parallel
- 🔍 **Grounded**: All recommendations from Tavily search (real-time web data)
- 📊 **Enriched**: Automatic extraction of prices, hours, addresses, phone numbers
- 🎯 **Simple**: Clean interface with minimal input required

---

## Architecture

### Multi-Agent System (MAS)

```
                    ParseRequest
                         │
         ┌───────────────┼───────────────┬───────────────┐
         │               │               │               │
         ▼               ▼               ▼               ▼
  RestaurantAgent  AttractionsAgent  HotelAgent   TransportAgent
                                                    (Car + Flights)
         │               │               │               │
         └───────────────┴───────────────┴───────────────┘
                              ▼
                      EnrichmentAgent
                              ▼
                      AggregateResults
                              ▼
                            END
```

**Execution Flow:**
1. **ParseRequest** - Extract origin, destination, dates from user prompt
2. **4 Domain Agents** - Execute in parallel:
   - RestaurantAgent: Search and rank restaurants
   - AttractionsAgent: Select top 3 must-see spots
   - HotelAgent: Find hotels with pricing
   - TransportAgent: Search car rentals AND flights
3. **EnrichmentAgent** - Batch extract webpage content, parse details (sequential after all 4 complete)
4. **AggregateResults** - Merge enriched data into final output

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
```bash
# Using Docker:
docker run -d -p 27017:27017 --name travel-mongo mongo:7

# Or using local MongoDB:
mongod --dbpath /path/to/data
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
    "prompt": "Tokyo to Seoul, departing March 15, 2026, returning March 18, 2026",
    "options": {}
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
    "flights": [...]
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
  -d '{"prompt": "From LAX to Paris on April 10, returning April 17"}'
```

**Expected constraints:**
- origin: "Los Angeles (LAX)"
- destination: "Paris"
- departing_date: "2026-04-10"
- returning_date: "2026-04-17"

**Test with interests:**
```bash
curl -X POST http://localhost:8000/api/runs \
  -H "Content-Type: application/json" \
  -d '{"prompt": "NYC to London next month, love food and museums, moderate budget"}'
```

**Expected:**
- interests: ["food", "museums"]
- budget: "moderate"

---

## Performance

### Expected Execution Times

| Phase | Duration | Notes |
|-------|----------|-------|
| ParseRequest | ~500ms | LLM call to extract constraints |
| Domain Agents | ~3-5s | **Parallel execution** (4 agents) |
| EnrichmentAgent | ~4-5s | Tavily extract + LLM parsing |
| AggregateResults | ~100ms | Merge data |
| **Total** | **~8-10s** | vs ~20-25s sequential |

### Timeouts

- RestaurantAgent: 30s
- AttractionsAgent: 30s
- HotelAgent: 30s
- TransportAgent: 40s (two sub-searches)
- EnrichmentAgent: 45s

---

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
Graph node start: EnrichmentAgent    <-- Starts after all 4 complete
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
  "prompt": "string (required)",
  "options": {
    "interests": ["string"],
    "budget": "budget|moderate|luxury"
  }
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
    "returning_date": "YYYY-MM-DD|null",
    "interests": ["string"],
    "budget": "string"
  },
  "final_output": {
    "restaurants": [...],
    "travel_spots": [...],
    "hotels": [...],
    "car_rentals": [...],
    "flights": [...]
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
