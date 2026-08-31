import asyncio
from fastapi.testclient import TestClient
from src.main import app
from src.core.security import get_current_user_with_role
from src.models.user import User
import uuid

def override_get_current_user():
    return User(
        id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        tenant_id=uuid.UUID("d3b07384-d113-46a6-a719-38cf89235d54"),
        role="owner"
    )

app.dependency_overrides[get_current_user_with_role] = override_get_current_user

client = TestClient(app)
response = client.get('/api/v1/prior-auth')
print("Status code:", response.status_code)
if response.status_code == 200:
    for item in response.json().get('data', []):
        print(f"Patient: {item['patient_name']}, Status: {item['status']}, Auth: {item['auth_status']}")
else:
    print(response.text)
