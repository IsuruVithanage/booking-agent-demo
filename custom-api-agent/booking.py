from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, status

from config import get_settings

logger = logging.getLogger(__name__)

DATA_PATH = Path(__file__).resolve().parent / "storage" / "bookings.json"
DATA_PATH.parent.mkdir(parents=True, exist_ok=True)

DEFAULT_POLICY_TEXT = (
    "Free cancellation up to 48 hours before check-in. "
    "Cancellations within 48 hours are charged one night's rate."
)

router = APIRouter()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_bookings() -> list[dict[str, Any]]:
    if not DATA_PATH.exists():
        DATA_PATH.write_text("[]")
        return []
    try:
        return json.loads(DATA_PATH.read_text())
    except json.JSONDecodeError:
        logger.warning("booking data corrupted; starting fresh")
        DATA_PATH.write_text("[]")
        return []


def _save_bookings(bookings: list[dict[str, Any]]) -> None:
    DATA_PATH.write_text(json.dumps(bookings, indent=2))


def _find(bookings: list[dict[str, Any]], booking_id: str, user_id: str) -> dict[str, Any] | None:
    return next(
        (b for b in bookings if b.get("booking_id") == booking_id and b.get("user_id") == user_id),
        None,
    )


def _read_policy_text() -> str:
    """Reads the cancellation policy from the file-mounted path (falls back for local dev)."""
    path = Path(get_settings().policy_file_path)
    if path.exists():
        return path.read_text().strip()
    logger.info("policy file not found at %s; using default text", path)
    return DEFAULT_POLICY_TEXT


def _confirmation_message(booking: dict[str, Any]) -> str:
    settings = get_settings()
    template = (
        f"Your booking {booking['booking_id']} at {settings.hotel_name} "
        f"from {booking['check_in_date']} to {booking['check_out_date']} is confirmed."
    )
    if not settings.openai_api_key:
        return template

    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key)
        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {
                    "role": "system",
                    "content": "Write one short, friendly sentence confirming a hotel booking.",
                },
                {
                    "role": "user",
                    "content": (
                        f"Guest: {booking.get('primary_guest', {}).get('name', 'Guest')}. "
                        f"Hotel: {settings.hotel_name}. "
                        f"Dates: {booking['check_in_date']} to {booking['check_out_date']}. "
                        f"Guests: {booking['number_of_guests']}. "
                        f"Confirmation number: {booking['confirmation_number']}."
                    ),
                },
            ],
            max_tokens=60,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        logger.exception("LLM confirmation message failed; using template")
        return template


@router.post("/bookings", status_code=201)
def create_booking(payload: dict[str, Any]):
    booking_id = f"BK{uuid.uuid4().hex[:8].upper()}"
    confirmation_number = f"CONF{uuid.uuid4()}"

    booking = {
        "booking_id": booking_id,
        "confirmation_number": confirmation_number,
        "user_id": payload.get("user_id", "guest"),
        "hotel_name": get_settings().hotel_name,
        "check_in_date": payload.get("check_in_date"),
        "check_out_date": payload.get("check_out_date"),
        "number_of_guests": payload.get("number_of_guests"),
        "primary_guest": payload.get("primary_guest"),
        "special_requests": payload.get("special_requests"),
        "booking_status": "CONFIRMED",
        "booking_date": _now(),
    }

    bookings = _load_bookings()
    bookings.append(booking)
    _save_bookings(bookings)

    return {
        "booking_id": booking_id,
        "confirmation_number": confirmation_number,
        "confirmation_message": _confirmation_message(booking),
        "cancellation_policy": _read_policy_text(),
        "booking_details": booking,
    }


@router.get("/bookings")
def list_bookings(user_id: str):
    bookings = _load_bookings()
    return [b for b in bookings if b.get("user_id") == user_id]


@router.get("/bookings/{booking_id}")
def get_booking(booking_id: str, user_id: str):
    booking = _find(_load_bookings(), booking_id, user_id)
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    return booking


@router.put("/bookings/{booking_id}")
def update_booking(booking_id: str, payload: dict[str, Any]):
    user_id = payload.get("user_id", "guest")
    bookings = _load_bookings()
    booking = _find(bookings, booking_id, user_id)
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    for field in ("check_in_date", "check_out_date", "number_of_guests", "primary_guest", "special_requests"):
        if field in payload:
            booking[field] = payload[field]
    booking["updated_at"] = _now()
    _save_bookings(bookings)
    return {"message": "Booking updated", "booking_details": booking}


@router.delete("/bookings/{booking_id}")
def cancel_booking(booking_id: str, user_id: str):
    bookings = _load_bookings()
    booking = _find(bookings, booking_id, user_id)
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    booking["booking_status"] = "CANCELLED"
    booking["cancelled_at"] = _now()
    _save_bookings(bookings)
    return {"message": "Booking cancelled", "booking_details": booking}


@router.get("/policy")
def get_policy():
    return {"cancellation_policy": _read_policy_text()}
