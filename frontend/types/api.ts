/** Shared TypeScript interfaces for the Spot On frontend. */

export interface Restaurant {
  id: string;
  name: string;
  cuisine: string | null;
  area?: string;
  price_range?: string;
  menu_url?: string | null;
  reservation_url?: string | null;
  url: string;
  snippet?: string;
  why_recommended?: string;
  tags?: string[];
  rating?: number;
  hours_text?: string;
  phone?: string;
  address?: string;
  price_hint?: string;
  reservation_required?: boolean;
}

export interface TravelSpot {
  id: string;
  name: string;
  kind: string | null;
  area?: string;
  url: string;
  snippet?: string;
  why_recommended?: string;
  estimated_duration_min?: number;
  hours_text?: string;
  price_hint?: string;
  admission_price?: string | null;
  reservation_required?: boolean;
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
  phone?: string;
  address?: string;
  parking_details?: string | null;
}

export interface CarRental {
  id: string;
  provider: string;
  vehicle_class?: string | null;
  price_per_day?: string;
  pickup_location?: string;
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

export interface SpotOnResults {
  restaurants?: Restaurant[];
  travel_spots?: TravelSpot[];
  hotels?: Hotel[];
  car_rentals?: CarRental[];
  flights?: Flight[];
  constraints?: Record<string, unknown>;
  references?: Reference[];
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
