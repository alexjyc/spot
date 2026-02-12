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

export interface TravelReport {
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
}

export type NodeStatus = "start" | "end" | "error";

export interface NodeEventPayload {
  node: string;
  status: NodeStatus;
  message?: string;
  error?: string;
}

export interface RecommendedDestination {
  destination: string;
  reasoning: string;
}

export interface LogEventPayload {
  message?: string;
}

export interface ArtifactEventPayload {
  type: string;
  payload: Record<string, unknown>;
}
