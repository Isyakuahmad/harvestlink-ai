import hashlib
import hmac
import json
import re
from datetime import UTC, date, datetime, timedelta
from secrets import token_urlsafe
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db import get_db
from app.dependencies import get_current_user
from app.models import (
    FarmerPendingEntry, FarmActivity, FarmSeason, PlantHealthCase, User,
    WhatsAppChannelLink, WhatsAppInboundMessage,
)

router = APIRouter(tags=["WhatsApp Farmer Agent", "plant health", "climate"])
DatabaseSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


class WhatsAppLinkRequest(BaseModel):
    phone_e164: str = Field(pattern=r"^\+[1-9][0-9]{7,14}$")


class PlantHealthReport(BaseModel):
    crop_name: str = Field(min_length=2, max_length=100)
    farm_location: str = Field(min_length=2, max_length=180)
    symptoms: str = Field(min_length=5, max_length=3000)
    affected_area_percent: float | None = Field(default=None, ge=0, le=100)
    severity: str = Field(default="unknown", pattern="^(low|moderate|high|unknown)$")
    photo_uri: str | None = Field(default=None, max_length=2000)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _normal_phone(value: str) -> str:
    return value if value.startswith("+") else f"+{value}"


def _ipm_guidance(symptoms: str) -> dict:
    text = symptoms.lower()
    likely_categories = []
    if any(word in text for word in ("hole", "chewed", "caterpillar", "insect", "worm")):
        likely_categories.append("chewing insect damage")
    if any(word in text for word in ("yellow", "wilting", "wilt", "stunted")):
        likely_categories.append("water, nutrient, root or disease stress")
    if any(word in text for word in ("spot", "blight", "mould", "mold", "rot", "fungus")):
        likely_categories.append("possible fungal or bacterial disease symptoms")
    if any(word in text for word in ("mosaic", "curl", "curled", "distorted")):
        likely_categories.append("possible viral, insect-vector or herbicide injury symptoms")
    if not likely_categories:
        likely_categories.append("cause not yet clear; more field observations are needed")
    return {
        "assessment": "Preliminary symptom grouping only; this is not a confirmed diagnosis.",
        "possible_categories": likely_categories,
        "confidence": "low_without_expert_review_and_clear_field_images",
        "recommended_steps": [
            "Photograph the whole plant, affected leaves (both sides), stem and nearby healthy plants in daylight.",
            "Check several plants across the field and estimate the percentage affected.",
            "Record when symptoms began, recent rainfall, irrigation, fertiliser and any pesticide applications.",
            "Where practical, isolate heavily affected plant material and avoid moving it between fields until assessed.",
            "Ask a local agricultural extension officer or plant-health specialist to inspect severe, spreading or unfamiliar symptoms.",
        ],
        "pesticide_safety": [
            "Do not spray based on this preliminary symptom grouping alone.",
            "Identify the pest or disease first and use integrated pest management where possible.",
            "If a pesticide is justified, use only a product currently registered in Nigeria for the specific crop and target pest, and follow its label exactly.",
            "Use the label-specified protective equipment, re-entry interval and pre-harvest interval; never mix products unless the label explicitly permits it.",
            "Keep pesticides away from children, food, water sources and livestock; never reuse empty containers.",
        ],
        "urgent_escalation": "Seek prompt local extension advice if damage is spreading quickly, affects a large area, or threatens the crop.",
    }


def _parse_activity(text: str) -> dict | None:
    value = text.lower()
    activity_type = None
    if re.search(r"\b(plant(ed|ing)?|sow(ed|ing)?)\b", value):
        activity_type = "planting"
    elif re.search(r"\b(bought|purchased|buy|purchase)\b", value):
        activity_type = "input_purchase"
    elif re.search(r"\b(spray(ed|ing)?|pesticide|insecticide)\b", value):
        activity_type = "pest_control"
    elif re.search(r"\b(water(ed|ing)?|irrigat(ed|ion))\b", value):
        activity_type = "irrigation"
    elif re.search(r"\b(harvest(ed|ing)?)\b", value):
        activity_type = "harvest"
    elif re.search(r"\b(sold|sale)\b", value):
        activity_type = "sale"
    elif re.search(r"\b(labour|labor|workers|worker)\b", value):
        activity_type = "labour"
    if not activity_type:
        return None
    crops = ("maize", "corn", "rice", "cassava", "yam", "sorghum", "millet",
             "soybean", "soya", "groundnut", "peanut", "tomato", "pepper",
             "onion", "beans", "cowpea", "sesame", "ginger", "cocoa")
    crop = next((c for c in crops if re.search(rf"\b{re.escape(c)}\b", value)), None)
    quantity_match = re.search(r"\b(\d+(?:\.\d+)?)\s*(hectares?|ha|acres?|bags?|kg|kgs|tonnes?|tons?)\b", value)
    money_match = re.search(r"(?:₦|ngn\s*)([\d,]+(?:\.\d+)?)", text, re.IGNORECASE)
    quantity = float(quantity_match.group(1)) if quantity_match else None
    unit = quantity_match.group(2).lower() if quantity_match else None
    amount = float(money_match.group(1).replace(",", "")) if money_match else None
    return {
        "activity_type": activity_type,
        "description": text.strip()[:2000],
        "activity_date": date.today().isoformat(),
        "quantity": quantity,
        "quantity_unit": unit,
        "amount": amount,
        "currency": "NGN" if amount is not None else None,
        "crop_name": crop,
    }


def _send_whatsapp_text(to: str, body: str) -> bool:
    settings = get_settings()
    if not settings.whatsapp_access_token or not settings.whatsapp_phone_number_id:
        return False
    url = (
        f"https://graph.facebook.com/{settings.whatsapp_graph_api_version}/"
        f"{settings.whatsapp_phone_number_id}/messages"
    )
    try:
        response = httpx.post(
            url,
            headers={"Authorization": f"Bearer {settings.whatsapp_access_token}"},
            json={"messaging_product": "whatsapp", "to": to.lstrip("+"),
                  "type": "text", "text": {"preview_url": False, "body": body[:4000]}},
            timeout=8.0,
        )
        response.raise_for_status()
        return True
    except httpx.HTTPError:
        return False


def _weather(latitude: float, longitude: float) -> dict:
    try:
        response = httpx.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": latitude, "longitude": longitude,
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_sum,wind_speed_10m_max",
                "forecast_days": 3, "timezone": "auto",
            },
            timeout=8.0,
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError):
        raise HTTPException(status_code=503, detail="Weather service is temporarily unavailable") from None
    daily = payload.get("daily", {})
    days = []
    for index, day in enumerate(daily.get("time", [])):
        rain_chance = (daily.get("precipitation_probability_max") or [None] * len(daily["time"]))[index]
        rain_mm = (daily.get("precipitation_sum") or [None] * len(daily["time"]))[index]
        wind = (daily.get("wind_speed_10m_max") or [None] * len(daily["time"]))[index]
        days.append({
            "date": day,
            "temperature_max_c": (daily.get("temperature_2m_max") or [None] * len(daily["time"]))[index],
            "temperature_min_c": (daily.get("temperature_2m_min") or [None] * len(daily["time"]))[index],
            "precipitation_probability_max_percent": rain_chance,
            "precipitation_sum_mm": rain_mm,
            "wind_speed_max_kmh": wind,
            "field_planning_notes": [
                note for condition, note in [
                    (rain_chance is not None and rain_chance >= 70, "High forecast rain chance: plan field access and avoid timing pesticide applications immediately before rain; follow the product label's rainfast guidance."),
                    (wind is not None and wind >= 20, "Wind may increase spray drift: avoid spraying in unsuitable wind and follow the product label."),
                ] if condition
            ],
        })
    return {
        "provider": "Open-Meteo",
        "coordinates": {"latitude": latitude, "longitude": longitude},
        "timezone": payload.get("timezone"),
        "daily": days,
        "disclaimer": "Forecasts are estimates, not field measurements or guarantees. Check local conditions and product labels before farm operations.",
    }


@router.post("/api/v1/whatsapp/link-challenge")
def create_link_challenge(payload: WhatsAppLinkRequest, db: DatabaseSession, user: CurrentUser):
    if user.role != "farmer":
        raise HTTPException(status_code=403, detail="Farmer account required")
    existing_phone = db.query(WhatsAppChannelLink).filter(
        WhatsAppChannelLink.phone_e164 == payload.phone_e164,
        WhatsAppChannelLink.user_id != user.id,
    ).first()
    if existing_phone:
        raise HTTPException(status_code=409, detail="This WhatsApp number is already linked")
    code = token_urlsafe(6)[:8].upper()
    link = db.query(WhatsAppChannelLink).filter(WhatsAppChannelLink.user_id == user.id).first()
    if link is None:
        link = WhatsAppChannelLink(user_id=user.id, phone_e164=payload.phone_e164)
        db.add(link)
    link.phone_e164 = payload.phone_e164
    link.link_code_hash = _hash(code)
    link.link_expires_at = datetime.now(UTC) + timedelta(minutes=15)
    link.verified_at = None
    db.commit()
    return {
        "phone_e164": payload.phone_e164,
        "link_code": code,
        "expires_in_minutes": 15,
        "instruction": "Send LINK followed by this code to the official HarvestLink WhatsApp number. Do not share the code with anyone.",
    }


@router.get("/api/v1/whatsapp/webhook")
def verify_whatsapp_webhook(
    mode: str | None = Query(default=None, alias="hub.mode"),
    token: str | None = Query(default=None, alias="hub.verify_token"),
    challenge: str | None = Query(default=None, alias="hub.challenge"),
):
    settings = get_settings()
    if mode == "subscribe" and settings.whatsapp_verify_token and hmac.compare_digest(
        token or "", settings.whatsapp_verify_token
    ):
        return PlainTextResponse(challenge or "")
    raise HTTPException(status_code=403, detail="Webhook verification failed")


@router.post("/api/v1/whatsapp/webhook")
async def receive_whatsapp_webhook(request: Request, db: DatabaseSession):
    settings = get_settings()
    if not settings.whatsapp_app_secret:
        raise HTTPException(status_code=503, detail="WhatsApp webhook signature verification is not configured")
    raw = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")
    expected = "sha256=" + hmac.new(
        settings.whatsapp_app_secret.encode(), raw, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid webhook JSON") from None

    processed = 0
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for message in value.get("messages", []):
                provider_id = message.get("id")
                sender = _normal_phone(str(message.get("from", "")))
                if not provider_id or not sender:
                    continue
                if db.query(WhatsAppInboundMessage).filter(
                    WhatsAppInboundMessage.provider_message_id == provider_id
                ).first():
                    continue
                message_type = message.get("type", "unknown")
                message_text = message.get("text", {}).get("body") if message_type == "text" else None
                media_id = message.get(message_type, {}).get("id") if message_type in {"image", "audio", "document"} else None
                inbound = WhatsAppInboundMessage(
                    provider_message_id=provider_id, from_phone=sender,
                    message_type=message_type, message_text=message_text, media_id=media_id,
                )
                db.add(inbound)
                db.flush()

                link = db.query(WhatsAppChannelLink).filter(
                    WhatsAppChannelLink.phone_e164 == sender
                ).first()
                text_body = (message_text or "").strip()
                if text_body.upper().startswith("LINK "):
                    supplied_code = text_body.split(maxsplit=1)[1].strip().upper()
                    if (link and link.verified_at is None and link.link_code_hash
                        and link.link_expires_at):
                        expiry = link.link_expires_at
                        if expiry.tzinfo is None:
                            expiry = expiry.replace(tzinfo=UTC)
                        if expiry > datetime.now(UTC) and hmac.compare_digest(
                            link.link_code_hash, _hash(supplied_code)
                        ):
                            link.verified_at = datetime.now(UTC)
                            link.link_code_hash = None
                            link.link_expires_at = None
                            inbound.status = "linked"
                            _send_whatsapp_text(sender, "Your WhatsApp number is now linked to HarvestLink. You can record farm activities or report crop problems here.")
                        else:
                            _send_whatsapp_text(sender, "That link code is invalid or expired. Request a new code from your HarvestLink account.")
                    else:
                        _send_whatsapp_text(sender, "No active link request was found for this number. Request a new code from your HarvestLink account.")
                    processed += 1
                    continue

                if link is None or link.verified_at is None:
                    _send_whatsapp_text(sender, "Welcome to HarvestLink. First link your number from your farmer account, then send LINK followed by the one-time code.")
                    processed += 1
                    continue

                pending = db.query(FarmerPendingEntry).filter(
                    FarmerPendingEntry.farmer_user_id == link.user_id,
                    FarmerPendingEntry.status == "pending",
                ).order_by(FarmerPendingEntry.created_at.desc()).first()
                if pending is not None and pending.expires_at.tzinfo is None:
                    pending.expires_at = pending.expires_at.replace(tzinfo=UTC)
                if pending is not None and pending.expires_at <= datetime.now(UTC):
                    pending.status = "expired"
                    pending = None
                if text_body.lower() in {"yes", "confirm", "save", "1"} and pending:
                    entry_data = pending.entry_json
                    activity = FarmActivity(
                        farmer_user_id=link.user_id, season_id=pending.season_id,
                        activity_type=entry_data["activity_type"],
                        description=entry_data["description"],
                        activity_date=date.fromisoformat(entry_data["activity_date"]),
                        quantity=entry_data.get("quantity"),
                        quantity_unit=entry_data.get("quantity_unit"),
                        amount=entry_data.get("amount"), currency=entry_data.get("currency"),
                        source_channel="whatsapp",
                    )
                    db.add(activity)
                    pending.status = "confirmed"
                    inbound.status = "activity_confirmed"
                    _send_whatsapp_text(sender, "Saved to your HarvestLink farm records. Reply HELP for examples.")
                    processed += 1
                    continue
                if text_body.lower() in {"no", "cancel", "2"} and pending:
                    pending.status = "cancelled"
                    inbound.status = "activity_cancelled"
                    _send_whatsapp_text(sender, "Okay, I did not save that activity. Send the corrected details whenever you are ready.")
                    processed += 1
                    continue

                if message_type == "location":
                    location = message.get("location", {})
                    lat, lon = location.get("latitude"), location.get("longitude")
                    if lat is not None and lon is not None:
                        link.latitude, link.longitude = float(lat), float(lon)
                        forecast = _weather(link.latitude, link.longitude)
                        summary = "3-day local forecast:\n" + "\n".join(
                            f"{day['date']}: rain chance {day['precipitation_probability_max_percent']}%, rain {day['precipitation_sum_mm']} mm, max temp {day['temperature_max_c']}°C"
                            for day in forecast["daily"]
                        )
                        _send_whatsapp_text(sender, summary)
                    processed += 1
                    continue

                if message_type == "image":
                    case = PlantHealthCase(
                        farmer_user_id=link.user_id, crop_name="unspecified",
                        farm_location="not provided", symptoms="Image received; crop and symptoms awaiting farmer details.",
                        image_media_id=media_id, status="awaiting_details",
                        guidance_json={"next_step": "Reply with crop name, symptoms, when they started and approximate affected area."},
                    )
                    db.add(case)
                    _send_whatsapp_text(sender, "I received your crop photo. Please reply with the crop name, what you see, when it started and how much of the field is affected. I will not diagnose from an image alone.")
                    processed += 1
                    continue

                symptoms = any(word in text_body.lower() for word in (
                    "yellow", "wilt", "wilting", "spots", "holes", "chewed",
                    "caterpillar", "insect", "worm", "blight", "rot", "curl", "mosaic",
                ))
                if symptoms and any(word in text_body.lower() for word in ("leaf", "leaves", "plant", "crop", "maize", "cassava", "rice", "tomato", "pepper")):
                    crop_match = re.search(r"\b(maize|corn|cassava|rice|tomato|pepper|yam|sorghum|millet|soybean|groundnut|beans)\b", text_body, re.I)
                    crop = crop_match.group(1).lower() if crop_match else "unspecified"
                    guidance = _ipm_guidance(text_body)
                    case = PlantHealthCase(
                        farmer_user_id=link.user_id, crop_name=crop,
                        farm_location="not provided", symptoms=text_body,
                        status="needs_review", guidance_json=guidance,
                    )
                    db.add(case)
                    _send_whatsapp_text(sender, "I have logged your plant-health report. " + " ".join(guidance["recommended_steps"][:3]) + " I cannot confirm a diagnosis or recommend a pesticide from this message alone.")
                    processed += 1
                    continue

                if any(word in text_body.lower() for word in ("weather", "rain forecast", "climate", "rain tomorrow")):
                    if link.latitude is None or link.longitude is None:
                        _send_whatsapp_text(sender, "Please share your farm location using WhatsApp's Location attachment so I can retrieve a local forecast.")
                    else:
                        forecast = _weather(link.latitude, link.longitude)
                        _send_whatsapp_text(sender, "3-day forecast: " + "; ".join(
                            f"{d['date']} rain chance {d['precipitation_probability_max_percent']}%, {d['precipitation_sum_mm']} mm"
                            for d in forecast["daily"]
                        ))
                    processed += 1
                    continue

                parsed = _parse_activity(text_body) if message_type == "text" else None
                if parsed:
                    crop = parsed.pop("crop_name")
                    seasons = db.query(FarmSeason).filter(
                        FarmSeason.farmer_user_id == link.user_id, FarmSeason.status == "active"
                    ).all()
                    if crop:
                        seasons = [s for s in seasons if s.crop_name.lower() in {crop, {"corn": "maize", "soya": "soybean", "peanut": "groundnut"}.get(crop, crop)}]
                    if not seasons:
                        _send_whatsapp_text(sender, "I understood an activity, but could not find a matching active crop season. Add your farm and crop season in HarvestLink first, then send the message again.")
                    else:
                        season = seasons[0]
                        pending_entry = FarmerPendingEntry(
                            farmer_user_id=link.user_id, season_id=season.id,
                            entry_json=parsed, expires_at=datetime.now(UTC) + timedelta(minutes=30),
                        )
                        db.add(pending_entry)
                        details = f"{parsed['activity_type'].replace('_', ' ')} for {season.crop_name}: {parsed['description']}"
                        _send_whatsapp_text(sender, f"Please confirm this farm record: {details}. Reply YES to save or NO to cancel.")
                        inbound.status = "awaiting_confirmation"
                    processed += 1
                    continue

                if text_body.lower() in {"help", "hi", "hello", "start"}:
                    _send_whatsapp_text(sender, "HarvestLink Farmer Agent\n1) Record: I planted 3 hectares of maize today.\n2) Inputs: I bought 4 bags of fertiliser for ₦120,000.\n3) Crop issue: My tomato leaves have yellow spots.\n4) Weather: send WEATHER, or share your farm location.\nI will ask you to confirm records before saving.")
                else:
                    _send_whatsapp_text(sender, "I did not understand that yet. Try: I planted 3 hectares of maize today; I bought 4 bags of fertiliser for ₦120,000; or describe your crop symptoms.")
                processed += 1
    db.commit()
    return {"status": "accepted", "processed_messages": processed}


@router.post("/api/v1/plant-health/cases", status_code=201)
def create_plant_health_case(payload: PlantHealthReport, db: DatabaseSession, user: CurrentUser):
    if user.role != "farmer":
        raise HTTPException(status_code=403, detail="Farmer account required")
    if payload.photo_uri and not payload.photo_uri.startswith("https://"):
        raise HTTPException(status_code=422, detail="Photo URI must use HTTPS")
    guidance = _ipm_guidance(payload.symptoms)
    case = PlantHealthCase(
        farmer_user_id=user.id, crop_name=payload.crop_name,
        farm_location=payload.farm_location, symptoms=payload.symptoms,
        affected_area_percent=payload.affected_area_percent,
        severity=payload.severity, image_uri=payload.photo_uri,
        status="needs_review", guidance_json=guidance,
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return {"case_id": case.id, "status": case.status, "guidance": guidance,
            "disclaimer": "Preliminary IPM guidance only; not a confirmed diagnosis or pesticide prescription."}


@router.get("/api/v1/plant-health/cases")
def list_plant_health_cases(db: DatabaseSession, user: CurrentUser):
    if user.role != "farmer":
        raise HTTPException(status_code=403, detail="Farmer account required")
    cases = db.query(PlantHealthCase).filter(
        PlantHealthCase.farmer_user_id == user.id
    ).order_by(PlantHealthCase.created_at.desc()).all()
    return [{
        "case_id": c.id, "crop_name": c.crop_name, "farm_location": c.farm_location,
        "symptoms": c.symptoms, "severity": c.severity, "status": c.status,\n        "image_uri": c.image_uri, "has_whatsapp_media": c.image_media_id is not None,
        "guidance": c.guidance_json, "created_at": c.created_at,
    } for c in cases]


@router.get("/api/v1/climate/forecast")
def climate_forecast(
    user: CurrentUser,
    latitude: float = Query(ge=-90, le=90),
    longitude: float = Query(ge=-180, le=180),
):
    if user.role != "farmer":
        raise HTTPException(status_code=403, detail="Farmer account required")
    return _weather(latitude, longitude)
