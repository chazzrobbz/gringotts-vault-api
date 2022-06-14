import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, AsyncConnection
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql.ddl import CreateSchema, DropSchema
from pika.adapters.blocking_connection import BlockingChannel
from gringotts.config import get_settings
from gringotts.database import engine
from gringotts.main import app
from gringotts.models.base import Base
from seed.seed_data import seed
from worker.queueing import create_queue_channel


@pytest.fixture(
    params=[
        pytest.param(("asyncio", {"use_uvloop": True}), id="asyncio+uvloop"),
    ]
)
def anyio_backend(request):
    return request.param


def pytest_addoption(parser):
    parser.addoption(
        "--seed-data", action="store", default="", help="seeds the database wth data before running the tests"
    )

async def start_db():
    async with engine.begin() as conn:
        await conn.execute(DropSchema('gringotts', cascade=True))
        await conn.execute(CreateSchema('gringotts'))
        conn: AsyncConnection = await conn.execution_options(schema_translate_map={None: "gringotts"})
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


    # for AsyncEngine created in function scope, close and
    # clean-up pooled connections
    await engine.dispose()

@pytest.fixture
async def goblin_channel(request) -> BlockingChannel:
    settings = get_settings()
    return create_queue_channel(settings)


@pytest_asyncio.fixture
async def client(request) -> AsyncClient:
    async with AsyncClient(
            app=app,
            base_url="http://testserver",
            headers={"Content-Type": "application/json"},
    ) as client:
        await start_db()

        yield client
        # for AsyncEngine created in function scope, close and
        # clean-up pooled connections
        await engine.dispose()


@pytest_asyncio.fixture()
async def db_session(request) -> AsyncSession:
    async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    if request.config.getoption("--seed-data"):
        await seed(async_session)
    async with async_session() as session:
        yield session





