/**
 * Route types for the Phoenix AI Travel Companion.
 */

/**
 * POI brief information within a route.
 */
export interface RoutePOI {
  id: string;
  name: string;
  categories: string[];
  latitude: number;
  longitude: number;
  rating: number | null;
  price_level: number | null;
  estimated_duration_minutes: number | null;
}

/**
 * A single stop in a route.
 */
export interface RouteStop {
  sequence_order: number;
  poi: RoutePOI;
  estimated_arrival_time: string | null;
  estimated_departure_time: string | null;
  estimated_duration_minutes: number | null;
  distance_from_previous_km: number | null;
  travel_time_minutes: number | null;
  transport_mode: string | null;
}

/**
 * Complete route response from the API.
 */
export interface RouteResponse {
  id: string;
  title: string | null;
  description: string | null;
  status: string;
  stops: RouteStop[];
  total_distance_km: number | null;
  total_duration_minutes: number | null;
  estimated_start_time: string | null;
  estimated_end_time: string | null;
  satisfaction_score: number | null;
  optimization_version: number | null;
  created_at: string;
}

/**
 * Request to generate a new route.
 */
export interface RouteGenerateRequest {
  start_location: {
    latitude: number;
    longitude: number;
    address?: string;
    city?: string;
    country?: string;
  };
  end_location?: {
    latitude: number;
    longitude: number;
    address?: string;
    city?: string;
    country?: string;
  };
  start_time?: string;
  end_time?: string;
  max_duration_minutes?: number;
  max_distance_km?: number;
  preferred_categories?: string[];
  excluded_categories?: string[];
  transport_mode?: "walking" | "driving" | "transit" | "cycling";
  include_pois?: string[];
  exclude_pois?: string[];
  optimize_for?: "time" | "distance" | "satisfaction" | "variety";
}

/**
 * Stop display data for the UI.
 */
export interface StopDisplayData {
  sequence_order: number;
  title: string;
  subtitle: string;
  time: string;
  image?: string;
  vibe: string;
  vibeColor: string;
  x: number;
  y: number;
  latitude: number;
  longitude: number;
  icon: "Coffee" | "Palette" | "ShoppingBag" | "MapPin" | "Camera";
  estimated_duration_minutes?: number;
}

/**
 * Convert POI categories to icon type.
 */
export function categoryToIcon(categories: string[]): "Coffee" | "Palette" | "ShoppingBag" | "MapPin" | "Camera" {
  const lowerCategories = categories.map((c) => c.toLowerCase());

  if (lowerCategories.some((c) => ["food", "cafe", "restaurant", "bar", "coffee"].includes(c))) {
    return "Coffee";
  }
  if (lowerCategories.some((c) => ["art", "museum", "gallery", "culture"].includes(c))) {
    return "Palette";
  }
  if (lowerCategories.some((c) => ["shopping", "market", "store"].includes(c))) {
    return "ShoppingBag";
  }
  if (lowerCategories.some((c) => ["monument", "landmark", "historical"].includes(c))) {
    return "Camera";
  }
  return "MapPin";
}

/**
 * Generate subtitle from POI data.
 */
export function generateSubtitle(poi: RoutePOI): string {
  const categories = poi.categories.slice(0, 2).join(", ");
  return categories.charAt(0).toUpperCase() + categories.slice(1) || "Point of Interest";
}

/**
 * API base URL for route endpoints.
 */
export const ROUTE_API_BASE = "/api/v1/routes";
