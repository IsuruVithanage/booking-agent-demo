"""Booking MCP server.

Exposes the booking tools over streamable-HTTP MCP at /mcp so it can be
fronted by an AMP MCP Proxy. Deployed on AMP as a custom-api agent —
see ../README.md for the registration steps.
"""

from __future__ import annotations

from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

import store

# Fixed port, matching the AMP agent's declared inputInterface.port (8000).
# Buildpack runtimes inject their own PORT (typically 8080) by convention;
# reading it here would desync the app from the port AMP's gateway routes
# to, so it's deliberately ignored (same approach the platform's own
# samples/hotel-booking-agent uses via an explicit --port start-command arg).
mcp = FastMCP(
    "Booking MCP",
    host="0.0.0.0",
    port=8000,
    streamable_http_path="/mcp",
)


@mcp.tool()
def search_hotels(
    destination: Optional[str] = None,
    min_rating: Optional[float] = None,
    max_price: Optional[float] = None,
) -> list[dict[str, Any]]:
    """Search hotels, optionally filtered by destination city, minimum rating, and maximum nightly price.

    Args:
        destination: City name to search in (case-insensitive substring match), e.g. "Tokyo".
        min_rating: Minimum star rating (0-5).
        max_price: Maximum nightly price in USD.

    Returns:
        A list of matching hotels with hotel_id, name, city, rating, price_per_night, amenities.
    """
    return store.search_hotels(destination=destination, min_rating=min_rating, max_price=max_price)


@mcp.tool()
def get_hotel_info(hotel_id: str) -> dict[str, Any]:
    """Get full details for one hotel by its hotel_id.

    Args:
        hotel_id: The hotel identifier, e.g. "htl_tokyo_01".

    Returns:
        Hotel details, or an error if hotel_id is not found.
    """
    hotel = store.get_hotel(hotel_id)
    return hotel if hotel else {"error": f"Unknown hotel_id '{hotel_id}'."}


@mcp.tool()
def check_availability(
    hotel_id: str, check_in_date: str, check_out_date: str, rooms_requested: int = 1
) -> dict[str, Any]:
    """Check how many rooms are available at a hotel for a date range.

    Args:
        hotel_id: The hotel identifier.
        check_in_date: Check-in date, YYYY-MM-DD.
        check_out_date: Check-out date, YYYY-MM-DD.
        rooms_requested: Number of rooms the guest wants to book.

    Returns:
        Availability info including rooms_available and can_fulfill.
    """
    return store.check_availability(hotel_id, check_in_date, check_out_date, rooms_requested)


@mcp.tool()
def create_booking(
    hotel_id: str,
    check_in_date: str,
    check_out_date: str,
    guest_name: str,
    guest_email: str,
    rooms: int = 1,
    guests: int = 1,
    user_id: Optional[str] = None,
) -> dict[str, Any]:
    """Create a confirmed hotel booking.

    Args:
        hotel_id: The hotel identifier to book.
        check_in_date: Check-in date, YYYY-MM-DD.
        check_out_date: Check-out date, YYYY-MM-DD.
        guest_name: Full name of the primary guest.
        guest_email: Email address of the primary guest.
        rooms: Number of rooms to book.
        guests: Total number of guests.
        user_id: Optional caller-supplied user identifier, used to list bookings later.

    Returns:
        The created booking record (with booking_id and total_price), or an error.
    """
    return store.create_booking(
        hotel_id=hotel_id,
        check_in_date=check_in_date,
        check_out_date=check_out_date,
        rooms=rooms,
        guests=guests,
        guest_name=guest_name,
        guest_email=guest_email,
        user_id=user_id,
    )


@mcp.tool()
def list_bookings(user_id: Optional[str] = None, status: Optional[str] = None) -> list[dict[str, Any]]:
    """List bookings, optionally filtered by user_id and status.

    Args:
        user_id: Filter to bookings made by this user_id.
        status: Filter by status: CONFIRMED, CANCELLED, or ALL (default ALL).

    Returns:
        A list of matching booking records.
    """
    return store.list_bookings(user_id=user_id, status=status)


@mcp.tool()
def cancel_booking(booking_id: str) -> dict[str, Any]:
    """Cancel an existing booking by its booking_id.

    Args:
        booking_id: The booking identifier to cancel.

    Returns:
        The updated booking record with status CANCELLED, or an error.
    """
    return store.cancel_booking(booking_id)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
