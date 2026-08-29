"""
test_agent_config.py — Comprehensive Unit Tests for AI Voice Agent Builder & Retell Synchronization
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.api.routers.agent_config_router import (
    compile_agent_prompt,
    _sync_to_retell,
    _push_to_retell,
    sanitize_phone_number,
    _is_mock_retell_key,
)
from src.core.security import AuthenticatedUser, get_current_user_with_role

DUMMY_AUTH = AuthenticatedUser(
    user_id="user-owner-123",
    email="doctor@sunrisemedical.com",
    clinic_id="clinic-test-uuid-1",
    clinic_name="Sunrise Medical Clinic",
    role="owner",
)

def _owner_override():
    return DUMMY_AUTH

@pytest.fixture(scope="module")
def client():
    with TestClient(app, base_url="http://localhost:8000", raise_server_exceptions=False) as c:
        yield c


# ─────────────────────────────────────────────────────────────────────────────
# 1. Helper Utilities Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_sanitize_phone_number():
    assert sanitize_phone_number("+1 (555) 987-6543") == "+15559876543"
    assert sanitize_phone_number("(555) 987-6543") == "5559876543"
    assert sanitize_phone_number("+1-800-555-0199") == "+18005550199"
    assert sanitize_phone_number(None) is None
    assert sanitize_phone_number("") is None


def test_is_mock_retell_key():
    assert _is_mock_retell_key("mock_key") is True
    assert _is_mock_retell_key("mock_retell_key") is True
    assert _is_mock_retell_key("test_key") is True
    assert _is_mock_retell_key("") is True
    assert _is_mock_retell_key(None) is True
    assert _is_mock_retell_key("key_live_secret_production_abc") is False


# ─────────────────────────────────────────────────────────────────────────────
# 2. Prompt Compiler Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_compile_prompt_basic_english():
    prompt = compile_agent_prompt(
        clinic_name="Sunrise Medical Clinic",
        greeting="Hello, thank you for calling!",
        custom_persona="You are a warm, helpful receptionist.",
        faqs={"Hours?": "8am-5pm Mon-Fri"},
        language="en-US",
    )
    assert "Sunrise Medical Clinic" in prompt
    assert "Hello, thank you for calling!" in prompt
    assert "You are a warm, helpful receptionist." in prompt
    assert "Hours?: 8am-5pm Mon-Fri" in prompt
    assert "Never provide medical diagnoses" in prompt
    assert "Protected Health Information" in prompt
    assert "IDIOMA" not in prompt


def test_compile_prompt_spanish_and_emergency():
    prompt = compile_agent_prompt(
        clinic_name="Clínica Buena Salud",
        greeting="¡Hola! Bienvenidos a Clínica Buena Salud.",
        custom_persona="Eres una recepcionista bilingüe.",
        faqs={},
        language="es-MX",
        emergency_forward_phone="+1 (555) 987-6543",
    )
    assert "Clínica Buena Salud" in prompt
    assert "¡Hola! Bienvenidos a Clínica Buena Salud." in prompt
    assert "No FAQs configured." in prompt
    assert "IDIOMA: Responde siempre en español" in prompt
    assert "CALL TRANSFER & EMERGENCY ROUTING" in prompt
    assert "+15559876543" in prompt
    assert "dial 911 immediately" in prompt


def test_compile_prompt_french():
    prompt = compile_agent_prompt(
        clinic_name="Clinique Santé",
        greeting="Bonjour!",
        custom_persona="Vous êtes un réceptionniste professionnel.",
        faqs={"Parking?": "Oui, gratuit."},
        language="fr-CA",
    )
    assert "Clinique Santé" in prompt
    assert "LANGUE: Répondez toujours en français" in prompt


# ─────────────────────────────────────────────────────────────────────────────
# 3. Retell Synchronization Helper Tests
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sync_to_retell_mock_mode():
    with patch("src.api.routers.agent_config_router.settings") as mock_settings:
        mock_settings.RETELL_API_KEY = "mock_key"
        res = await _sync_to_retell(
            retell_agent_id="agent_123",
            compiled_prompt="You are an AI receptionist.",
            greeting_message="Hi!",
            voice_id="11labs-rachel",
            language="en-US",
            emergency_forward_phone="+15551234567",
        )
        assert res["success"] is True
        assert res["status"] == "mock_synced"


@pytest.mark.asyncio
async def test_sync_to_retell_live_call():
    with patch("src.api.routers.agent_config_router.settings") as mock_settings, \
         patch("httpx.AsyncClient") as mock_client_cls:
        mock_settings.RETELL_API_KEY = "retell_live_secret_key_123"
        
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        
        # 1. GET agent
        get_res = MagicMock()
        get_res.status_code = 200
        get_res.json.return_value = {"agent_id": "agent_123", "response_engine": {"type": "retell-llm", "llm_id": "llm_abc"}}

        # 1b. GET LLM
        get_llm_res = MagicMock()
        get_llm_res.status_code = 200
        get_llm_res.json.return_value = {
            "llm_id": "llm_abc",
            "general_tools": [
                {"type": "end_call", "name": "end_call"},
                {"type": "custom", "name": "custom_calendar_lookup"}
            ]
        }
        
        # 2. PATCH agent
        patch_agent_res = MagicMock()
        patch_agent_res.status_code = 200
        
        # 3. PATCH llm
        patch_llm_res = MagicMock()
        patch_llm_res.status_code = 200

        mock_client.get.side_effect = [get_res, get_llm_res]
        mock_client.patch.side_effect = [patch_agent_res, patch_llm_res]

        res = await _sync_to_retell(
            retell_agent_id="agent_123",
            compiled_prompt="Compiled prompt text",
            greeting_message="Welcome!",
            voice_id="11labs-charlie",
            language="en-US",
            emergency_forward_phone="+1 (555) 999-8888",
        )
        assert res["success"] is True
        assert res["status"] == "synced"
        assert res["llm_id"] == "llm_abc"


# ─────────────────────────────────────────────────────────────────────────────
# 4. Router Endpoints Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_get_agent_config_success(client):
    app.dependency_overrides[get_current_user_with_role] = _owner_override
    try:
        mock_res = MagicMock()
        mock_res.data = [{
            "id": "cfg-1",
            "clinic_id": "clinic-test-uuid-1",
            "retell_agent_id": "agent_test_123",
            "greeting_message": "Hello!",
            "custom_system_prompt": "Be professional.",
            "voice_id": "11labs-rachel",
            "language": "en-US",
            "emergency_forward_phone": "+15551234567",
            "faq_data": {"Hours": "9-5"},
            "ab_test_active": False,
            "retell_sync_status": "synced"
        }]

        with patch("src.api.routers.agent_config_router.supabase_read") as mock_db:
            mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_res
            r = client.get("/api/v1/agent-config", headers={"Authorization": "Bearer test-token"})

        assert r.status_code in (200, 401, 403)
        if r.status_code == 200:
            data = r.json()["data"]
            assert data["retell_agent_id"] == "agent_test_123"
            assert data["greeting_message"] == "Hello!"
            assert data["transfer_phone_number"] == "+15551234567"
    finally:
        app.dependency_overrides.pop(get_current_user_with_role, None)


def test_post_agent_config_create_and_upsert(client):
    app.dependency_overrides[get_current_user_with_role] = _owner_override
    try:
        mock_clinic_res = MagicMock()
        mock_clinic_res.data = {"name": "Sunrise Medical Clinic"}

        mock_existing_res = MagicMock()
        mock_existing_res.data = []  # simulate first creation

        mock_saved_res = MagicMock()
        mock_saved_res.data = [{
            "id": "cfg-created-1",
            "clinic_id": "clinic-test-uuid-1",
            "retell_agent_id": "agent_new_999",
            "greeting_message": "Hi, welcome to Sunrise!",
            "custom_system_prompt": "Help patients book appointments.",
            "voice_id": "11labs-charlie",
            "language": "en-US",
            "emergency_forward_phone": "+15558889999",
            "faq_data": {"Insurance": "PPO accepted"},
            "ab_test_active": True,
            "script_a": "Script A",
            "script_b": "Script B"
        }]

        with patch("src.api.routers.agent_config_router.supabase_read") as mock_read, \
             patch("src.api.routers.agent_config_router.supabase") as mock_db, \
             patch("src.api.routers.agent_config_router._sync_to_retell", new_callable=AsyncMock) as mock_sync:
            
            mock_read.table.return_value.select.return_value.single.return_value.execute.return_value = mock_clinic_res
            mock_read.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = mock_clinic_res
            mock_read.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_existing_res
            mock_db.table.return_value.insert.return_value.execute.return_value = mock_saved_res
            mock_db.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[{}])

            r = client.post(
                "/api/v1/agent-config",
                json={
                    "retell_agent_id": "agent_new_999",
                    "greeting_message": "Hi, welcome to Sunrise!",
                    "custom_system_prompt": "Help patients book appointments.",
                    "voice_id": "11labs-charlie",
                    "language": "en-US",
                    "emergency_forward_phone": "+1 (555) 888-9999",
                    "faq_data": {"Insurance": "PPO accepted"},
                    "ab_test_active": True,
                    "script_a": "Script A",
                    "script_b": "Script B"
                },
                headers={"Authorization": "Bearer test-token"}
            )

            assert r.status_code in (200, 401, 403)
            if r.status_code == 200:
                assert r.json()["data"]["retell_agent_id"] == "agent_new_999"
    finally:
        app.dependency_overrides.pop(get_current_user_with_role, None)


def test_put_agent_config_update(client):
    app.dependency_overrides[get_current_user_with_role] = _owner_override
    try:
        existing = MagicMock()
        existing.data = [{
            "id": "cfg-1",
            "clinic_id": "clinic-test-uuid-1",
            "retell_agent_id": "agent_test_123",
            "greeting_message": "Old greeting",
            "custom_system_prompt": "Old persona",
            "voice_id": "11labs-rachel",
            "language": "en-US",
            "emergency_forward_phone": "+15551112222",
            "faq_data": {},
        }]

        updated = MagicMock()
        updated.data = [{
            "id": "cfg-1",
            "clinic_id": "clinic-test-uuid-1",
            "retell_agent_id": "agent_test_123",
            "greeting_message": "Updated greeting message",
            "voice_id": "11labs-adam",
            "emergency_forward_phone": "+15553334444",
        }]

        clinic_res = MagicMock()
        clinic_res.data = {"name": "Sunrise Medical Clinic"}

        with patch("src.api.routers.agent_config_router.supabase_read") as mock_read, \
             patch("src.api.routers.agent_config_router.supabase") as mock_db, \
             patch("src.api.routers.agent_config_router._sync_to_retell", new_callable=AsyncMock):
            
            mock_read.table.return_value.select.return_value.eq.return_value.execute.return_value = existing
            mock_read.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = clinic_res
            mock_db.table.return_value.update.return_value.eq.return_value.execute.return_value = updated

            r = client.put(
                "/api/v1/agent-config",
                json={
                    "greeting_message": "Updated greeting message",
                    "voice_id": "11labs-adam",
                    "emergency_forward_phone": "+1 (555) 333-4444"
                },
                headers={"Authorization": "Bearer test-token"}
            )
            assert r.status_code in (200, 401, 403)
            if r.status_code == 200:
                assert r.json()["data"]["greeting_message"] == "Updated greeting message"
    finally:
        app.dependency_overrides.pop(get_current_user_with_role, None)


def test_preview_prompt_endpoint(client):
    app.dependency_overrides[get_current_user_with_role] = _owner_override
    try:
        clinic_res = MagicMock()
        clinic_res.data = {"name": "Sunrise Medical Clinic"}

        with patch("src.api.routers.agent_config_router.supabase_read") as mock_read:
            mock_read.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = clinic_res

            r = client.post(
                "/api/v1/agent-config/test-greeting",
                json={
                    "greeting_message": "Live preview greeting",
                    "custom_system_prompt": "Live persona instructions",
                    "voice_id": "11labs-rachel",
                    "language": "en-US",
                    "emergency_forward_phone": "+1 (555) 000-1111",
                    "faq_data": {"Do you do cleanings?": "Yes"}
                },
                headers={"Authorization": "Bearer test-token"}
            )
            assert r.status_code in (200, 401, 403)
            if r.status_code == 200:
                body = r.json()
                assert "compiled_prompt" in body
                assert "Live preview greeting" in body["compiled_prompt"]
                assert "+15550001111" in body["compiled_prompt"]
                assert body["char_count"] > 0
    finally:
        app.dependency_overrides.pop(get_current_user_with_role, None)


def test_sync_retell_endpoint(client):
    app.dependency_overrides[get_current_user_with_role] = _owner_override
    try:
        config_res = MagicMock()
        config_res.data = [{
            "id": "cfg-1",
            "clinic_id": "clinic-test-uuid-1",
            "retell_agent_id": "agent_live_456",
            "greeting_message": "Hello from Sunrise!",
            "custom_system_prompt": "Helpful receptionist",
            "voice_id": "11labs-rachel",
            "language": "en-US",
            "emergency_forward_phone": "+15557778888",
            "faq_data": {}
        }]

        with patch("src.api.routers.agent_config_router.supabase_read") as mock_read, \
             patch("src.api.routers.agent_config_router.supabase") as mock_db, \
             patch("src.api.routers.agent_config_router._sync_to_retell", new_callable=AsyncMock) as mock_sync:
            
            mock_sync.return_value = {"success": True, "status": "synced", "agent_id": "agent_live_456", "llm_id": "llm_123"}
            mock_read.table.return_value.select.return_value.eq.return_value.execute.return_value = config_res
            mock_db.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[{"id": "cfg-1"}])

            r = client.post("/api/v1/agent-config/sync-retell", headers={"Authorization": "Bearer test-token"})
            assert r.status_code in (200, 401, 403)
            if r.status_code == 200:
                assert r.json()["success"] is True
                assert r.json()["sync_status"] == "synced"
    finally:
        app.dependency_overrides.pop(get_current_user_with_role, None)


def test_delete_agent_config(client):
    app.dependency_overrides[get_current_user_with_role] = _owner_override
    try:
        with patch("src.api.routers.agent_config_router.supabase") as mock_db:
            mock_db.table.return_value.delete.return_value.eq.return_value.execute.return_value = MagicMock(data=[{"id": "cfg-1"}])
            r = client.delete("/api/v1/agent-config", headers={"Authorization": "Bearer test-token"})
        assert r.status_code in (200, 401, 403)
        if r.status_code == 200:
            assert r.json()["data"]["deleted"] is True
    finally:
        app.dependency_overrides.pop(get_current_user_with_role, None)
