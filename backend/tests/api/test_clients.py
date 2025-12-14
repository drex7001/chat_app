import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from app.main import app

def random_suffix():
    return str(uuid.uuid4())[:8]

@pytest.mark.asyncio
async def test_create_client():
    transport = ASGITransport(app=app)
    uid = random_suffix()
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/clients/", json={
            "name": f"Test Co {uid}", 
            "external_id": f"test_co_{uid}",
            "config": {
                "prompts": {
                    "system_instruction": "Be helpful.",
                    "task_specific_prompts": {"abc": "def"}
                }
            }
        })
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == f"Test Co {uid}"
    assert data["config"]["prompts"]["system_instruction"] == "Be helpful."
    assert "id" in data

@pytest.mark.asyncio
async def test_duplicate_client():
    transport = ASGITransport(app=app)
    uid = random_suffix()
    ext_id = f"duplicate_{uid}"
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r1 = await ac.post("/clients/", json={"name": "Test Co", "external_id": ext_id})
        print(f"DEBUG: r1 status={r1.status_code} body={r1.text}")
        assert r1.status_code == 201
        response = await ac.post("/clients/", json={"name": "Test Co", "external_id": ext_id})
        print(f"DEBUG: r2 status={response.status_code} body={response.text}")
    assert response.status_code == 400

@pytest.mark.asyncio
async def test_list_clients():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/clients/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

@pytest.mark.asyncio
async def test_update_client():
    transport = ASGITransport(app=app)
    uid = random_suffix()
    # Create client
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        create_res = await ac.post("/clients/", json={"name": f"Update {uid}", "external_id": f"update_{uid}"})
        client_id = create_res.json()["id"]
        
        # Update
        response = await ac.patch(f"/clients/{client_id}", json={
            "name": "Updated Name",
            "config": {"prompts": {"system_instruction": "New prompt"}}
        })
        
    assert response.status_code == 200
    assert response.json()["name"] == "Updated Name"
    assert response.json()["config"]["prompts"]["system_instruction"] == "New prompt"
