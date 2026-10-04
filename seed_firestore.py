# Copyright 2026 Google LLC
# Seed script for Wanderlust Travel Concierge Firestore collection

import os
from google.cloud import firestore

# CRITICAL: Hardcode the GCP Project ID as a string.
# Do NOT use os.getenv("GOOGLE_CLOUD_PROJECT") or google.auth.default()
# because Agent Platform returns the project NUMBER, breaking Firestore.
FIRESTORE_PROJECT_ID = "qwiklabs-gcp-03-faf61ce9a80f"

db = firestore.Client(project=FIRESTORE_PROJECT_ID)

COLLECTION_NAME = "destinations"

SAMPLE_DESTINATIONS = [
    {
        "id": "dest_sf_coastal",
        "name": "San Francisco Coastal Highway & Marin Headlands",
        "city": "San Francisco",
        "category": "Scenic & Outdoor",
        "description": "Breathtaking ocean views, Golden Gate Bridge vistas, and coastal hiking trails.",
        "price_tier": "$$",
        "rating": 4.9,
        "tags": ["scenic", "nature", "coastal", "hiking"]
    },
    {
        "id": "dest_kyoto_bamboo",
        "name": "Kyoto Arashiyama Bamboo Grove & Tenryu-ji Temple",
        "city": "Kyoto",
        "category": "Culture & Heritage",
        "description": "Serene bamboo paths leading to historic UNESCO World Heritage zen temples and tea gardens.",
        "price_tier": "$$",
        "rating": 4.8,
        "tags": ["culture", "historic", "temple", "tranquil"]
    },
    {
        "id": "dest_paris_bistro",
        "name": "Le Marais Culinary Walk & Classic Bistro Experience",
        "city": "Paris",
        "category": "Dining & Gastronomy",
        "description": "Authentic French patisseries, artisanal cheese shops, and charming historic neighborhood bistros.",
        "price_tier": "$$$",
        "rating": 4.7,
        "tags": ["foodie", "dining", "culture", "city-walk"]
    },
    {
        "id": "dest_tokyo_ginza",
        "name": "Ginza Luxury Shopping & Rooftop Gardens",
        "city": "Tokyo",
        "category": "Shopping & Luxury",
        "description": "High-end flagship stores, Michelin-starred dining, and modern architectural masterpieces.",
        "price_tier": "$$$$",
        "rating": 4.6,
        "tags": ["shopping", "luxury", "city", "dining"]
    },
    {
        "id": "dest_nyc_central_park",
        "name": "Central Park & Bethesda Terrace Walk",
        "city": "New York",
        "category": "Parks & Culture",
        "description": "Iconic Manhattan green space featuring picturesque bridges, Bethesda Fountain, and rowboats.",
        "price_tier": "$",
        "rating": 4.8,
        "tags": ["park", "scenic", "family-friendly", "iconic"]
    }
]

def seed():
    print(f"Seeding '{COLLECTION_NAME}' collection in project: {FIRESTORE_PROJECT_ID}...")
    collection_ref = db.collection(COLLECTION_NAME)
    for item in SAMPLE_DESTINATIONS:
        doc_ref = collection_ref.document(item["id"])
        doc_ref.set(item)
        print(f"  ✓ Added/Updated document: {item['id']} ({item['name']})")
    print("Seeding complete! ✅")

if __name__ == "__main__":
    seed()
