/** Shared TypeScript interfaces for the Spot On frontend.
 */

export interface Restaurant {
  id: string;
  name: string;
  cuisine: string | null;
  area?: string;
  operating_hours?: string | null;
  price_range?: string;
  url: string;
  menu_url?: string | null;
  reservation_url?: string | null;
  snippet?: string;
  why_recommended?: string;
  rating?: number | null;
  tags?: string[];
}

export interface TravelSpot {
  id: string;
  name: string;
  kind: string | null;
  area?: string;
  operating_hours?: string | null;
  url: string;
  reservation_url?: string | null;
  admission_price?: string | null;
  snippet?: string;
  why_recommended?: string;
  estimated_duration_min?: number;
}

export interface Hotel {
  id: string;
  name: string;
  area?: string;
  price_per_night?: string;
  url: string;
  snippet?: string;
  why_recommended?: string;
  amenities?: string[];
}

export interface CarRental {
  id: string;
  provider: string;
  vehicle_class?: string | null;
  price_per_day?: string;
  pickup_location?: string;
  operating_hours?: string | null;
  url: string;
  why_recommended?: string;
}

export interface Flight {
  id: string;
  airline?: string;
  route: string;
  trip_type: "one-way" | "round-trip";
  price_range?: string;
  url: string;
  snippet?: string;
  why_recommended?: string;
}

export interface Reference {
  title?: string;
  url: string;
  content?: string;
  section: string;
}

export interface ItinerarySlot {
  time_of_day: "morning" | "afternoon" | "evening";
  activity: string;
  item_name: string;
  item_type: "restaurant" | "attraction" | "hotel" | "transport";
  estimated_cost: string | null;
}

export interface ItineraryDay {
  day_number: number;
  date: string;
  slots: ItinerarySlot[];
  daily_total: string;
}

export interface TravelReport {
  flight_summary: Record<string, string>[];
  car_rental_summary: Record<string, string>[];
  hotel_summary: Record<string, string>[];
  attraction_summary: Record<string, string>[];
  restaurant_summary: Record<string, string>[];
  itinerary: ItineraryDay[];
  total_estimated_budget: string;
}

export interface SpotOnResults {
  restaurants?: Restaurant[];
  travel_spots?: TravelSpot[];
  hotels?: Hotel[];
  car_rentals?: CarRental[];
  flights?: Flight[];
  constraints?: Record<string, unknown>;
  references?: Reference[];
  report?: TravelReport;
}

export interface RunProgress {
  nodes?: Record<string, NodeEventPayload>;
}

export interface RunError {
  message: string;
}

export interface RunResponse {
  runId: string;
  status: string;
  updatedAt: string;
  progress?: RunProgress;
  constraints?: Record<string, unknown>;
  final_output?: SpotOnResults;
  warnings?: string[];
  error?: RunError;
  durationMs?: number;
}

export type NodeStatus = "start" | "end" | "error";

export interface NodeEventPayload {
  node: string;
  status: NodeStatus;
  message?: string;
  durationMs?: number;
  error?: string;
}

export interface LogEventPayload {
  message?: string;
}

export interface ArtifactEventPayload {
  type: string;
  payload: Record<string, unknown>;
}
