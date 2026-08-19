import hashlib
import random
import time

from app.integrations.base import ProviderCallResult

_COUNTRIES = ["China", "Vietnam", "India", "Turkey", "Mexico", "Poland", "Indonesia"]
_COMPANY_SUFFIXES = ["Manufacturing Co.", "Trading Ltd.", "Industries", "Global Supply", "Group"]


class MockSupplierProvider:
    """Deterministic fake supplier-discovery provider.

    Generates plausible supplier candidates and quoted terms for a product with zero
    external dependencies, seeded from the product title for stable demo results.
    """

    name = "mock"

    def find_suppliers(
        self,
        product_title: str,
        category: str | None,
        target_unit_price: float,
        currency: str = "USD",
    ) -> ProviderCallResult:
        start = time.perf_counter()
        seed = int(hashlib.sha256(product_title.lower().encode()).hexdigest(), 16) % (2**32)
        rng = random.Random(seed)

        count = rng.randint(3, 6)
        suppliers = []
        for i in range(count):
            country = rng.choice(_COUNTRIES)
            company_name = (
                f"{country.split()[0]}{rng.choice(['Tek', 'Well', 'Pro', 'Star', 'Prime'])} "
                f"{rng.choice(_COMPANY_SUFFIXES)}"
            )
            price_variance = rng.uniform(0.5, 0.85)
            suppliers.append(
                {
                    "name": company_name,
                    "country": country,
                    "website": f"https://{company_name.lower().replace(' ', '')}.example.com",
                    "contact_email": f"sales@{company_name.lower().replace(' ', '')}.example.com",
                    "contact_phone": f"+{rng.randint(1, 99)} {rng.randint(100000000, 999999999)}",
                    "unit_price": round(max(target_unit_price * price_variance, 0.5), 2),
                    "currency": currency,
                    "moq": rng.choice([50, 100, 200, 500, 1000]),
                    "lead_time_days": rng.randint(7, 45),
                    "shipping_method": rng.choice(["Sea Freight", "Air Freight", "Express Courier"]),
                    "shipping_cost": round(rng.uniform(50, 800), 2),
                    "notes": "Auto-generated candidate for MVP evaluation.",
                }
            )

        latency_ms = int((time.perf_counter() - start) * 1000)
        request = {
            "product_title": product_title,
            "category": category,
            "target_unit_price": target_unit_price,
            "currency": currency,
        }
        response = {"results": suppliers}
        return ProviderCallResult(
            provider_name=self.name,
            request=request,
            response=response,
            data=suppliers,
            latency_ms=latency_ms,
        )
