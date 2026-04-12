import uuid

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from healthflow.auth.dependencies import get_current_broker
from healthflow.database.config import get_db
from healthflow.database.models import Broker, Client
from healthflow.models.schemas import ClientCreate, ClientResponse, ClientUpdate

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
    """List all clients belonging to the current broker."""
    result = await db.execute(
        select(Client).where(Client.broker_id == broker.id)
    )
    clients = result.scalars().all()
    return [_client_to_response(c) for c in clients]


@client_router.get("/{client_id}", response_model=ClientResponse)
async def get_client(
    client_id: str,
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
) -> ClientResponse:
    """Get a specific client by ID. Must belong to the current broker."""
    try:
        parsed_id = uuid.UUID(client_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Client not found")

    result = await db.execute(select(Client).where(Client.id == parsed_id))
    client = result.scalar_one_or_none()

    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")

    if client.broker_id != broker.id:
        raise HTTPException(status_code=403, detail="Access denied")

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

    if client.broker_id != broker.id:
        raise HTTPException(status_code=403, detail="Access denied")

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

    if client.broker_id != broker.id:
        raise HTTPException(status_code=403, detail="Access denied")

    await db.delete(client)
    await db.flush()
    return Response(status_code=204)
