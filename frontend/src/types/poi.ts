/**
 * POI (Point of Interest) types for the Phoenix AI Travel Companion.
 */

/**
 * Brief POI information returned by the API.
 */
export interface POI {
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
 * API response for nearby POIs query.
 */
export interface NearbyPOIsRequest {
  latitude: number;
  longitude: number;
  radius?: number; // km
  categories?: string[];
  limit?: number;
}

/**
 * POI display data for the map.
 */
export interface POIDisplayData {
  id: string;
  name: string;
  x: number;
  y: number;
  size: "lg" | "md" | "sm";
  vibe: "hot" | "warm" | "cool";
  categories: string[];
  rating?: number;
}

/**
 * User location on the map.
 */
export interface UserLocation {
  latitude: number;
  longitude: number;
}

/**
 * Convert POI categories to vibe mapping.
 */
export function categoryToVibe(categories: string[]): "hot" | "warm" | "cool" {
  const lowerCategories = categories.map((c) => c.toLowerCase());

  // Hot: Food, cafes, bars, entertainment
  if (lowerCategories.some((c) => ["food", "restaurant", "cafe", "bar", "nightlife", "entertainment"].includes(c))) {
    return "hot";
  }

  // Warm: Art, museums, history, culture
  if (lowerCategories.some((c) => ["art", "museum", "gallery", "history", "culture", "monument", "church"].includes(c))) {
    return "warm";
  }

  // Cool: Parks, nature, shopping
  if (lowerCategories.some((c) => ["park", "nature", "garden", "shopping", "market"].includes(c))) {
    return "cool";
  }

  return "warm"; // Default
}

/**
 * Convert POI rating to size mapping.
 */
export function ratingToSize(rating: number | null): "lg" | "md" | "sm" {
  if (!rating) return "sm";
  if (rating >= 4.5) return "lg";
  if (rating >= 4.0) return "md";
  return "sm";
}

/**
 * API base URL for POI endpoints.
 */
export const POI_API_BASE = "/api/v1/poi";
