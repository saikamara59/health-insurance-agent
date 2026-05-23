"""GET /drugs/search — authenticated drug autocomplete backed by RxNav.

Silent-fail at the boundary: any exception from RxNavClient becomes an empty
matches list, not a 500. Autocomplete shouldn't crash on a flaky upstream.
"""
import logging

from fastapi import APIRouter, Depends, Query

from healthflow.auth.dependencies import get_current_broker
from healthflow.database.models import Broker
from healthflow.models.schemas import DrugMatchModel, DrugSearchResponse
from healthflow.tools.rxnav_client import RxNavClient

logger = logging.getLogger(__name__)

drug_router = APIRouter(prefix="/drugs", tags=["drugs"])


@drug_router.get("/search", response_model=DrugSearchResponse)
async def search_drugs(
    q: str = Query(..., min_length=1, max_length=100, description="Drug name to search for"),
    limit: int = Query(10, ge=1, le=50, description="Max matches to return"),
    broker: Broker = Depends(get_current_broker),
) -> DrugSearchResponse:
    """Autocomplete drug search backed by RxNav (NLM RxNorm REST API).

    Returns up to `limit` matches ordered by RxNorm's own concept-group ordering.
    Silent-fail: a RxNav outage returns an empty list, not a 500.
    """
    query = q.strip()
    try:
        async with RxNavClient() as rxnav:
            matches = await rxnav.search(query, limit=limit)
    except Exception as e:
        logger.warning("drugs.search rxnav client raised: %s", e)
        matches = []

    logger.info(
        "drugs.search broker_id=%s query_length=%d result_count=%d",
        broker.id, len(query), len(matches),
    )

    return DrugSearchResponse(
        query=query,
        matches=[
            DrugMatchModel(
                rxcui=m.rxcui,
                name=m.name,
                term_type=m.term_type,
                is_brand=m.is_brand,
            )
            for m in matches
        ],
    )
