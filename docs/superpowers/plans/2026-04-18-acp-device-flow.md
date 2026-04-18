# ACP Device Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add OAuth 2.0 Device Authorization Grant (RFC 8628) to the ACP server so remote clients can authenticate via a browser approval page instead of pre-shared tokens.

**Architecture:** A new `DeviceFlowManager` class handles code generation, approval state, and token persistence to `.operator_use/acp_tokens.json`. Three new HTTP endpoints are added to `ACPServer` (POST /auth/device, POST /auth/token, GET+POST /auth/approve). The existing auth middleware is extended to validate device-flow-issued tokens. `ACPClient` gains a `device_auth()` method that runs the full client-side flow.

**Tech Stack:** Python 3.13+, aiohttp, pydantic v2, pytest + pytest-asyncio, aiohttp test utils

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `operator_use/acp/config.py` | Modify | Add `device_flow_enabled: bool` and `tokens_path: str` to `ACPServerConfig` |
| `operator_use/acp/models.py` | Modify | Add `DeviceCodeResponse`, `TokenRequest`, `TokenResponse` pydantic models |
| `operator_use/acp/device_flow.py` | Create | `DeviceFlowManager` — code generation, approval, token validation, disk persistence |
| `operator_use/acp/server.py` | Modify | Register 4 new route handlers + extend auth middleware |
| `operator_use/acp/client.py` | Modify | Add `device_auth()` method |
| `tests/test_acp_device_flow.py` | Create | All tests for device flow (manager + server endpoints + client method) |

---

### Task 1: Config and Model Changes

**Files:**
- Modify: `operator_use/acp/config.py`
- Modify: `operator_use/acp/models.py`

- [ ] **Step 1: Add fields to `ACPServerConfig`**

In `operator_use/acp/config.py`, add two fields to the `ACPServerConfig` dataclass after `public_url`:

```python
    # Device Authorization Grant (RFC 8628)
    device_flow_enabled: bool = False
    # Path to JSON file for persisting approved tokens (default: .operator_use/acp_tokens.json)
    tokens_path: str = ""
```

- [ ] **Step 2: Add device flow models to `models.py`**

Append to `operator_use/acp/models.py`:

```python
# ---------------------------------------------------------------------------
# Device Authorization Grant (RFC 8628)
# ---------------------------------------------------------------------------


class DeviceCodeResponse(BaseModel):
    """POST /auth/device response."""

    device_code: str
    user_code: str          # short human-typeable code, e.g. "KQBG-MDJX"
    verification_uri: str   # URL to open in browser
    expires_in: int = 600   # seconds until device_code expires
    interval: int = 5       # polling interval in seconds


class TokenRequest(BaseModel):
    """POST /auth/token body."""

    device_code: str


class TokenResponse(BaseModel):
    """POST /auth/token success response."""

    access_token: str
    token_type: str = "bearer"
```

- [ ] **Step 3: Commit**

```bash
git add operator_use/acp/config.py operator_use/acp/models.py
git commit -m "feat(acp): add device flow config fields and models"
```

---

### Task 2: DeviceFlowManager

**Files:**
- Create: `operator_use/acp/device_flow.py`
- Create: `tests/test_acp_device_flow.py`

- [ ] **Step 1: Write failing tests for DeviceFlowManager**

Create `tests/test_acp_device_flow.py`:

```python
"""Tests for ACP Device Authorization Grant flow."""

from __future__ import annotations

import json
import os
import time
import pytest

from operator_use.acp.device_flow import DeviceFlowManager


# ---------------------------------------------------------------------------
# DeviceFlowManager unit tests
# ---------------------------------------------------------------------------


def test_create_code_returns_device_and_user_code(tmp_path):
    mgr = DeviceFlowManager(tokens_path=str(tmp_path / "tokens.json"))
    code = mgr.create_code(verification_uri="http://localhost:8765/auth/approve")
    assert code.device_code
    assert "-" in code.user_code          # format: XXXX-XXXX
    assert len(code.user_code) == 9       # 4 + dash + 4
    assert code.verification_uri == "http://localhost:8765/auth/approve"
    assert code.expires_in == 600
    assert code.interval == 5


def test_poll_returns_none_when_pending(tmp_path):
    mgr = DeviceFlowManager(tokens_path=str(tmp_path / "tokens.json"))
    code = mgr.create_code(verification_uri="http://localhost:8765/auth/approve")
    assert mgr.poll(code.device_code) is None


def test_approve_then_poll_returns_token(tmp_path):
    mgr = DeviceFlowManager(tokens_path=str(tmp_path / "tokens.json"))
    code = mgr.create_code(verification_uri="http://localhost:8765/auth/approve")
    token = mgr.approve(code.device_code)
    assert token is not None
    assert token.startswith("op_")
    assert mgr.poll(code.device_code) == token


def test_validate_token_true_after_approve(tmp_path):
    mgr = DeviceFlowManager(tokens_path=str(tmp_path / "tokens.json"))
    code = mgr.create_code(verification_uri="http://localhost:8765/auth/approve")
    token = mgr.approve(code.device_code)
    assert mgr.validate_token(token) is True


def test_validate_token_false_for_unknown(tmp_path):
    mgr = DeviceFlowManager(tokens_path=str(tmp_path / "tokens.json"))
    assert mgr.validate_token("op_doesnotexist") is False


def test_tokens_persisted_to_disk(tmp_path):
    path = str(tmp_path / "tokens.json")
    mgr = DeviceFlowManager(tokens_path=path)
    code = mgr.create_code(verification_uri="http://localhost:8765/auth/approve")
    token = mgr.approve(code.device_code)

    # Load a fresh manager from the same file
    mgr2 = DeviceFlowManager(tokens_path=path)
    assert mgr2.validate_token(token) is True


def test_list_pending_returns_active_codes(tmp_path):
    mgr = DeviceFlowManager(tokens_path=str(tmp_path / "tokens.json"))
    mgr.create_code(verification_uri="http://localhost:8765/auth/approve")
    mgr.create_code(verification_uri="http://localhost:8765/auth/approve")
    pending = mgr.list_pending()
    assert len(pending) == 2


def test_list_pending_excludes_approved(tmp_path):
    mgr = DeviceFlowManager(tokens_path=str(tmp_path / "tokens.json"))
    code = mgr.create_code(verification_uri="http://localhost:8765/auth/approve")
    mgr.approve(code.device_code)
    assert len(mgr.list_pending()) == 0


def test_approve_unknown_code_returns_none(tmp_path):
    mgr = DeviceFlowManager(tokens_path=str(tmp_path / "tokens.json"))
    assert mgr.approve("bad-device-code") is None


def test_poll_unknown_code_returns_none(tmp_path):
    mgr = DeviceFlowManager(tokens_path=str(tmp_path / "tokens.json"))
    assert mgr.poll("bad-device-code") is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_acp_device_flow.py -v
```

Expected: `ImportError` or `ModuleNotFoundError` — `device_flow` doesn't exist yet.

- [ ] **Step 3: Implement `DeviceFlowManager`**

Create `operator_use/acp/device_flow.py`:

```python
"""Device Authorization Grant manager (RFC 8628)."""

from __future__ import annotations

import json
import logging
import random
import secrets
import string
from dataclasses import dataclass, field
from datetime import datetime, timezone

from operator_use.acp.models import DeviceCodeResponse

logger = logging.getLogger(__name__)

_CODE_CHARS = string.ascii_uppercase + string.digits
_EXPIRES_IN = 600  # seconds


@dataclass
class _PendingCode:
    device_code: str
    user_code: str
    verification_uri: str
    expires_at: float          # time.monotonic() deadline
    access_token: str | None = None


class DeviceFlowManager:
    """Manages device codes, approvals, and token persistence."""

    def __init__(self, tokens_path: str) -> None:
        self._tokens_path = tokens_path
        self._pending: dict[str, _PendingCode] = {}   # device_code -> _PendingCode
        self._tokens: dict[str, str] = {}              # access_token -> approved_at ISO
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_code(self, verification_uri: str) -> DeviceCodeResponse:
        import time
        device_code = secrets.token_hex(24)
        user_code = self._gen_user_code()
        entry = _PendingCode(
            device_code=device_code,
            user_code=user_code,
            verification_uri=verification_uri,
            expires_at=time.monotonic() + _EXPIRES_IN,
        )
        self._pending[device_code] = entry
        return DeviceCodeResponse(
            device_code=device_code,
            user_code=user_code,
            verification_uri=verification_uri,
            expires_in=_EXPIRES_IN,
            interval=5,
        )

    def approve(self, device_code: str) -> str | None:
        """Approve a pending code. Returns access_token or None if not found/expired."""
        import time
        entry = self._pending.get(device_code)
        if entry is None or time.monotonic() > entry.expires_at:
            return None
        if entry.access_token:
            return entry.access_token
        token = "op_" + secrets.token_hex(32)
        entry.access_token = token
        self._tokens[token] = datetime.now(timezone.utc).isoformat()
        self._save()
        return token

    def poll(self, device_code: str) -> str | None:
        """Return access_token if approved, None if still pending or unknown."""
        import time
        entry = self._pending.get(device_code)
        if entry is None or time.monotonic() > entry.expires_at:
            return None
        return entry.access_token

    def validate_token(self, token: str) -> bool:
        return token in self._tokens

    def list_pending(self) -> list[_PendingCode]:
        import time
        now = time.monotonic()
        return [
            e for e in self._pending.values()
            if now <= e.expires_at and e.access_token is None
        ]

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        try:
            with open(self._tokens_path) as f:
                self._tokens = json.load(f)
        except FileNotFoundError:
            pass
        except Exception as exc:
            logger.warning(f"Could not load ACP tokens from {self._tokens_path}: {exc}")

    def _save(self) -> None:
        try:
            import os
            os.makedirs(os.path.dirname(self._tokens_path) or ".", exist_ok=True)
            with open(self._tokens_path, "w") as f:
                json.dump(self._tokens, f, indent=2)
        except Exception as exc:
            logger.error(f"Could not save ACP tokens to {self._tokens_path}: {exc}")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _gen_user_code() -> str:
        part = lambda: "".join(random.choices(_CODE_CHARS, k=4))
        return f"{part()}-{part()}"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_acp_device_flow.py -v
```

Expected: All 10 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add operator_use/acp/device_flow.py tests/test_acp_device_flow.py
git commit -m "feat(acp): add DeviceFlowManager with persistence and tests"
```

---

### Task 3: Server Endpoints

**Files:**
- Modify: `operator_use/acp/server.py`
- Modify: `tests/test_acp_device_flow.py`

- [ ] **Step 1: Write failing server endpoint tests**

Append to `tests/test_acp_device_flow.py`:

```python
# ---------------------------------------------------------------------------
# Server endpoint tests
# ---------------------------------------------------------------------------

import pytest_asyncio
from aiohttp.test_utils import TestClient, TestServer

from operator_use.acp.config import ACPServerConfig
from operator_use.acp.models import AgentCapabilities, AgentMetadata
from operator_use.acp.server import ACPServer


def _make_df_server(tmp_path) -> ACPServer:
    async def _echo(text, session_id):
        yield f"echo:{text}"

    config = ACPServerConfig(
        device_flow_enabled=True,
        tokens_path=str(tmp_path / "tokens.json"),
        id="test-df-server",
    )
    meta = AgentMetadata(
        id="operator",
        name="Operator",
        capabilities=AgentCapabilities(streaming=True, async_mode=True, session=True),
    )
    return ACPServer(config=config, runners={"operator": _echo}, metadata={"operator": meta})


@pytest.fixture
def df_server(tmp_path):
    return _make_df_server(tmp_path)


@pytest.mark.asyncio
async def test_post_auth_device_returns_code(df_server):
    async with TestClient(TestServer(df_server._app)) as client:
        resp = await client.post("/auth/device")
        assert resp.status == 200
        data = await resp.json()
        assert "device_code" in data
        assert "user_code" in data
        assert "-" in data["user_code"]
        assert "verification_uri" in data
        assert data["interval"] == 5


@pytest.mark.asyncio
async def test_post_auth_token_pending_returns_202(df_server):
    async with TestClient(TestServer(df_server._app)) as client:
        resp = await client.post("/auth/device")
        data = await resp.json()
        token_resp = await client.post("/auth/token", json={"device_code": data["device_code"]})
        assert token_resp.status == 202


@pytest.mark.asyncio
async def test_post_auth_token_approved_returns_token(df_server):
    async with TestClient(TestServer(df_server._app)) as client:
        resp = await client.post("/auth/device")
        data = await resp.json()
        device_code = data["device_code"]

        # Approve directly via manager
        df_server._device_flow.approve(device_code)

        token_resp = await client.post("/auth/token", json={"device_code": device_code})
        assert token_resp.status == 200
        token_data = await token_resp.json()
        assert token_data["access_token"].startswith("op_")


@pytest.mark.asyncio
async def test_get_auth_approve_shows_pending(df_server):
    async with TestClient(TestServer(df_server._app)) as client:
        await client.post("/auth/device")
        resp = await client.get("/auth/approve")
        assert resp.status == 200
        text = await resp.text()
        assert "XXXX" not in text   # rendered, not template literal
        assert "<form" in text


@pytest.mark.asyncio
async def test_post_auth_approve_approves_code(df_server):
    async with TestClient(TestServer(df_server._app)) as client:
        resp = await client.post("/auth/device")
        device_code = (await resp.json())["device_code"]

        approve_resp = await client.post(f"/auth/approve/{device_code}")
        assert approve_resp.status == 200

        token_resp = await client.post("/auth/token", json={"device_code": device_code})
        assert token_resp.status == 200


@pytest.mark.asyncio
async def test_device_flow_token_accepted_as_bearer(df_server):
    async with TestClient(TestServer(df_server._app)) as client:
        resp = await client.post("/auth/device")
        device_code = (await resp.json())["device_code"]
        await client.post(f"/auth/approve/{device_code}")

        token_resp = await client.post("/auth/token", json={"device_code": device_code})
        token = (await token_resp.json())["access_token"]

        agents_resp = await client.get("/agents", headers={"Authorization": f"Bearer {token}"})
        assert agents_resp.status == 200


@pytest.mark.asyncio
async def test_device_flow_disabled_returns_404():
    async def _echo(text, session_id):
        yield text

    config = ACPServerConfig(device_flow_enabled=False, id="test-no-df")
    meta = AgentMetadata(id="operator", name="Operator")
    server = ACPServer(config=config, runners={"operator": _echo}, metadata={"operator": meta})

    async with TestClient(TestServer(server._app)) as client:
        resp = await client.post("/auth/device")
        assert resp.status == 404
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_acp_device_flow.py::test_post_auth_device_returns_code -v
```

Expected: FAIL — `/auth/device` endpoint doesn't exist yet.

- [ ] **Step 3: Add device flow routes and handlers to `server.py`**

In `_build_app()`, add routes after the existing ones (only when `device_flow_enabled`):

```python
def _build_app(self) -> web.Application:
    app = web.Application(middlewares=[self._auth_middleware, self._signature_middleware])
    app.router.add_get("/agents", self._handle_list_agents)
    app.router.add_get("/agents/{agent_id}", self._handle_get_agent)
    app.router.add_get("/agents/{agent_id}/pubkey", self._handle_get_pubkey)
    app.router.add_post("/runs", self._handle_create_run)
    app.router.add_get("/runs/{run_id}", self._handle_get_run)
    app.router.add_delete("/runs/{run_id}", self._handle_cancel_run)
    app.router.add_get("/runs/{run_id}/await", self._handle_await_run)
    if self.config.device_flow_enabled:
        app.router.add_post("/auth/device", self._handle_device_request)
        app.router.add_post("/auth/token", self._handle_device_token)
        app.router.add_get("/auth/approve", self._handle_approve_page)
        app.router.add_post("/auth/approve/{device_code}", self._handle_approve_action)
    return app
```

- [ ] **Step 4: Initialize `DeviceFlowManager` in `__init__`**

Add import at top of `server.py`:

```python
from operator_use.acp.device_flow import DeviceFlowManager
```

Add to `ACPServer.__init__` after `self._peer_pubkeys` line:

```python
        self._device_flow: DeviceFlowManager | None = (
            DeviceFlowManager(
                tokens_path=config.tokens_path or ".operator_use/acp_tokens.json"
            )
            if config.device_flow_enabled
            else None
        )
```

- [ ] **Step 5: Add the four handler methods to `ACPServer`**

Add after `_handle_await_run`:

```python
    # ------------------------------------------------------------------
    # Device Authorization Grant handlers (RFC 8628)
    # ------------------------------------------------------------------

    async def _handle_device_request(self, request: web.Request) -> web.Response:
        base = self.config.public_url or f"http://{self.config.host}:{self.config.port}"
        code = self._device_flow.create_code(verification_uri=f"{base}/auth/approve")
        return web.json_response(code.model_dump())

    async def _handle_device_token(self, request: web.Request) -> web.Response:
        try:
            body = await request.json()
            device_code = body.get("device_code", "")
        except Exception:
            return web.json_response({"error": "invalid request"}, status=400)

        token = self._device_flow.poll(device_code)
        if token is None:
            return web.Response(status=202)  # still pending
        from operator_use.acp.models import TokenResponse
        return web.json_response(TokenResponse(access_token=token).model_dump())

    async def _handle_approve_page(self, request: web.Request) -> web.Response:
        import time
        pending = self._device_flow.list_pending()
        if not pending:
            body = "<h1>No pending device requests</h1>"
        else:
            rows = []
            now = time.monotonic()
            for p in pending:
                mins = max(0, int((p.expires_at - now) / 60))
                rows.append(
                    f"<form method='POST' action='/auth/approve/{p.device_code}' style='margin:1em 0'>"
                    f"<p>Code: <strong>{p.user_code}</strong> &mdash; expires in ~{mins} min</p>"
                    f"<button type='submit'>Approve</button></form>"
                )
            body = "<h1>Pending Device Connections</h1>" + "".join(rows)

        html = f"<!DOCTYPE html><html><head><title>Approve Device</title></head><body>{body}</body></html>"
        return web.Response(text=html, content_type="text/html")

    async def _handle_approve_action(self, request: web.Request) -> web.Response:
        device_code = request.match_info["device_code"]
        token = self._device_flow.approve(device_code)
        if token is None:
            return web.Response(text="Code not found or expired.", status=404)
        return web.Response(text="Approved. The remote device is now connected.", content_type="text/html")
```

- [ ] **Step 6: Extend `_auth_middleware` to validate device-flow tokens**

Replace the final `else` branch in `_auth_middleware` (the `# no auth configured — open access` branch) with:

```python
        else:
            # No static auth configured — check device-flow tokens
            if self._device_flow and provided:
                if not self._device_flow.validate_token(provided):
                    return web.Response(status=401, text="Unauthorized")
            request["_authed_agent"] = None
```

- [ ] **Step 7: Run tests to verify they pass**

```bash
pytest tests/test_acp_device_flow.py -v
```

Expected: All 17 tests PASS.

- [ ] **Step 8: Commit**

```bash
git add operator_use/acp/server.py tests/test_acp_device_flow.py
git commit -m "feat(acp): add device flow server endpoints and auth middleware extension"
```

---

### Task 4: Client `device_auth()` Method

**Files:**
- Modify: `operator_use/acp/client.py`
- Modify: `tests/test_acp_device_flow.py`

- [ ] **Step 1: Write failing client test**

Append to `tests/test_acp_device_flow.py`:

```python
# ---------------------------------------------------------------------------
# Client device_auth() integration test
# ---------------------------------------------------------------------------

from operator_use.acp.client import ACPClient
from operator_use.acp.config import ACPClientConfig


@pytest.mark.asyncio
async def test_client_device_auth_completes(tmp_path):
    """Full device_auth() flow: request code, auto-approve server-side, poll until done."""
    df_server = _make_df_server(tmp_path)
    async with TestClient(TestServer(df_server._app)) as http_client:
        base_url = str(http_client.make_url("/")).rstrip("/")
        cfg = ACPClientConfig(base_url=base_url, agent_id="operator")
        acp = ACPClient(cfg)

        # Simulate: as soon as code is created, auto-approve it (what a human would do)
        original_create = df_server._device_flow.create_code
        def auto_approve_create(verification_uri):
            code = original_create(verification_uri)
            df_server._device_flow.approve(code.device_code)
            return code
        df_server._device_flow.create_code = auto_approve_create

        async with acp:
            token = await acp.device_auth()

        assert token.startswith("op_")
        assert acp.config.auth_token == token
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_acp_device_flow.py::test_client_device_auth_completes -v
```

Expected: FAIL — `ACPClient` has no `device_auth` method.

- [ ] **Step 3: Add `device_auth()` to `ACPClient`**

Add import at top of `client.py`:

```python
import asyncio
```

Add method after `run_stream()`:

```python
    async def device_auth(self, poll_interval: float | None = None) -> str:
        """Run the Device Authorization Grant flow.

        Requests a device code, prints the verification URI and user code,
        then polls until the human approves. On success, sets
        self.config.auth_token and returns the access token.
        """
        from operator_use.acp.models import DeviceCodeResponse, TokenRequest

        session = self._ensure_session()

        # Step 1: Request a device code
        async with session.post("/auth/device") as resp:
            resp.raise_for_status()
            data = await resp.json()
        code_info = DeviceCodeResponse(**data)

        print(
            f"\nVisit {code_info.verification_uri} and enter code: {code_info.user_code}\n"
            f"Waiting for approval..."
        )

        interval = poll_interval if poll_interval is not None else float(code_info.interval)

        # Step 2: Poll until approved or expired
        deadline = asyncio.get_event_loop().time() + code_info.expires_in
        while asyncio.get_event_loop().time() < deadline:
            await asyncio.sleep(interval)
            async with session.post(
                "/auth/token",
                json=TokenRequest(device_code=code_info.device_code).model_dump(),
            ) as resp:
                if resp.status == 202:
                    continue  # still pending
                if resp.status == 200:
                    token_data = await resp.json()
                    token = token_data["access_token"]
                    self.config.auth_token = token
                    # Update session headers so subsequent calls use the new token
                    self._session._default_headers.update({"Authorization": f"Bearer {token}"})
                    return token
                resp.raise_for_status()

        raise TimeoutError("Device authorization timed out — code expired before approval")
```

- [ ] **Step 4: Run all device flow tests**

```bash
pytest tests/test_acp_device_flow.py -v
```

Expected: All 18 tests PASS.

- [ ] **Step 5: Run full test suite to check for regressions**

```bash
pytest tests/test_acp_server.py tests/test_acp_device_flow.py -v
```

Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add operator_use/acp/client.py tests/test_acp_device_flow.py
git commit -m "feat(acp): add ACPClient.device_auth() for device flow client side"
```
