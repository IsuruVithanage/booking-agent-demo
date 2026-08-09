"""In-memory hotel and booking data for the Booking MCP server.

No external dependencies (no database, no vector store) so the server
has nothing to misconfigure — it's meant to be a fast, self-contained
demo of AMP's MCP proxy + gateway governance, not a production booking
backend.
"""

from __future__ import annotations

import itertools
import threading
from datetime import date
from typing import Any, Optional

_booking_id_seq = itertools.count(1)
_lock = threading.Lock()

HOTELS: dict[str, dict[str, Any]] = {
    "htl_tokyo_01": {
        "hotel_id": "htl_tokyo_01",
        "name": "Shibuya Sky Hotel",
        "city": "Tokyo",
        "rating": 4.6,
        "price_per_night": 210.0,
        "rooms_total": 12,
        "amenities": ["wifi", "breakfast", "gym"],
    },
    "htl_tokyo_02": {
        "hotel_id": "htl_tokyo_02",
        "name": "Asakusa Riverside Inn",
        "city": "Tokyo",
        "rating": 4.2,
        "price_per_night": 140.0,
        "rooms_total": 20,
        "amenities": ["wifi", "onsen"],
    },
    "htl_ny_01": {
        "hotel_id": "htl_ny_01",
        "name": "Brooklyn Heights Loft Hotel",
        "city": "New York",
        "rating": 4.4,
        "price_per_night": 260.0,
        "rooms_total": 8,
        "amenities": ["wifi", "rooftop-bar"],
    },
    "htl_paris_01": {
        "hotel_id": "htl_paris_01",
        "name": "Le Marais Boutique Hotel",
        "city": "Paris",
        "rating": 4.7,
        "price_per_night": 300.0,
        "rooms_total": 10,
        "amenities": ["wifi", "breakfast", "spa"],
    },
}

# booking_id -> booking record. Occupied nights per hotel are tracked in
# BOOKED_NIGHTS so availability accounts for existing confirmed bookings.
BOOKINGS: dict[str, dict[str, Any]] = {}
BOOKED_NIGHTS: dict[str, list[tuple[str, str, int]]] = {h: [] for h in HOTELS}


def search_hotels(
    destination: Optional[str] = None,
    min_rating: Optional[float] = None,
    max_price: Optional[float] = None,
) -> list[dict[str, Any]]:
    results = list(HOTELS.values())
    if destination:
        needle = destination.strip().lower()
        results = [h for h in results if needle in h["city"].lower()]
    if min_rating is not None:
        results = [h for h in results if h["rating"] >= min_rating]
    if max_price is not None:
        results = [h for h in results if h["price_per_night"] <= max_price]
    return results


def get_hotel(hotel_id: str) -> Optional[dict[str, Any]]:
    return HOTELS.get(hotel_id)


def _nights_overlap(a_start: str, a_end: str, b_start: str, b_end: str) -> bool:
    return date.fromisoformat(a_start) < date.fromisoformat(b_end) and date.fromisoformat(
        b_start
    ) < date.fromisoformat(a_end)


def rooms_booked_for_range(hotel_id: str, check_in: str, check_out: str) -> int:
    return sum(
        rooms
        for (start, end, rooms) in BOOKED_NIGHTS.get(hotel_id, [])
        if _nights_overlap(start, end, check_in, check_out)
    )


def check_availability(
    hotel_id: str, check_in_date: str, check_out_date: str, rooms_requested: int
) -> dict[str, Any]:
    hotel = get_hotel(hotel_id)
    if not hotel:
        return {"error": f"Unknown hotel_id '{hotel_id}'."}
    booked = rooms_booked_for_range(hotel_id, check_in_date, check_out_date)
    available = hotel["rooms_total"] - booked
    return {
        "hotel_id": hotel_id,
        "check_in_date": check_in_date,
        "check_out_date": check_out_date,
        "rooms_available": max(available, 0),
        "can_fulfill": available >= rooms_requested,
    }


def create_booking(
    hotel_id: str,
    check_in_date: str,
    check_out_date: str,
    rooms: int,
    guests: int,
    guest_name: str,
    guest_email: str,
    user_id: Optional[str] = None,
) -> dict[str, Any]:
    hotel = get_hotel(hotel_id)
    if not hotel:
        return {"error": f"Unknown hotel_id '{hotel_id}'."}
    availability = check_availability(hotel_id, check_in_date, check_out_date, rooms)
    if not availability["can_fulfill"]:
        return {"error": "Not enough rooms available for the requested dates."}

    with _lock:
        booking_id = f"bkg_{next(_booking_id_seq):04d}"
        nights = (date.fromisoformat(check_out_date) - date.fromisoformat(check_in_date)).days
        total_price = round(nights * hotel["price_per_night"] * rooms, 2)
        record = {
            "booking_id": booking_id,
            "user_id": user_id or "guest",
            "hotel_id": hotel_id,
            "hotel_name": hotel["name"],
            "check_in_date": check_in_date,
            "check_out_date": check_out_date,
            "rooms": rooms,
            "guests": guests,
            "guest_name": guest_name,
            "guest_email": guest_email,
            "total_price": total_price,
            "status": "CONFIRMED",
        }
        BOOKINGS[booking_id] = record
        BOOKED_NIGHTS[hotel_id].append((check_in_date, check_out_date, rooms))
    return record


def list_bookings(user_id: Optional[str] = None, status: Optional[str] = None) -> list[dict[str, Any]]:
    results = list(BOOKINGS.values())
    if user_id:
        results = [b for b in results if b["user_id"] == user_id]
    if status and status.upper() != "ALL":
        results = [b for b in results if b["status"] == status.upper()]
    return results


def cancel_booking(booking_id: str) -> dict[str, Any]:
    booking = BOOKINGS.get(booking_id)
    if not booking:
        return {"error": f"Unknown booking_id '{booking_id}'."}
    with _lock:
        booking["status"] = "CANCELLED"
        nights = (booking["check_in_date"], booking["check_out_date"], booking["rooms"])
        remaining = [n for n in BOOKED_NIGHTS[booking["hotel_id"]] if n != nights]
        BOOKED_NIGHTS[booking["hotel_id"]] = remaining
    return booking
