def build_restaurant_prompt(*, destination: str, item_count: int) -> str:
    return f"""ROLE: You are an data extraction specialist .

TASK: Normalize ALL restaurant search results for {destination} into structured output.

RULES:
- Output EXACTLY {item_count} items — one per search result. Do NOT merge, drop, or invent items.
- NO DUPLICATES

FIELDS:
- id: "restaurant_<destination>_<number>" (e.g., restaurant_paris_1)
- name: Exact restaurant name as stated in source
- cuisine: Standard label (e.g., "Italian", "Korean BBQ", "Seafood") — null if not stated
- area: Neighborhood/district (e.g. "Los Angeles, CA", "Paris, France") — null if not mentioned
- price_range: "$", "$$", "$$$", or "$$$$" — null if not inferable
- url: Exact source URL, copied verbatim
- snippet: 1-2 factual sentences from the source
- why_recommended: 1-2 sentences on suitability for a first-day visitor
- tags: 2-4 from [michelin-star, local-favorite, vegetarian-friendly, late-night, outdoor-seating, iconic, hidden-gem, family-friendly, date-spot, quick-bite]


STEPS:
1. Identify the fields requirement for restaurants
2. Convert string input to list of sources (each source has title, url, content)
3. Extract fields from source text and page_content per source
4. Normalize each unique source into structured output

CALIBRATION: If < 80% confident a value is correct, set to null.
"""


def build_attractions_prompt(*, destination: str, item_count: int) -> str:
    return f"""ROLE: You are a data extraction specialist.

TASK: Normalize ALL attraction search results for {destination} into structured output.

RULES:
- Output EXACTLY {item_count} items — one per search result. Do NOT merge, drop, or invent items.
- NO DUPLICATES

FIELDS:
- id: "attraction_<destination_city>_<number>"
- name: Exact name from source
- kind: One of [museum, park, landmark, temple, shrine, market, district, beach, garden, viewpoint, palace, other] — null if unclear
- area: Neighborhood/district — null if not mentioned
- url: Exact source URL
- snippet: 1-2 factual sentences from source
- why_recommended: Why essential for first-time visitor
- estimated_duration_min: Visit duration in minutes. Use source if available; estimate conservatively (museums: 90-120, parks: 60-90, landmarks: 30-60)

STEPS:
1. Identify the fields requirement for attractions
2. Convert string input to list of sources (each source has title, url, content)
3. Extract fields from source text and page_content per source
4. Normalize each unique source into structured output

CALIBRATION: If < 80% confident a value is correct, set to null.
"""


def build_hotel_prompt(
    *,
    destination: str,
    departing_date: str,
    returning_date: str | None,
    stay_nights: int | None = None,
    item_count: int,
) -> str:
    return f"""ROLE: You are a data extraction specialist.

TASK: Normalize ALL hotel search results for {destination} into structured output.

RULES:
- Output EXACTLY {item_count} items — one per search result. Do NOT merge, drop, or invent items.
- NO DUPLICATES


CONTEXT:
- Check-in: {departing_date}
- Check-out: {returning_date or "Not specified"}
- Stay: {stay_nights or "Not specified"} nights


FIELDS:
- id: "hotel_<destination_city>_<number>"
- name: Exact hotel name
- area: Neighborhood/district — null if not mentioned
- price_per_night: Per-night rate as numeric value in USD (e.g., "150", "320") — null if not extractable
- url: Exact source URL
- snippet: 1-2 factual sentences from source
- why_recommended: Why it suits a visitor. Mention location advantages
- amenities: Confirmed amenities only, from [wifi, pool, gym, breakfast-included, parking, spa, restaurant, airport-shuttle, pet-friendly]


STEPS:
1. Identify the fields requirement for hotels
2. Convert string input to list of sources (each source has title, url, content)
3. Extract fields from source text and page_content per source
4. Normalize each unique source into structured output


CALIBRATION: If < 80% confident a value is correct, set to null.
"""


def build_car_rental_prompt(*, destination: str, departing_date: str, returning_date: str | None = None, item_count: int) -> str:
    return f"""ROLE: You are a data extraction specialist.

TASK: Normalize ALL car rental search results for {destination} into structured output.

CONTEXT:
- Pickup date: {departing_date}
- Return date: {returning_date or "Not specified"}

RULES:
- Output EXACTLY {item_count} items — one per search result. Do NOT merge, drop, or invent items.
- NO DUPLICATES

FIELDS:
- id: "car_<destination_city>_<number>"
- provider: Rental company name (e.g., "Hertz", "Budget") or local providers
- vehicle_class: One of [economy, compact, sedan, SUV, luxury, minivan, convertible] — null if not stated
- price_per_day: Daily rental rate as numeric value in USD (e.g., "45", "80") — null if not stated
- pickup_location: Pickup location (e.g., "Airport Terminal 1") — null if unknown
- url: Exact source URL
- why_recommended: 1-2 sentences on why practical for a visitor


STEPS:
1. Identify the fields requirement for car rentals
2. Convert string input to list of sources (each source has title, url, content)
3. Extract fields from source text and page_content per source
4. Normalize each unique source into structured output


CALIBRATION: If < 80% confident a value is correct, set to null."""


def build_flight_prompt(
    *,
    origin: str,
    destination: str,
    departing_date: str,
    returning_date: str | None,
    trip_type: str,
    item_count: int,
) -> str:
    return f"""ROLE: You are a data extraction specialist.

TASK: Normalize ALL flight search results from {origin} to {destination} into structured output.

CONTEXT:
- Departure: {departing_date}
- Return: {returning_date or "N/A (one-way)"}
- Trip type: {trip_type}

RULES:
- Output EXACTLY {item_count} items — one per search result. Do NOT merge, drop, or invent items.
- NO DUPLICATES

FIELDS:
- id: "flight_<origin_code>_<dest_code>_<number>"
- airline: Airline name — null if source is aggregator without specific airline
- route: "<city/code> -> <city/code>" (e.g., "LAX -> NRT")
- trip_type: Must be "{trip_type}" — do not override
- price_range: Price/range with currency (e.g., "$450", "$350-$600") — null if not stated
- url: Exact source URL
- snippet: 1-2 factual sentences about the option
- why_recommended: Why it stands out (direct flight, best price, schedule convenience)


STEPS:
1. Identify the fields requirement for flights
2. Convert string input to list of sources (each source has title, url, content)
3. Extract fields from source text and page_content per source
4. Normalize each unique source into structured output


CALIBRATION: If < 80% confident a value is correct, set to null."""


def build_enrichment_prompt(
    *, item_type: str, missing_fields: list[str] | None = None
) -> str:
    type_hint = TYPE_HINTS.get(item_type, "Focus on: price, hours, address, phone")

    if missing_fields:
        field_descriptions = {
            "operating_hours": "operating_hours: Operating hours as stated on page — copy verbatim",
            "menu_url": "menu_url: Full URL to the menu if explicitly present — null otherwise",
            "reservation_url": "reservation_url: Full URL to reservation/booking if explicitly present — null otherwise",
            "price_range": "price_range: Price range (e.g., '$$', '$$$') — null if not inferable",
            "cuisine": "cuisine: Cuisine label if explicitly stated — null otherwise",
            "rating": "rating: Numeric rating score (e.g., 4.5) from a review source like Google, Yelp, TripAdvisor — null if not stated",
            "kind": "kind: Attraction type (museum, park, landmark, etc.) — null if unclear",
            "admission_price": "admission_price: Admission/ticket price as stated — null otherwise",
            "price_per_night": "price_per_night: Per-night hotel rate as numeric value in USD (e.g., '150') — null if not stated",
            "amenities": "amenities: Confirmed amenities list — empty list if none found",
            "price_per_day": "price_per_day: Daily car rental rate as numeric value in USD (e.g., '45') — null if not stated",
            "vehicle_class": "vehicle_class: Vehicle type (economy, compact, sedan, SUV, luxury, etc.) — null if not stated",
            "airline": "airline: Airline name — null if not stated",
        }
        fields_text = "\n".join(
            f"- {field_descriptions.get(f, f'{f}: Extract if present — null otherwise')}"
            for f in missing_fields
        )
    else:
        fields_text = (
            "- cuisine: Cuisine label if explicitly stated (restaurants only) — null otherwise\n"
            "- kind: Attraction kind if explicitly stated (attractions only) — null otherwise\n"
            "- menu_url: Full URL to the menu if explicitly present (restaurants only) — null otherwise\n"
            "- reservation_url: Full URL to reservation/booking if explicitly present — null otherwise\n"
            "- admission_price: Admission/ticket price as stated (attractions only) — null otherwise\n"
            "- operating_hours: Operating hours as stated on page — copy verbatim\n"
            "- price_range: Price range (e.g., '$$', '$$$') — null if not inferable\n"
            "- price_per_night: Per-night rate as numeric value in USD (hotels only) — null if not stated\n"
            "- amenities: Confirmed amenities list (hotels only) — empty list if none"
        )

    return f"""ROLE: You are a data extraction specialist converting unstructured webpage content into precise structured records.

TASK: Extract structured details from webpage content for a {item_type} listing.

TYPE FOCUS:
{type_hint}

FIELDS (set to null if confidence < 80%):
{fields_text}

RULES:
1. Extract ONLY information explicitly stated on the page
2. Do NOT infer from context or general knowledge
3. If conflicting values, prefer the most specific/recent

CALIBRATION: If < 80% confident a value is correct, set to null."""


def build_location_normalization_prompt() -> str:
    return """You are a travel location normalization service.

TASK: Normalize user-provided origin and destination to improve travel search quality.

STEPS:
1. Expand abbreviations to full city names (e.g., "SF" → "San Francisco, CA", "NYC" → "New York, NY").
2. Identify the PRIMARY international airport code (IATA) for the city if not specified (e.g., "Seoul" → "ICN", "London" → "LHR").
3. If user provides a specific code, use that (e.g., "LGA" → code: "LGA").

RULES:
- origin_city/destination_city: Full canonical city name (City, State/Country). No airport codes here.
- origin_code/destination_code: The 3-letter IATA code. 
  - If user input is a city, infer the MAIN international airport.
  - If user input is a code, use that code.
- confidence: 
  - "high": Clear city or code (e.g. "Seoul", "JFK", "San Francisco").
  - "medium": Ambiguous but likely (e.g. "Paris" -> CDG, but could be ORY).
  - "low": Unintelligible input.

EXAMPLES:
Input: "SF" → origin_city: "San Francisco, CA, USA", origin_code: "SFO"
Input: "NYC" → origin_city: "New York, NY, USA", origin_code: "JFK"
Input: "Seoul" → destination_city: "Seoul, South Korea", destination_code: "ICN"
Input: "GMP" → destination_city: "Seoul, South Korea", destination_code: "GMP"
Input: "London" → destination_city: "London, UK", destination_code: "LHR"
"""


def build_enrichment_query_prompt() -> str:
    return """ROLE: You are a search query specialist. Given items with missing data fields, generate targeted search queries to find the missing information.

TASK: For each item, create ONE precise search query that is most likely to surface the missing fields.

OUTPUT RULES:
- MUST give at least 3 search queries
- Make sure each query target DISTINCT missing fields


Steps:
1. Include the item name and city in every query
2. Add field-specific keywords:
   - menu_url/reservation_url → "menu" "reservations" "opentable" "resy"
   - operating_hours → "hours" "open" "schedule"
   - admission_price → "tickets" "admission" "price"
   - price_per_night → "rate" "price per night" "booking"
   - price_per_day → "rental rate" "daily price"
   - price_range → "price" "fare" "cost"
3. Keep queries concise (under 15 words)
4. Use quotes around the item name for exact matching"""


def build_report_prompt(
    *,
    destination: str,
    departing_date: str,
    returning_date: str | None,
    stay_nights: int | None,
) -> str:
    duration = f"{stay_nights} nights" if stay_nights else "flexible duration"
    return_info = f"Return: {returning_date}" if returning_date else "One-way trip"

    return f"""ROLE: You are a travel planning expert synthesizing research into a concise trip summary.

TASK: Estimate the total trip budget for {destination}.

CONTEXT:
- Departure: {departing_date}
- {return_info}
- Duration: {duration}

OUTPUT:
- Calculate total_estimated_budget for the trip based on available prices
- Include transport, accommodation, dining, and attraction costs
- If prices are missing, note "Partial estimate" and sum available prices only

RULES:
- Use ONLY price data from the provided items — do not invent prices
- Format as a dollar amount (e.g., "$1,200 - $1,800")"""


def build_recommendation_prompt(
    *,
    origin: str,
    departing_date: str,
    returning_date: str | None,
    vibe: str,
    budget: str,
    climate: str,
) -> str:
    month = departing_date[5:7] if len(departing_date) >= 7 else "unknown"
    month_names = {
        "01": "January", "02": "February", "03": "March", "04": "April",
        "05": "May", "06": "June", "07": "July", "08": "August",
        "09": "September", "10": "October", "11": "November", "12": "December",
    }
    month_name = month_names.get(month, month)
    return_info = f"Return: {returning_date}" if returning_date else "One-way / flexible return"

    return f"""ROLE: You are an expert travel advisor who recommends ideal destinations based on traveler preferences.

TASK: Recommend exactly 1 destination for a traveler departing from {origin}.

TRAVELER PREFERENCES:
- Trip Vibe: {vibe}
- Budget: {budget}
- Climate: {climate}

TRAVEL DATES:
- Departing: {departing_date} ({month_name})
- {return_info}

CALIBRATION:
- "Adventure" → hiking, outdoor sports, national parks, diving, trekking
- "Culture & History" → museums, historic sites, UNESCO heritage, local traditions
- "Beach & Relaxation" → coastal resorts, islands, spa retreats, tropical getaways
- "Food & Nightlife" → culinary capitals, street food scenes, bar districts, food tours
- "Budget-friendly" → destinations with low cost of living, hostels, street food
- "Mid-range" → comfortable hotels, mix of dining options, moderate prices
- "Luxury" → 5-star resorts, fine dining, premium experiences
- "Warm" → tropical/subtropical, 25-35°C expected
- "Moderate" → temperate, 15-25°C expected
- "Cold" → winter destinations, skiing, northern climates, under 10°C

SEASONALITY: Consider weather conditions in {month_name} at the destination. Avoid recommending destinations during their rainy/monsoon/extreme seasons unless the traveler explicitly prefers that.

RULES:
1. Recommend a destination that is DIFFERENT from {origin}
2. The destination MUST include the primary airport code in parentheses, e.g. "Tokyo (NRT)", "Barcelona (BCN)"
3. Provide 2-3 sentences explaining why this destination perfectly matches the preferences
4. Consider flight accessibility from {origin}
5. Factor in seasonality — the destination should have good conditions in {month_name}"""


TYPE_HINTS: dict[str, str] = {
    "restaurant": "Focus on: menu URL, reservation URL, menu price range, operating hours, phone, full address, reservation policy",
    "attraction": "Focus on: admission/ticket price, visiting hours, phone, full address",
    "hotel": "Focus on: nightly room rate, parking policy/details, check-in/out times, phone, full address",
    "car_rental": "Focus on: daily rental rate, vehicle class, pickup location, operating hours",
    "flight": "Focus on: fare/ticket price, airline name, route, flight duration",
}
