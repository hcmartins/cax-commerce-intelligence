import hashlib
import random
import time
from typing import Any

from app.integrations.base import ProviderCallResult

# Genuine, independent product concepts per category — never derived from the
# query text. This is the fix for the bug where a title like "Compact Find 10
# Products Suitable For A £200 Test Budget Pro" leaked the raw search request:
# the old version built titles as f"{adjective} {query} {suffix}". Titles now
# come only from this catalog; the query only influences *which* candidates and
# how many are picked (see `opportunity/query_parsing.py`).
_CATALOG: dict[str, list[str]] = {
    "Home & Kitchen": [
        "Adjustable Drawer Organiser Set",
        "Reusable Silicone Food Storage Set",
        "Cable Management Box",
        "Collapsible Kitchen Colander",
        "Magnetic Spice Rack Set",
        "Bamboo Cutting Board Set",
        "Over-the-Sink Dish Drying Rack",
        "Airtight Pantry Storage Containers",
        "Non-Slip Drawer Liner Roll",
        "Stackable Fridge Organiser Bins",
    ],
    "Fitness": [
        "Resistance Band Set",
        "Foldable Yoga Mat",
        "Adjustable Ankle Weights",
        "Compact Foam Roller",
        "Grip Strengthener Set",
        "Portable Pull-Up Bar",
        "Massage Gun Attachment Set",
        "Non-Slip Exercise Sliders",
        "Jump Rope with Counter",
        "Compact Resistance Loop Bands",
    ],
    "Pet Supplies": [
        "Pet Hair Remover Roller",
        "Car Seat Gap Organiser",
        "Collapsible Travel Pet Bowl",
        "Automatic Pet Water Fountain",
        "Anti-Slip Pet Feeding Mat",
        "Retractable Dog Leash",
        "Pet Grooming Glove Set",
        "Cat Scratching Post Pad",
        "Pet Car Seat Cover",
        "Interactive Treat Dispenser Toy",
    ],
    "Electronics Accessories": [
        "Cable Management Box",
        "Wireless Charging Stand",
        "Adjustable Laptop Stand",
        "Multi-Port USB Hub",
        "Phone Camera Lens Kit",
        "Magnetic Cable Organiser Clips",
        "Compact Bluetooth Tracker Tag",
        "Foldable Phone Stand",
        "Portable SSD Carrying Case",
        "Anti-Glare Screen Protector Kit",
    ],
    "Outdoors": [
        "Portable Camping Lantern",
        "Compact Travel Hammock",
        "Foldable Camping Chair",
        "Insulated Water Bottle Sleeve",
        "Collapsible Water Container",
        "Multi-Tool Carabiner Clip",
        "Waterproof Dry Bag",
        "Compact Camping Cookware Set",
        "Portable Solar Power Bank",
        "Reusable Hand Warmers",
    ],
}

_PRICE_RANGE_BY_CATEGORY = {
    "Home & Kitchen": (8.0, 45.0),
    "Fitness": (10.0, 60.0),
    "Pet Supplies": (7.0, 40.0),
    "Electronics Accessories": (9.0, 55.0),
    "Outdoors": (12.0, 65.0),
}

# Loose keyword -> category bias so a query like "kitchen storage" leans toward
# relevant categories without ever putting the query's own words into a title.
_CATEGORY_KEYWORDS = {
    "Home & Kitchen": ["kitchen", "home", "storage", "organiser", "organizer", "drawer"],
    "Fitness": ["fitness", "gym", "workout", "exercise", "training"],
    "Pet Supplies": ["pet", "dog", "cat", "puppy", "kitten"],
    "Electronics Accessories": ["electronic", "phone", "laptop", "charger", "cable", "usb"],
    "Outdoors": ["outdoor", "camping", "hiking", "travel", "garden"],
}


def _biased_categories(query: str) -> list[str]:
    lowered = query.lower()
    matched = [cat for cat, keywords in _CATEGORY_KEYWORDS.items() if any(k in lowered for k in keywords)]
    return matched or list(_CATALOG.keys())


class MockSearchProvider:
    """Deterministic fake product-discovery provider.

    Generates a plausible set of candidate products for a query with zero external
    dependencies, so the full pipeline is runnable/testable without any API keys.
    Results are seeded from the query text so the same query returns stable results.
    Product titles always come from a fixed catalog of genuine product concepts —
    the query is used only to pick a category bias, a price range and a count, not
    as content for the titles themselves.
    """

    name = "mock"

    def search_products(
        self, query: str, filters: dict[str, Any] | None = None
    ) -> ProviderCallResult:
        start = time.perf_counter()
        filters = filters or {}
        seed = int(hashlib.sha256(query.lower().encode()).hexdigest(), 16) % (2**32)
        rng = random.Random(seed)

        count = int(filters.get("number_of_products") or filters.get("limit") or 8)
        count = max(1, min(count, 20))
        currency = filters.get("currency") or "USD"
        budget = filters.get("budget")
        preferred_categories = [c for c in (filters.get("preferred_categories") or []) if c in _CATALOG]

        categories = preferred_categories or _biased_categories(query)
        # (category, product_name) pairs, pooled across every biased category so a
        # count larger than one category's catalog still yields distinct products.
        pool: list[tuple[str, str]] = [
            (category, name) for category in categories for name in _CATALOG[category]
        ]
        rng.shuffle(pool)
        selected = pool[:count]

        candidates = []
        for category, title in selected:
            low, high = _PRICE_RANGE_BY_CATEGORY.get(category, (10.0, 50.0))
            if budget:
                # Keep a test-budget-compatible spread: a handful of unit economics
                # below the stated budget, capped so the range stays sane.
                high = min(high, max(low + 1, float(budget) * 0.6))
            price = round(rng.uniform(low, high), 2)
            candidates.append(
                {
                    "title": title,
                    "category": category,
                    "demand_score": round(rng.uniform(30, 95), 1),
                    "competition_score": round(rng.uniform(10, 90), 1),
                    "trend_score": round(rng.uniform(20, 95), 1),
                    "avg_selling_price": price,
                    "currency": currency,
                    "evidence": {
                        "monthly_search_volume": rng.randint(500, 50000),
                        "active_sellers": rng.randint(3, 400),
                        "trend_direction": rng.choice(["rising", "stable", "declining"]),
                    },
                }
            )

        latency_ms = int((time.perf_counter() - start) * 1000)
        request = {"query": query, "filters": filters}
        response = {"results": candidates}
        return ProviderCallResult(
            provider_name=self.name,
            request=request,
            response=response,
            data=candidates,
            latency_ms=latency_ms,
        )
