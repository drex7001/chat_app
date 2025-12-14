import pytest
from app.db.session import get_db
# Inject mock agents BEFORE importing app modules
import tests.mocks.openai_agents_mock
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def mock_db_session():
    session = AsyncMock()
    # db.execute returns a Result proxy which is synchronous after await
    # So the return_value of execute() should be a MagicMock, not AsyncMock
    session.execute.return_value = MagicMock()
    return session

@pytest.fixture
def mock_crm_client():
    return AsyncMock()

@pytest.fixture
def mock_ops_client():
    return AsyncMock()
