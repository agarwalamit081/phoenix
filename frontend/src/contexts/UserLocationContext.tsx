/**
 * User Location Context
 *
 * This context manages the user's current location (city, coordinates, bounds)
 * which is set dynamically from voice input or user preferences.
 */

import { createContext, useContext, useState, ReactNode } from "react";

export interface LatLngBounds {
  minLat: number;
  maxLat: number;
  minLng: number;
  maxLng: number;
}

export interface UserLocation {
  city: string;
  country: string;
  latitude: number;
  longitude: number;
  bounds: LatLngBounds;
  timezone: string;
}

interface UserLocationContextType {
  userLocation: UserLocation | null;
  setLocation: (location: UserLocation) => void;
  updateCity: (city: string, country?: string) => void;
  updateCoordinates: (latitude: number, longitude: number) => void;
  clearLocation: () => void;
}

const UserLocationContext = createContext<UserLocationContextType | undefined>(undefined);

// Predefined bounds for common cities (can be extended)
const CITY_BOUNDS: Record<string, { bounds: LatLngBounds; timezone: string }> = {
  "Paris": {
    bounds: { minLat: 48.81, maxLat: 48.90, minLng: 2.25, maxLng: 2.42 },
    timezone: "Europe/Paris",
  },
  "London": {
    bounds: { minLat: 51.40, maxLat: 51.60, minLng: -0.25, maxLng: 0.10 },
    timezone: "Europe/London",
  },
  "New York": {
    bounds: { minLat: 40.65, maxLat: 40.85, minLng: -74.05, maxLng: -73.85 },
    timezone: "America/New_York",
  },
  "Tokyo": {
    bounds: { minLat: 35.55, maxLat: 35.80, minLng: 139.65, maxLng: 139.90 },
    timezone: "Asia/Tokyo",
  },
  "Rome": {
    bounds: { minLat: 41.80, maxLat: 42.00, minLng: 12.40, maxLng: 12.60 },
    timezone: "Europe/Rome",
  },
  "Barcelona": {
    bounds: { minLat: 41.35, maxLat: 41.45, minLng: 2.10, maxLng: 2.25 },
    timezone: "Europe/Madrid",
  },
  "Amsterdam": {
    bounds: { minLat: 52.30, maxLat: 52.42, minLng: 4.80, maxLng: 5.00 },
    timezone: "Europe/Amsterdam",
  },
  "Berlin": {
    bounds: { minLat: 52.45, maxLat: 52.55, minLng: 13.30, maxLng: 13.50 },
    timezone: "Europe/Berlin",
  },
};

/**
 * Calculate bounds from center coordinates (for cities not predefined)
 * Creates a ~0.2 degree bounding box around the center point
 */
function calculateBoundsFromCenter(lat: number, lng: number): LatLngBounds {
  const latDelta = 0.10; // ~11km
  const lngDelta = 0.10; // varies by latitude, ~8km at this latitude
  return {
    minLat: lat - latDelta,
    maxLat: lat + latDelta,
    minLng: lng - lngDelta,
    maxLng: lng + lngDelta,
  };
}

/**
 * Guess city from coordinates and provide defaults
 */
function guessLocationFromCoords(lat: number, lng: number): Partial<UserLocation> {
  // Simple coordinate matching for common cities
  // In production, this would use a reverse geocoding API
  const cities = [
    { name: "Paris", country: "France", lat: 48.8566, lng: 2.3522 },
    { name: "London", country: "United Kingdom", lat: 51.5074, lng: -0.1278 },
    { name: "New York", country: "United States", lat: 40.7128, lng: -74.0060 },
    { name: "Tokyo", country: "Japan", lat: 35.6762, lng: 139.6503 },
    { name: "Rome", country: "Italy", lat: 41.9028, lng: 12.4964 },
    { name: "Barcelona", country: "Spain", lat: 41.3851, lng: 2.1734 },
    { name: "Amsterdam", country: "Netherlands", lat: 52.3676, lng: 4.9041 },
    { name: "Berlin", country: "Germany", lat: 52.5200, lng: 13.4050 },
  ];

  // Find closest city within 0.5 degrees (~55km)
  for (const city of cities) {
    const distance = Math.sqrt(Math.pow(lat - city.lat, 2) + Math.pow(lng - city.lng, 2));
    if (distance < 0.5) {
      const cityData = CITY_BOUNDS[city.name];
      return {
        city: city.name,
        country: city.country,
        latitude: city.lat,
        longitude: city.lng,
        bounds: cityData?.bounds || calculateBoundsFromCenter(city.lat, city.lng),
        timezone: cityData?.timezone || "UTC",
      };
    }
  }

  // Default fallback
  return {
    city: "Unknown",
    country: "",
    bounds: calculateBoundsFromCenter(lat, lng),
    timezone: "UTC",
  };
}

interface UserLocationProviderProps {
  children: ReactNode;
  defaultCity?: string;
  defaultCountry?: string;
}

export function UserLocationProvider({
  children,
  defaultCity = "Paris",
  defaultCountry = "France",
}: UserLocationProviderProps) {
  const [userLocation, setUserLocation] = useState<UserLocation | null>(() => {
    // Initialize with default city
    const cityData = CITY_BOUNDS[defaultCity];
    if (cityData) {
      return {
        city: defaultCity,
        country: defaultCountry,
        latitude: (cityData.bounds.minLat + cityData.bounds.maxLat) / 2,
        longitude: (cityData.bounds.minLng + cityData.bounds.maxLng) / 2,
        bounds: cityData.bounds,
        timezone: cityData.timezone,
      };
    }
    return null;
  });

  const setLocation = (location: UserLocation) => {
    setUserLocation(location);
  };

  const updateCity = (city: string, country?: string) => {
    const cityData = CITY_BOUNDS[city];
    if (cityData) {
      setUserLocation({
        city,
        country: country || "",
        latitude: (cityData.bounds.minLat + cityData.bounds.maxLat) / 2,
        longitude: (cityData.bounds.minLng + cityData.bounds.maxLng) / 2,
        bounds: cityData.bounds,
        timezone: cityData.timezone,
      });
    }
  };

  const updateCoordinates = (latitude: number, longitude: number) => {
    const guessed = guessLocationFromCoords(latitude, longitude);
    setUserLocation({
      city: guessed.city || "Unknown",
      country: guessed.country || "",
      latitude,
      longitude,
      bounds: guessed.bounds || calculateBoundsFromCenter(latitude, longitude),
      timezone: guessed.timezone || "UTC",
    });
  };

  const clearLocation = () => {
    setUserLocation(null);
  };

  return (
    <UserLocationContext.Provider
      value={{
        userLocation,
        setLocation,
        updateCity,
        updateCoordinates,
        clearLocation,
      }}
    >
      {children}
    </UserLocationContext.Provider>
  );
}

export function useUserLocation(): UserLocationContextType {
  const context = useContext(UserLocationContext);
  if (context === undefined) {
    throw new Error("useUserLocation must be used within a UserLocationProvider");
  }
  return context;
}
