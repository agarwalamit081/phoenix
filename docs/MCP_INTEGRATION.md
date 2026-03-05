# MCP (Model Context Protocol) Integration

This document describes how Phoenix AI Travel Companion integrates with Google Maps via Composio MCP.

## Overview

Phoenix uses the **Model Context Protocol (MCP)** to integrate with Google Maps for:
- Geocoding (address → coordinates)
- Reverse geocoding (coordinates → address)
- Place search and details
- Distance matrix calculation
- Directions and route optimization

## Configuration

### MCP Server Setup

The MCP server is configured at:
```
platform.composio.dev/ (mcp-config-ejbf90)
```

### Environment Variables

Add to your `.env` file:

```bash
# Map Integration via MCP
MAP_PROVIDER=mcp
MCP_SERVER_URL=http://localhost:3000/mcp

# Fallback: Direct Google Maps API (if MCP unavailable)
GOOGLE_MAPS_API_KEY=your_google_maps_api_key
```

## Architecture

```
┌─────────────────┐
│   Phoenix API    │
│                 │
│  Maps Service   │
└────────┬────────┘
         │
         ├── MCP Client ──┐
         │               │
         └───────────────┴── Composio MCP Server
                                  │
                                  ▼
                         Google Maps API
```

## Usage

### 1. Geocoding

```python
from src.services.map_service import MapService

map_service = MapService()
location = await map_service.geocode("Eiffel Tower, Paris")
# Returns: {"latitude": 48.8584, "longitude": 2.2945, "address": "..."}
```

### 2. Place Search

```python
places = await map_service.search_places(
    query="museums in Paris",
    radius=5000,
    types=["museum"]
)
```

### 3. Distance Matrix

```python
distances = await map_service.get_distance_matrix(
    origins=[{"lat": 48.8566, "lng": 2.3522}],
    destinations=[
        {"lat": 48.8584, "lng": 2.2945},  # Eiffel Tower
        {"lat": 48.8606, "lng": 2.3376}   # Louvre
    ],
    mode="walking"
)
```

### 4. Directions

```python
route = await map_service.get_directions(
    origin={"lat": 48.8566, "lng": 2.3522},
    destination={"lat": 48.8584, "lng": 2.2945},
    mode="walking",
    alternatives=False
)
```

## MCP Tools Available

The following MCP tools are exposed:

1. **maps_geocode** - Convert addresses to coordinates
2. **maps_reverse_geocode** - Convert coordinates to addresses
3. **maps_search_places** - Search for places
4. **maps_place_details** - Get detailed information about a place
5. **maps_distance_matrix** - Calculate distances between multiple points
6. **maps_directions** - Get turn-by-turn directions
7. **maps_static_map** - Generate static map images

## Fallback Behavior

If the MCP server is unavailable, Phoenix will:
1. Log a warning
2. Attempt to use the direct Google Maps API key (if configured)
3. Return a graceful error if both are unavailable

## Development Setup

### Local MCP Server Testing

1. Start the MCP server:
```bash
# Using Composio CLI
composio mcp start google-maps
```

2. Verify connection:
```bash
curl http://localhost:3000/mcp/health
```

3. Test integration:
```python
import httpx

async def test_mcp_connection():
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{settings.mcp_server_url}/tools/maps_geocode",
            params={"address": "Eiffel Tower"}
        )
        return response.json()
```

## Production Deployment

### Docker Compose

```yaml
services:
  phoenix:
    environment:
      - MAP_PROVIDER=mcp
      - MCP_SERVER_URL=http://mcp-server:3000/mcp
    depends_on:
      - mcp-server

  mcp-server:
    image: composio/mcp-google-maps:latest
    environment:
      - GOOGLE_MAPS_API_KEY=${GOOGLE_MAPS_API_KEY}
    ports:
      - "3000:3000"
```

### Kubernetes

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: phoenix-config
data:
  MAP_PROVIDER: "mcp"
  MCP_SERVER_URL: "http://mcp-service:3000/mcp"
---
apiVersion: v1
kind: Service
metadata:
  name: mcp-service
spec:
  selector:
    app: mcp-google-maps
  ports:
  - port: 3000
```

## Troubleshooting

### Issue: MCP server unreachable

**Symptoms**:
- Timeout when calling map functions
- Error: "Failed to connect to MCP server"

**Solutions**:
1. Check MCP server is running: `curl http://localhost:3000/mcp/health`
2. Verify `MCP_SERVER_URL` in `.env`
3. Check network/firewall settings

### Issue: Rate limiting

**Symptoms**:
- 429 Too Many Requests errors
- Slow responses

**Solutions**:
1. Implement caching for frequently queried locations
2. Add exponential backoff for retries
3. Consider upgrading MCP server plan

### Issue: Invalid API responses

**Symptoms**:
- Malformed JSON responses
- Missing expected fields

**Solutions**:
1. Check MCP server logs
2. Verify Google Maps API quota
3. Test with direct Google Maps API key

## Performance Considerations

1. **Caching Strategy**:
   - Cache geocoding results for 24 hours
   - Cache place details for 7 days
   - Cache static map images for 30 days

2. **Rate Limits**:
   - Google Maps Free Tier: 50 requests/second
   - Consider upgrading for production workloads
   - Implement request queuing for batch operations

3. **Cost Optimization**:
   - Use MCP to centralize API calls
   - Batch geocoding requests where possible
   - Pre-fetch popular locations

## Security Notes

1. Never commit API keys to version control
2. Use environment variables for all credentials
3. Rotate API keys regularly
4. Monitor usage for anomalies
5. Set up alerts for quota exhaustion

## References

- [Composio MCP Documentation](https://composio.dev/docs)
- [Google Maps API Documentation](https://developers.google.com/maps)
- [MCP Specification](https://modelcontextprotocol.io/)
