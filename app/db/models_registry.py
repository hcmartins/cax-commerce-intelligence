"""Import every ORM model so SQLAlchemy's mapper registry is fully configured.

This module has no runtime logic — it exists purely for its import side effects.
Import it (not the individual model modules) from Alembic's `env.py` and from
anywhere that needs `Base.metadata` to know about every table, so that string-based
relationship references between modules resolve correctly.
"""

from app.modules.operations.models import OperationsApproval  # noqa: F401
from app.modules.opportunity.models import ProductOpportunity  # noqa: F401
from app.modules.profitability.models import ProfitabilityCalculation, Recommendation  # noqa: F401
from app.modules.runs.models import SearchRun  # noqa: F401
from app.modules.suppliers.models import Supplier, SupplierOffer  # noqa: F401
from app.shared.models import IntegrationCallLog  # noqa: F401
