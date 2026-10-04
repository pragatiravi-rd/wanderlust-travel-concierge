# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
import os
import uuid
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

from google import genai
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.memory import VertexAiMemoryBankService
from google.adk.models import Gemini
from google.adk.tools import ToolContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.cloud import firestore, storage
from google.genai import types

from a2ui.schema.manager import A2uiSchemaManager
from a2ui.basic_catalog.provider import BasicCatalog
from app.a2ui_utils import a2ui_callback

# CRITICAL: Hardcode project ID as string for Firestore and Cloud Storage clients.
# Do NOT use os.getenv("GOOGLE_CLOUD_PROJECT") or google.auth.default()
# because Agent Platform returns the project NUMBER on deployment.
FIRESTORE_PROJECT_ID = "qwiklabs-gcp-03-faf61ce9a80f"
COLLECTION_NAME = "destinations"
GCS_BUCKET_NAME = "wanderlust-travel-assets-qwiklabs-gcp-03-faf61ce9a80f"

db = firestore.Client(project=FIRESTORE_PROJECT_ID)


def search_destinations(city: str = "", category: str = "", tag: str = "") -> str:
    """Search for travel destinations in the Firestore database.

    Args:
        city: Optional city name to filter by (e.g., 'San Francisco', 'Paris', 'Kyoto', 'Tokyo', 'New York').
        category: Optional category filter (e.g., 'Scenic & Outdoor', 'Culture & Heritage', 'Dining & Gastronomy').
        tag: Optional keyword tag filter (e.g., 'foodie', 'scenic', 'historic', 'coastal', 'park').

    Returns:
        A list of matching travel destinations with details as a formatted string.
    """
    try:
        query_ref = db.collection(COLLECTION_NAME)
        docs = list(query_ref.stream())
        if not docs:
            return "No destinations found in database."

        results = []
        for doc in docs:
            data = doc.to_dict()
            doc_id = doc.id
            data["id"] = doc_id

            # Apply filters
            if city and city.lower() not in data.get("city", "").lower():
                continue
            if category and category.lower() not in data.get("category", "").lower():
                continue
            if tag and tag.lower() not in [t.lower() for t in data.get("tags", [])]:
                continue

            results.append(data)

        if not results:
            return f"No destinations found matching filters (city='{city}', category='{category}', tag='{tag}')."

        formatted = [
            f"- [{d['id']}] {d['name']} ({d['city']}) | Category: {d['category']} | Price: {d['price_tier']} | Rating: {d['rating']}/5\n  Description: {d['description']}\n  Tags: {', '.join(d.get('tags', []))}"
            for d in results
        ]
        return "Found destinations:\n" + "\n".join(formatted)
    except Exception as e:
        return f"Error querying Firestore destinations: {e}"


def get_destination_details(destination_id: str) -> str:
    """Retrieve full details for a specific destination by its document ID from Firestore.

    Args:
        destination_id: Document ID of the destination (e.g., 'dest_sf_coastal', 'dest_kyoto_bamboo').

    Returns:
        Full details of the requested destination.
    """
    try:
        doc_ref = db.collection(COLLECTION_NAME).document(destination_id)
        doc = doc_ref.get()
        if not doc.exists:
            return f"Destination ID '{destination_id}' not found."
        data = doc.to_dict()
        data["id"] = doc.id
        return (
            f"Destination: {data.get('name')}\n"
            f"ID: {data.get('id')}\n"
            f"City: {data.get('city')}\n"
            f"Category: {data.get('category')}\n"
            f"Price Tier: {data.get('price_tier')}\n"
            f"Rating: {data.get('rating')}/5\n"
            f"Description: {data.get('description')}\n"
            f"Tags: {', '.join(data.get('tags', []))}"
        )
    except Exception as e:
        return f"Error retrieving destination details: {e}"


def add_destination(
    name: str,
    city: str,
    category: str,
    description: str,
    price_tier: str = "Moderate",
    rating: float = 4.5,
    tags: str = "",
) -> str:
    """Add a new travel destination recommendation to the Firestore database.

    Args:
        name: Name of the destination or attraction.
        city: City where the destination is located.
        category: Category (e.g., 'Scenic & Outdoor', 'Dining', 'Culture', 'Nightlife').
        description: A brief summary or highlight of the spot.
        price_tier: Price tier string (e.g., 'Budget', 'Moderate', 'Upscale', 'Luxury').
        rating: Rating out of 5.0. Defaults to 4.5.
        tags: Comma-separated tags (e.g., 'foodie, scenic, family-friendly').

    Returns:
        Confirmation message with the created destination ID.
    """
    try:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
        doc_id = f"dest_{city.lower().replace(' ', '_')}_{uuid.uuid4().hex[:6]}"
        data = {
            "id": doc_id,
            "name": name,
            "city": city,
            "category": category,
            "description": description,
            "price_tier": price_tier,
            "rating": float(rating),
            "tags": tag_list,
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        db.collection(COLLECTION_NAME).document(doc_id).set(data)
        return f"Successfully added destination '{name}' to Firestore database with ID: {doc_id}!"
    except Exception as e:
        return f"Error adding destination to Firestore: {e}"


import json
import urllib.parse
import urllib.request

def fetch_live_weather(city: str) -> str:
    """Fetch real-time weather information for any city worldwide using live weather APIs.

    Args:
        city: The name of the city (e.g. 'San Francisco', 'Paris', 'Tokyo', 'Rome').

    Returns:
        A string summarizing current temperature, weather conditions, wind speed, and humidity.
    """
    try:
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={urllib.parse.quote(city)}&count=1&language=en&format=json"
        req = urllib.request.Request(geo_url, headers={"User-Agent": "WanderlustTravelApp/1.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            geo_data = json.loads(response.read().decode())

        if not geo_data.get("results"):
            return f"Could not find location coordinates for '{city}'."

        location = geo_data["results"][0]
        lat = location["latitude"]
        lon = location["longitude"]
        city_name = location.get("name", city)
        country = location.get("country", "")

        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,wind_speed_10m&temperature_unit=fahrenheit&wind_speed_unit=mph"
        req_w = urllib.request.Request(weather_url, headers={"User-Agent": "WanderlustTravelApp/1.0"})
        with urllib.request.urlopen(req_w, timeout=5) as resp_w:
            weather_data = json.loads(resp_w.read().decode())

        current = weather_data.get("current", {})
        temp = current.get("temperature_2m")
        humidity = current.get("relative_humidity_2m")
        wind = current.get("wind_speed_10m")

        return (
            f"Current live weather for {city_name}, {country}:\n"
            f"• Temperature: {temp}°F\n"
            f"• Relative Humidity: {humidity}%\n"
            f"• Wind Speed: {wind} mph"
        )
    except Exception as e:
        return f"Error fetching live weather for {city}: {e}"


def get_current_time(query: str) -> str:
    """Get current time for a city.

    Args:
        query: City name or timezone query.

    Returns:
        Formatted timestamp string.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        tz_identifier = "America/Los_Angeles"
    elif "paris" in query.lower():
        tz_identifier = "Europe/Paris"
    elif "kyoto" in query.lower() or "tokyo" in query.lower():
        tz_identifier = "Asia/Tokyo"
    else:
        tz_identifier = "America/New_York"

    tz = ZoneInfo(tz_identifier)
    now = datetime.datetime.now(tz)
    return f"The current time for query {query} is {now.strftime('%Y-%m-%d %H:%M:%S %Z%z')}"


def convert_travel_currency(amount: float = 100.0, from_currency: str = "USD", to_currency: str = "EUR") -> str:
    """Convert an amount from one currency to another using real-time foreign exchange rates for travel budgeting.

    Args:
        amount: The monetary amount to convert (e.g. 100.0). Defaults to 100.0.
        from_currency: 3-letter currency code to convert from (e.g., 'USD', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD').
        to_currency: 3-letter currency code to convert to (e.g., 'EUR', 'JPY', 'GBP', 'USD', 'CHF').

    Returns:
        A string with the calculated conversion and real-time exchange rate.
    """
    try:
        from_curr = from_currency.upper().strip()
        to_curr = to_currency.upper().strip()
        if from_curr == to_curr:
            return f"{amount} {from_curr} is equal to {amount} {to_curr}."

        url = f"https://api.frankfurter.app/latest?amount={amount}&from={from_curr}&to={to_curr}"
        api_key = os.getenv("EXCHANGE_RATE_API_KEY")
        if api_key:
            url += f"&key={api_key}"

        req = urllib.request.Request(url, headers={"User-Agent": "WanderlustTravelApp/1.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())

        rates = data.get("rates", {})
        converted_amount = rates.get(to_curr)
        rate_date = data.get("date", "recent")

        if converted_amount is None:
            return f"Could not convert from '{from_curr}' to '{to_curr}'."

        rate_per_unit = converted_amount / amount
        return (
            f"Foreign Exchange Conversion ({rate_date}):\n"
            f"• {amount:,.2f} {from_curr} = {converted_amount:,.2f} {to_curr}\n"
            f"• Rate: 1 {from_curr} = {rate_per_unit:,.4f} {to_curr}"
        )
    except Exception as e:
        return f"Error fetching exchange rate: {e}"


def geocode_address(address: str) -> str:
    """Convert an address, landmark, or location string into geographic latitude and longitude coordinates using Google Maps Geocoding API.

    Args:
        address: The location, address, or landmark string (e.g. 'Eiffel Tower, Paris', 'Times Square, NYC', '1600 Amphitheatre Pkwy, Mountain View').

    Returns:
        Formatted address, latitude, and longitude coordinates.
    """
    try:
        api_key = os.getenv("GOOGLE_MAPS_API_KEY")
        if not api_key:
            return "Error: GOOGLE_MAPS_API_KEY environment variable is not set."

        encoded_address = urllib.parse.quote(address)
        url = f"https://maps.googleapis.com/maps/api/geocode/json?address={encoded_address}&key={api_key}"
        req = urllib.request.Request(url, headers={"User-Agent": "WanderlustTravelApp/1.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())

        if data.get("status") != "OK" or not data.get("results"):
            return f"Geocoding failed for address '{address}'. Status: {data.get('status', 'ZERO_RESULTS')}"

        result = data["results"][0]
        formatted_address = result.get("formatted_address", address)
        location = result["geometry"]["location"]
        lat = location["lat"]
        lng = location["lng"]

        return (
            f"Geocoding Result:\n"
            f"• Name/Address: {formatted_address}\n"
            f"• Latitude: {lat}\n"
            f"• Longitude: {lng}"
        )
    except Exception as e:
        return f"Error during geocoding: {e}"


def find_nearby_places(latitude: float, longitude: float, place_type: str = "tourist_attraction", radius_meters: float = 2000.0) -> str:
    """Find nearby places (restaurants, tourist attractions, cafes, museums, lodging) around coordinates using Google Places API (New).

    Args:
        latitude: Latitude coordinate (e.g. 48.85837).
        longitude: Longitude coordinate (e.g. 2.29448).
        place_type: Type of place to search for (e.g. 'restaurant', 'tourist_attraction', 'cafe', 'museum', 'lodging', 'park'). Defaults to 'tourist_attraction'.
        radius_meters: Search radius in meters (e.g. 2000.0). Defaults to 2000.0.

    Returns:
        List of nearby places with name, formatted address, location coordinates, and rating.
    """
    try:
        api_key = os.getenv("GOOGLE_MAPS_API_KEY")
        if not api_key:
            return "Error: GOOGLE_MAPS_API_KEY environment variable is not set."

        url = "https://places.googleapis.com/v1/places:searchNearby"
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location,places.rating",
            "User-Agent": "WanderlustTravelApp/1.0",
        }
        payload = {
            "includedTypes": [place_type.lower().strip()],
            "maxResultCount": 5,
            "locationRestriction": {
                "circle": {
                    "center": {
                        "latitude": float(latitude),
                        "longitude": float(longitude),
                    },
                    "radius": float(radius_meters),
                }
            },
        }

        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())

        places = data.get("places", [])
        if not places:
            return f"No nearby places of type '{place_type}' found within {radius_meters}m of ({latitude}, {longitude})."

        formatted_places = []
        for p in places:
            display_name = p.get("displayName", {}).get("text", "Unknown Name")
            address = p.get("formattedAddress", "N/A")
            loc = p.get("location", {})
            lat = loc.get("latitude", "N/A")
            lng = loc.get("longitude", "N/A")
            rating = p.get("rating", "N/A")
            formatted_places.append(
                f"- Name: {display_name}\n"
                f"  Address: {address}\n"
                f"  Location: ({lat}, {lng})\n"
                f"  Rating: {rating}/5"
            )

        return f"Nearby '{place_type}' Places:\n" + "\n".join(formatted_places)
    except Exception as e:
        return f"Error searching nearby places: {e}"


async def generate_destination_image(
    description: str,
    tool_context: ToolContext = None,
) -> str:
    """Generate a high-quality travel image or postcard for a destination, landmark, scene, or dish using Gemini 3.1 Flash Lite Image model.
    Saves the generated image as an artifact in Playground and uploads it directly to public Google Cloud Storage to return its public HTTPS URL.

    Args:
        description: Description of the destination, landmark, scene, or dish to generate an image for (e.g., 'Eiffel Tower at sunset with cherry blossoms', 'Kyoto Bamboo Forest path in morning mist').

    Returns:
        The public HTTPS URL of the generated image stored in Google Cloud Storage.
    """
    try:
        genai_client = genai.Client(vertexai=True, project=FIRESTORE_PROJECT_ID, location="global")
        prompt = f"A scenic, high-quality travel postcard photo of: {description}"

        response = genai_client.models.generate_content(
            model="gemini-3.1-flash-lite-image",
            contents=prompt,
            config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
        )

        if not response.candidates or not response.candidates[0].content.parts:
            return "Failed to generate image: No content returned from model."

        image_part = None
        for part in response.candidates[0].content.parts:
            if part.inline_data:
                image_part = part
                break

        if not image_part:
            return "Failed to generate image: No inline image data in model response."

        image_bytes = image_part.inline_data.data
        mime_type = image_part.inline_data.mime_type or "image/jpeg"
        ext = "jpg" if "jpeg" in mime_type.lower() else "png"
        filename = f"destination_{uuid.uuid4().hex[:8]}.{ext}"

        # 1. Save artifact if tool_context is provided
        if tool_context and hasattr(tool_context, "save_artifact"):
            part_for_artifact = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
            await tool_context.save_artifact(filename=filename, artifact=part_for_artifact)

        # 2. Upload directly to public Cloud Storage from memory (no local file path returned)
        storage_client = storage.Client(project=FIRESTORE_PROJECT_ID)
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(filename)
        blob.upload_from_string(image_bytes, content_type=mime_type)

        public_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{filename}"
        return f"Successfully generated destination image! Public URL: {public_url}"

    except Exception as e:
        return f"Error generating destination image: {e}"


async def generate_destination_video(
    description: str,
    tool_context: ToolContext = None,
) -> str:
    """Generate a short promotional video clip for a travel destination, attraction, landmark, or scenic venue using Google's Omni model (gemini-omni-flash-preview).
    Saves the generated video as an artifact in Playground and uploads it directly to public Google Cloud Storage to return its public HTTPS URL.

    Args:
        description: Description of the travel destination, landmark, venue, or attraction to generate a short video for (e.g., 'Kyoto Bamboo Forest path in morning breeze', 'Eiffel Tower glowing at night').

    Returns:
        The public HTTPS URL of the generated video stored in Google Cloud Storage.
    """
    try:
        genai_client = genai.Client(vertexai=True, project=FIRESTORE_PROJECT_ID, location="global")
        prompt = f"Generate a short video clip showing: {description}"

        interaction = genai_client.interactions.create(
            model="gemini-omni-flash-preview",
            input=prompt,
        )

        video_bytes = None
        mime_type = "video/mp4"
        if hasattr(interaction, "output_video") and interaction.output_video:
            ov = interaction.output_video
            video_bytes = getattr(ov, "data", None) or getattr(ov, "video_bytes", None) or getattr(ov, "bytes", None)
            mime_type = getattr(ov, "mime_type", None) or "video/mp4"

        if not video_bytes:
            return "Failed to generate video: No video bytes returned from model."

        filename = f"destination_video_{uuid.uuid4().hex[:8]}.mp4"

        # 1. Save artifact if tool_context is provided
        if tool_context and hasattr(tool_context, "save_artifact"):
            part_for_artifact = types.Part.from_bytes(data=video_bytes, mime_type=mime_type)
            await tool_context.save_artifact(filename=filename, artifact=part_for_artifact)
            print(f"Artifact saved: {filename}")

        # 2. Upload directly to public Cloud Storage from memory (no local file path returned)
        storage_client = storage.Client(project=FIRESTORE_PROJECT_ID)
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(filename)
        blob.upload_from_string(video_bytes, content_type=mime_type)
        print(f"Uploaded to GCS: {GCS_BUCKET_NAME}/{filename}")

        public_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{filename}"
        return f"Successfully generated destination video! Public URL: {public_url}"

    except Exception as e:
        return f"Error generating destination video: {e}"


# WRITE: send session to Memory Bank for extraction after each turn
async def generate_memories_callback(callback_context: CallbackContext):
    try:
        await callback_context.add_session_to_memory()
    except ValueError:
        pass
    return None


# Read Agent Engine resource name from deployment_metadata.json if available
deployment_metadata_path = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "deployment_metadata.json"
)
agent_engine_resource_name = None
if os.path.exists(deployment_metadata_path):
    try:
        with open(deployment_metadata_path, "r") as f:
            metadata = json.load(f)
            agent_engine_resource_name = metadata.get("remote_agent_runtime_id")
    except Exception:
        pass

code_executor = AgentEngineSandboxCodeExecutor(
    agent_engine_resource_name=agent_engine_resource_name
)

# Extract Memory Bank ID from remote_agent_runtime_id
MEMORY_BANK_ID = (
    agent_engine_resource_name.split("/")[-1]
    if agent_engine_resource_name
    else "8796058937347538944"
)


def memory_service_builder():
    return VertexAiMemoryBankService(
        project=FIRESTORE_PROJECT_ID,
        location="us-east1",
        agent_engine_id=MEMORY_BANK_ID,
    )


schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

instruction = schema_manager.generate_system_prompt(
    role_description=(
        "You are Wanderlust Travel Concierge, a helpful AI travel assistant. "
        "Help users discover travel destinations, search curated recommendations from your Firestore database, "
        "add new destination spots to the database, check real-time live weather, convert foreign currency, "
        "geocode addresses into coordinates, find nearby restaurants and attractions, "
        "generate AI destination images and short travel videos, or write Python code blocks to execute code calculations in a sandbox.\n\n"
        "You remember the user's stated preferences, facts, and ALLERGIES (such as dietary restrictions, peanut allergies, gluten intolerance, shellfish allergies, or medical allergies) from previous conversations and use them to personalize your responses and travel/dining recommendations."
    ),
    workflow_description="Analyze the request, use tools as needed, and return structured UI when appropriate.",
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "You may include one Image component, but only when you have a public https "
        "URL for the image (for example the URL an image tool returns after uploading "
        "to a public bucket). Set the Image url to that exact https link, for example "
        "{\"Image\": {\"url\": {\"literalString\": \"https://...\"}}}. Never point an "
        "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the image instead. "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
        "headings and emphasis. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects."
    ),
    include_schema=True,
    include_examples=True,
)

root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-2.5-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=instruction,
    code_executor=code_executor,
    tools=[
        PreloadMemoryTool(),
        search_destinations,
        get_destination_details,
        add_destination,
        fetch_live_weather,
        convert_travel_currency,
        geocode_address,
        find_nearby_places,
        generate_destination_image,
        generate_destination_video,
        get_current_time,
    ],
    after_model_callback=a2ui_callback,
    after_agent_callback=generate_memories_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)
