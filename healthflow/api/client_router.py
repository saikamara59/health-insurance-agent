import uuid

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from contextlib import nullcontext

from healthflow.auth.dependencies import get_current_broker
from healthflow.auth.tenant_context import system_context
from healthflow.database.config import get_db
from healthflow.database.models import Broker, Client
from healthflow.models.schemas import ClientCreate, ClientResponse, ClientUpdate


def _admin_bypass(broker: Broker):
    """Cross-tenant read bypass for admins.

    Admins use the workspace view to audit, support, and run forensics on
    any broker's book. Wrapping the SELECT in system_context() suspends
    the tenant filter for the duration of that read. Writes deliberately
    stay scoped — admins can see everyone's clients but cannot mutate
    them through the same endpoint.
    """
    if broker.role == "admin":
        return system_context(f"admin cross-tenant read: {broker.email}")
    return nullcontext()

client_router = APIRouter(prefix="/clients", tags=["clients"])


def _client_to_response(client: Client) -> ClientResponse:
    """Convert a Client ORM model to a ClientResponse Pydantic model."""
    return ClientResponse(
        id=str(client.id),
        broker_id=str(client.broker_id),
        full_name=client.full_name,
        zip_code=client.zip_code,
        age=client.age,
        income_level=client.income_level,
        doctors=client.doctors,
        prescriptions=client.prescriptions,
        procedures=client.procedures,
        created_at=client.created_at.isoformat(),
        updated_at=client.updated_at.isoformat(),
    )


@client_router.post("", response_model=ClientResponse, status_code=201)
async def create_client(
    client_data: ClientCreate,
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
) -> ClientResponse:
    """Create a new client profile for the current broker."""
    client = Client(
        broker_id=broker.id,
        full_name=client_data.full_name,
        zip_code=client_data.zip_code,
        age=client_data.age,
        income_level=client_data.income_level,
        doctors=client_data.doctors,
        prescriptions=client_data.prescriptions,
        procedures=client_data.procedures,
    )
    db.add(client)
    await db.flush()
    await db.refresh(client)
    return _client_to_response(client)


@client_router.get("", response_model=list[ClientResponse])
async def list_clients(
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
) -> list[ClientResponse]:
    """List clients. Brokers see their own book; admins see every broker's."""
    # Brokers: tenant filter auto-injects WHERE Client.broker_id = broker.id.
    # Admins: _admin_bypass suspends the filter so the workspace view is whole.
    with _admin_bypass(broker):
        result = await db.execute(select(Client))
        clients = result.scalars().all()
    return [_client_to_response(c) for c in clients]


@client_router.get("/{client_id}", response_model=ClientResponse)
async def get_client(
    client_id: str,
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
) -> ClientResponse:
    """Get a specific client by ID. Brokers: own book only. Admins: any."""
    try:
        parsed_id = uuid.UUID(client_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Client not found")

    with _admin_bypass(broker):
        result = await db.execute(select(Client).where(Client.id == parsed_id))
        client = result.scalar_one_or_none()

    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")

    return _client_to_response(client)


@client_router.put("/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: str,
    update_data: ClientUpdate,
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
) -> ClientResponse:
    """Update a client's profile. Must belong to the current broker."""
    try:
        parsed_id = uuid.UUID(client_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Client not found")

    result = await db.execute(select(Client).where(Client.id == parsed_id))
    client = result.scalar_one_or_none()

    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")

    # Apply only the fields that were explicitly set
    update_fields = update_data.model_dump(exclude_unset=True)
    for field, value in update_fields.items():
        setattr(client, field, value)

    await db.flush()
    await db.refresh(client)
    return _client_to_response(client)


@client_router.delete("/{client_id}", status_code=204)
async def delete_client(
    client_id: str,
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Delete a client. Must belong to the current broker."""
    try:
        parsed_id = uuid.UUID(client_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Client not found")

    result = await db.execute(select(Client).where(Client.id == parsed_id))
    client = result.scalar_one_or_none()

    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")

    # tenant filter auto-injects AND Client.broker_id = current_broker_id
    await db.execute(delete(Client).where(Client.id == parsed_id))
    await db.flush()
    return Response(status_code=204)
