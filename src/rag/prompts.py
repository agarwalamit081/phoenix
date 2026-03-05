"""RAG prompts for generating responses."""

from typing import Any


def get_system_prompt() -> str:
    """Get system prompt for RAG responses.

    Returns:
        System prompt string
    """
    return """You are Phoenix, an AI travel companion for the Phoenix AI Travel Companion application. Your role is to help users plan their travels, discover places of interest, and get personalized recommendations.

## Key Capabilities

- Provide travel advice and recommendations
- Help users discover attractions, restaurants, and activities
- Assist with route planning and itineraries
- Offer personalized suggestions based on user preferences
- Answer questions about destinations, activities, and logistics

## Guidelines

- Be helpful, friendly, and informative
- Use the provided context to give accurate, specific answers
- When context is insufficient, acknowledge limitations clearly
- Prioritize user safety and practical considerations
- Consider accessibility and family-friendly options when relevant
- Provide specific, actionable recommendations
- Include relevant details like hours, pricing, and tips when available
- Suggest alternatives or similar options when appropriate

## Tone and Style

- Conversational but professional
- Enthusiastic about travel and discovery
- Clear and concise in explanations
- Respectful of user preferences and constraints
- Honest about uncertainties or limitations

## Response Structure

1. Direct answer to the question
2. Supporting details from context
3. Practical tips or considerations
4. Alternative suggestions if applicable
5. Follow-up questions to help clarify needs

Remember: Your goal is to make travel planning easier and more enjoyable while providing accurate, helpful information."""


def get_travel_advice_prompt(
    query: str,
    context: list[dict[str, Any]],
) -> str:
    """Get prompt for travel advice.

    Args:
        query: User query
        context: Retrieved context

    Returns:
        Prompt string
    """
    context_str = _format_context(context)

    return f"""I need travel advice based on the following information.

{context_str}

**Question:** {query}

Please provide helpful travel advice based on the context above. Include:
- A direct answer to the question
- Relevant details from the provided information
- Practical considerations or tips
- Any alternatives or options worth considering

If the context doesn't fully address the question, please let me know what additional information would be helpful."""


def get_poi_recommendation_prompt(
    query: str,
    context: list[dict[str, Any]],
) -> str:
    """Get prompt for POI recommendations.

    Args:
        query: User query
        context: Retrieved context

    Returns:
        Prompt string
    """
    context_str = _format_poi_context(context)

    return f"""I'm looking for recommendations for places to visit.

{context_str}

**Request:** {query}

Please provide personalized recommendations including:
- Top suggestions that match the request
- Brief description of why each place is recommended
- Key details (hours, pricing, highlights)
- Any practical tips for visiting

Organize the recommendations in order of relevance, and explain why each place might be a good fit."""


def get_route_planning_prompt(
    query: str,
    context: list[dict[str, Any]],
) -> str:
    """Get prompt for route planning.

    Args:
        query: User query
        context: Retrieved context

    Returns:
        Prompt string
    """
    context_str = _format_route_context(context)

    return f"""I need help planning a travel route.

{context_str}

**Request:** {query}

Please provide route planning advice including:
- Suggested itinerary or route structure
- Optimal ordering of stops
- Time estimates and logistics
- Transportation recommendations
- Things to consider (timing, distances, etc.)

If route information is provided in the context, reference it directly. Otherwise, provide general guidance based on the locations mentioned."""


def get_comparison_prompt(
    query: str,
    context: list[dict[str, Any]],
) -> str:
    """Get prompt for comparisons.

    Args:
        query: User query
        context: Retrieved context

    Returns:
        Prompt string
    """
    context_str = _format_context(context)

    return f"""I need to compare options for my trip.

{context_str}

**Question:** {query}

Please provide a helpful comparison including:
- Key differences between the options
- Pros and cons of each
- When each option might be preferable
- Any other factors to consider

Present the comparison clearly, helping me understand which option might be best for my situation."""


def get_general_prompt(
    query: str,
    context: list[dict[str, Any]],
) -> str:
    """Get general prompt.

    Args:
        query: User query
        context: Retrieved context

    Returns:
        Prompt string
    """
    context_str = _format_context(context)

    return f"""Based on the following information, please answer my question.

{context_str}

**Question:** {query}

Please provide a helpful response based on the context above. If the context doesn't contain enough information, please acknowledge this and suggest what would be helpful."""


def _format_context(context: list[dict[str, Any]]) -> str:
    """Format general context.

    Args:
        context: Context documents

    Returns:
        Formatted context string
    """
    if not context:
        return "No additional context available."

    parts = []

    for i, doc in enumerate(context[:6], 1):
        doc_type = doc.get("type", "information")
        content = doc.get("content", "")

        if content:
            source = doc.get("source", "knowledge base")
            parts.append(
                f"[Source {i}] ({doc_type} from {source}):\n{content[:400]}"
            )

    return "\n\n".join(parts)


def _format_poi_context(context: list[dict[str, Any]]) -> str:
    """Format POI context.

    Args:
        context: Context documents

    Returns:
        Formatted POI context string
    """
    if not context:
        return "No place information available."

    parts = []

    for i, doc in enumerate(context[:8], 1):
        if doc.get("type") == "poi" or doc.get("source") in ["poi_search", "vector"]:
            metadata = doc.get("metadata", {})
            name = metadata.get("name") or doc.get("title", "Unknown Place")
            category = metadata.get("category", "attraction")
            content = doc.get("content", "")
            rating = metadata.get("rating")

            rating_str = f" ({rating}/5)" if rating else ""

            parts.append(
                f"[{i}] **{name}** - {category}{rating_str}\n{content[:200]}"
            )
        else:
            content = doc.get("content", "")
            if content:
                parts.append(f"[{i}] {content[:300]}")

    return "\n\n".join(parts) if parts else "No specific places found in context."


def _format_route_context(context: list[dict[str, Any]]) -> str:
    """Format route context.

    Args:
        context: Context documents

    Returns:
        Formatted route context string
    """
    if not context:
        return "No route information available."

    parts = []

    for i, doc in enumerate(context[:5], 1):
        if doc.get("type") == "route":
            metadata = doc.get("metadata", {})
            total_pois = metadata.get("total_pois", 0)
            distance = metadata.get("estimated_distance_km")
            duration = metadata.get("estimated_duration_minutes")

            route_info = f"Route with {total_pois} stops"
            if distance:
                route_info += f" covering {distance:.1f}km"
            if duration:
                hours = int(duration // 60)
                mins = int(duration % 60)
                route_info += f" (~{hours}h {mins}mins)"

            parts.append(f"[{i}] {route_info}")

            # Add POIs if available
            content = doc.get("content", "")
            if content:
                parts.append(f"    {content[:300]}")
        else:
            content = doc.get("content", "")
            if content:
                parts.append(f"[{i}] {content[:300]}")

    return "\n\n".join(parts) if parts else "No route details available in context."


def get_conversation_followup_prompt(
    conversation_summary: str,
    new_query: str,
    context: list[dict[str, Any]] | None = None,
) -> str:
    """Get prompt for conversation follow-up.

    Args:
        conversation_summary: Summary of previous conversation
        new_query: New user query
        context: Optional new context

    Returns:
        Prompt string
    """
    context_str = ""

    if context:
        context_str = f"\nAdditional context:\n{_format_context(context)}"

    return f"""We've been discussing travel plans. Here's what we've covered so far:

{conversation_summary}

{context_str}

**New question:** {new_query}

Please continue the conversation naturally, referencing our previous discussion when relevant. Provide a helpful response that builds on what we've already discussed."""


def get_clarification_prompt(
    original_query: str,
    missing_information: list[str],
) -> str:
    """Get prompt for asking clarification.

    Args:
        original_query: Original user query
        missing_information: List of missing info

        Returns:
        Prompt string
    """
    missing_str = "\n".join(f"- {info}" for info in missing_information)

    return f"""The user asked: "{original_query}"

To provide the best recommendations, I need to clarify:

{missing_str}

Could you please provide these details? This will help me give you more personalized and useful recommendations."""


def get_fallback_prompt(query: str) -> str:
    """Get fallback prompt when context is insufficient.

    Args:
        query: User query

    Returns:
        Fallback prompt string
    """
    return f"""The user asked: "{query}"

I don't have specific information in my current knowledge base to fully answer this question. Please:

1. Acknowledge what you understood from their question
2. Explain what specific information would help you provide a better answer
3. Offer general guidance or suggest alternatives if possible
4. Ask clarifying questions to better understand their needs

Be helpful while being honest about the limitations of your current knowledge."""


def get_multi_day_itinerary_prompt(
    days: int,
    location: str,
    context: list[dict[str, Any]],
) -> str:
    """Get prompt for multi-day itinerary.

    Args:
        days: Number of days
        location: Location name
        context: Retrieved context

    Returns:
        Prompt string
    """
    context_str = _format_context(context)

    return f"""Create a {days}-day itinerary for {location}.

{context_str}

Please provide:
- Day-by-day breakdown with suggested activities
- Logical grouping of nearby attractions
- Time estimates for each activity
- Transportation recommendations between locations
- Meal suggestions
- Tips for maximizing time

Make it practical and realistic, considering travel time and operating hours."""


def get_budget_conscious_prompt(
    query: str,
    budget: str,
    context: list[dict[str, Any]],
) -> str:
    """Get prompt for budget-conscious recommendations.

    Args:
        query: User query
        budget: Budget constraint
        context: Retrieved context

    Returns:
        Prompt string
    """
    context_str = _format_context(context)

    return f"""I'm traveling on a {budget} budget.

{context_str}

**Request:** {query}

Please focus on:
- Free or low-cost activities
- Budget-friendly dining options
- Money-saving tips
- Value-for-money recommendations
- What's worth spending on vs. what to skip

Be practical and realistic about costs while still providing great experiences."""


def get_family_friendly_prompt(
    query: str,
    family_details: str,
    context: list[dict[str, Any]],
) -> str:
    """Get prompt for family-friendly recommendations.

    Args:
        query: User query
        family_details: Family composition
        context: Retrieved context

    Returns:
        Prompt string
    """
    context_str = _format_context(context)

    return f"""I'm traveling with my family: {family_details}

{context_str}

**Request:** {query}

Please recommend:
- Family-appropriate activities and attractions
- Kid-friendly dining options
- Stroller/wheelchair accessibility considerations
- Places with facilities for families
- Activities that engage different age groups

Consider safety, convenience, and what will keep everyone entertained."""


def get_accessibility_prompt(
    query: str,
    accessibility_needs: str,
    context: list[dict[str, Any]],
) -> str:
    """Get prompt for accessibility-focused recommendations.

    Args:
        query: User query
        accessibility_needs: Accessibility requirements
        context: Retrieved context

    Returns:
        Prompt string
    """
    context_str = _format_context(context)

    return f"""I have the following accessibility needs: {accessibility_needs}

{context_str}

**Request:** {query}

Please focus on:
- Wheelchair accessible locations
- Transportation options that accommodate my needs
- Accessible restrooms and facilities
- Reserved seating or accommodation options
- Any accessibility considerations to be aware of

Be specific about accessibility features where information is available."""


def get_seasonal_prompt(
    query: str,
    season: str,
    year: str,
    context: list[dict[str, Any]],
) -> str:
    """Get prompt for seasonal recommendations.

    Args:
        query: User query
        season: Season of travel
        year: Year of travel
        context: Retrieved context

    Returns:
        Prompt string
    """
    context_str = _format_context(context)

    return f"""I'm planning a trip in {season} {year}.

{context_str}

**Request:** {query}

Please consider:
- Weather conditions and what to expect
- Seasonal attractions or events
- What's in bloom or seasonal highlights
- Packing recommendations
- Any seasonal closures or considerations
- Best alternatives if main attractions aren't available"""


# Export all prompt functions
__all__ = [
    "get_system_prompt",
    "get_travel_advice_prompt",
    "get_poi_recommendation_prompt",
    "get_route_planning_prompt",
    "get_comparison_prompt",
    "get_general_prompt",
    "get_conversation_followup_prompt",
    "get_clarification_prompt",
    "get_fallback_prompt",
    "get_multi_day_itinerary_prompt",
    "get_budget_conscious_prompt",
    "get_family_friendly_prompt",
    "get_accessibility_prompt",
    "get_seasonal_prompt",
]
