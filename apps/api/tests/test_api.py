import json
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.container import Container
from app.domain.enums import ConversationStatus, GapStatus
from app.infra.db.models import Conversation, KnowledgeGap, Lead, Site, User
from app.infra.db.session import Database
from app.infra.embeddings import HashEmbedder
from app.main import create_app
from app.services.auth import password_hash
from tests.factories import make_site, make_source
from tests.test_chat import KNOWLEDGE, RecordingNotifier, ScriptedModel
from tests.test_indexing import service as indexing_service

ORIGIN = "https://ohmsolder.test"
CSRF = {"x-relay-csrf": "1"}


@pytest.fixture
async def container(database: Database) -> AsyncIterator[Container]:
    container = Container(settings=get_settings(), database=database)
    container.__dict__["embedder"] = HashEmbedder(get_settings().embedding_dim)
    container.__dict__["notifier"] = RecordingNotifier()
    container.__dict__["llm"] = ScriptedModel("A new iPhone 15 screen costs 189 EUR [1].")
    await container.redis.flushdb()
    yield container
    await container.redis.aclose()


@pytest.fixture
async def client(container: Container) -> AsyncIterator[AsyncClient]:
    app = create_app(container)
    app.state.container = container
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://api.test") as http:
        yield http


@pytest.fixture
async def site(session: AsyncSession) -> Site:
    site = await make_site(session, confidence_threshold=0.2)
    source = await make_source(session, site)
    await indexing_service(session).ingest_documents(source, KNOWLEDGE)
    session.add(
        User(
            workspace_id=site.workspace_id,
            email="owner@ohmsolder.test",
            name="Marta",
            password_hash=password_hash.hash("correct horse"),
        )
    )
    session.add(
        User(
            workspace_id=site.workspace_id,
            email="demo@relay.example",
            name="Demo",
            password_hash=password_hash.hash("demo"),
            is_demo=True,
        )
    )
    await session.commit()
    return site


def parse_sse(body: str) -> list[tuple[str, dict[str, object]]]:
    events = []
    for block in body.strip().split("\n\n"):
        name, data = "message", ""
        for line in block.splitlines():
            if line.startswith("event:"):
                name = line[6:].strip()
            elif line.startswith("data:"):
                data += line[5:].strip()
        if data:
            events.append((name, json.loads(data)))
    return events


async def start(client: AsyncClient, site: Site) -> tuple[str, dict[str, str]]:
    response = await client.post(
        f"/v1/widget/{site.public_key}/conversations",
        json={"page_url": f"{ORIGIN}/prices", "language": "en-US"},
        headers={"origin": ORIGIN},
    )
    assert response.status_code == 201
    body = response.json()
    return body["id"], {"origin": ORIGIN, "x-visitor-token": body["token"]}


async def login(client: AsyncClient, email: str = "owner@ohmsolder.test") -> None:
    if email.startswith("demo"):
        response = await client.post("/v1/admin/auth/demo")
    else:
        response = await client.post(
            "/v1/admin/auth/login", json={"email": email, "password": "correct horse"}
        )
    assert response.status_code == 200, response.text


async def test_config_respects_allowed_domains(client: AsyncClient, site: Site) -> None:
    ok = await client.get(f"/v1/widget/{site.public_key}/config", headers={"origin": ORIGIN})
    assert ok.status_code == 200
    assert ok.headers["access-control-allow-origin"] == ORIGIN
    assert ok.json()["site_name"] == "Ohm & Solder"

    blocked = await client.get(
        f"/v1/widget/{site.public_key}/config", headers={"origin": "https://copycat.example"}
    )
    assert blocked.status_code == 403


async def test_message_streams_answer_with_sources(client: AsyncClient, site: Site) -> None:
    conversation_id, headers = await start(client, site)

    response = await client.post(
        f"/v1/widget/conversations/{conversation_id}/messages",
        json={"text": "How much is an iPhone 15 screen?"},
        headers=headers,
    )

    assert response.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(response.text)
    assert events[0][0] == "start"
    done = events[-1][1]
    assert done["mode"] == "llm"
    assert done["sources"][0]["title"] == "Repair prices"

    transcript = await client.get(
        f"/v1/widget/conversations/{conversation_id}/messages", headers=headers
    )
    assert [m["role"] for m in transcript.json()["messages"]] == ["visitor", "bot"]


async def test_conversation_needs_its_token(client: AsyncClient, site: Site) -> None:
    conversation_id, headers = await start(client, site)
    response = await client.get(
        f"/v1/widget/conversations/{conversation_id}/messages",
        headers={**headers, "x-visitor-token": "stolen"},
    )
    assert response.status_code == 404


async def test_rate_limit_stops_message_floods(
    client: AsyncClient, site: Site, container: Container
) -> None:
    container.settings.widget_rate_per_minute = 2
    conversation_id, headers = await start(client, site)
    url = f"/v1/widget/conversations/{conversation_id}/messages"
    try:
        for _ in range(2):
            await client.post(url, json={"text": "battery warranty"}, headers=headers)
        response = await client.post(url, json={"text": "battery warranty"}, headers=headers)
    finally:
        container.settings.widget_rate_per_minute = 12
    assert parse_sse(response.text) == [("error", {"code": "rate_limited"})]


async def test_handoff_then_manager_reply_from_admin(
    client: AsyncClient, site: Site, session: AsyncSession, container: Container
) -> None:
    conversation_id, headers = await start(client, site)
    await client.post(
        f"/v1/widget/conversations/{conversation_id}/messages",
        json={"text": "Can you fix a drone?"},
        headers=headers,
    )
    handoff = await client.post(
        f"/v1/widget/conversations/{conversation_id}/handoff", headers=headers
    )
    assert handoff.json()["status"] == "waiting"
    assert ("handoff", conversation_id) in [
        (kind, str(value))
        for kind, value in container.notifier.events  # type: ignore[attr-defined]
    ]

    await login(client)
    reply = await client.post(
        f"/v1/admin/sites/{site.id}/conversations/{conversation_id}/reply",
        json={"text": "Hi, yes, bring it in tomorrow."},
        headers=CSRF,
    )
    assert reply.status_code == 200
    assert reply.json()["author_name"] == "Marta"

    conversation = await session.get(Conversation, conversation_id)
    await session.refresh(conversation)
    assert conversation is not None and conversation.status == ConversationStatus.HUMAN

    transcript = await client.get(
        f"/v1/widget/conversations/{conversation_id}/messages", headers=headers
    )
    assert transcript.json()["messages"][-1]["role"] == "manager"


async def test_lead_is_saved_and_linked(
    client: AsyncClient, site: Site, session: AsyncSession
) -> None:
    conversation_id, headers = await start(client, site)
    response = await client.post(
        f"/v1/widget/{site.public_key}/leads",
        json={
            "name": "Anna",
            "contact": "@anna_k",
            "question": "Water damage on a MacBook Air",
            "conversation_id": conversation_id,
        },
        headers=headers,
    )
    assert response.status_code == 201
    lead = await session.scalar(select(Lead))
    assert lead is not None and str(lead.conversation_id) == conversation_id


async def test_admin_requires_session_and_csrf_header(client: AsyncClient, site: Site) -> None:
    assert (await client.get("/v1/admin/me")).status_code == 401
    await login(client)
    assert (await client.get("/v1/admin/me")).json()["sites"][0]["name"] == "Ohm & Solder"
    no_header = await client.post(
        f"/v1/admin/sites/{site.id}/faq", json={"question": "Parking?", "answer": "Yes."}
    )
    assert no_header.status_code == 403


async def test_wrong_password_is_rejected(client: AsyncClient, site: Site) -> None:
    response = await client.post(
        "/v1/admin/auth/login", json={"email": "owner@ohmsolder.test", "password": "nope"}
    )
    assert response.status_code == 401


async def test_other_workspace_sites_are_invisible(
    client: AsyncClient, site: Site, session: AsyncSession
) -> None:
    stranger = await make_site(session)
    await session.commit()
    await login(client)
    response = await client.get(f"/v1/admin/sites/{stranger.id}/conversations")
    assert response.status_code == 404


async def test_demo_account_cannot_crawl_or_delete(client: AsyncClient, site: Site) -> None:
    await login(client, "demo@relay.example")
    crawl = await client.post(
        f"/v1/admin/sites/{site.id}/sources",
        json={"kind": "sitemap", "url": "https://example.com/sitemap.xml"},
        headers=CSRF,
    )
    assert crawl.status_code == 403
    delete = await client.delete(f"/v1/admin/sites/{site.id}", headers=CSRF)
    assert delete.status_code == 403


async def test_answering_a_gap_teaches_the_bot(
    client: AsyncClient, site: Site, session: AsyncSession, container: Container
) -> None:
    site.confidence_threshold = 0.99
    await session.commit()
    conversation_id, headers = await start(client, site)
    await client.post(
        f"/v1/widget/conversations/{conversation_id}/messages",
        json={"text": "Do you repair drones?"},
        headers=headers,
    )
    await login(client)
    gaps = (await client.get(f"/v1/admin/sites/{site.id}/gaps")).json()
    assert gaps[0]["question"] == "Do you repair drones?"

    response = await client.post(
        f"/v1/admin/sites/{site.id}/gaps/{gaps[0]['id']}/answer",
        json={"question": "Do you repair drones?", "answer": "Yes, DJI Mini and Air series."},
        headers=CSRF,
    )
    assert response.json()["status"] == GapStatus.ANSWERED

    faq = (await client.get(f"/v1/admin/sites/{site.id}/faq")).json()
    assert faq[0]["answer"] == "Yes, DJI Mini and Air series."
    gap = await session.scalar(select(KnowledgeGap))
    await session.refresh(gap)
    assert gap is not None and gap.status == GapStatus.ANSWERED


async def test_analytics_counts_outcomes(client: AsyncClient, site: Site) -> None:
    first, headers = await start(client, site)
    await client.post(
        f"/v1/widget/conversations/{first}/messages",
        json={"text": "iPhone 15 screen price"},
        headers=headers,
    )
    await client.post(
        f"/v1/widget/conversations/{first}/rating", json={"value": 1}, headers=headers
    )
    second, headers2 = await start(client, site)
    await client.post(
        f"/v1/widget/conversations/{second}/messages",
        json={"text": "battery warranty"},
        headers=headers2,
    )
    await client.post(f"/v1/widget/conversations/{second}/handoff", headers=headers2)

    await login(client)
    data = (await client.get(f"/v1/admin/sites/{site.id}/analytics")).json()
    assert data["conversations"] == 2
    assert data["resolved_confirmed"] == 1
    assert data["handoffs"] == 1
    assert data["automation_rate"] == 0.5
    assert data["tokens_this_month"] > 0


async def test_demo_cannot_rewrite_bot_instructions(client: AsyncClient, site: Site) -> None:
    await login(client, "demo@relay.example")
    response = await client.patch(
        f"/v1/admin/sites/{site.id}", json={"instructions": "Be rude"}, headers=CSRF
    )
    assert response.status_code == 403
    allowed = await client.patch(
        f"/v1/admin/sites/{site.id}", json={"confidence_threshold": 0.5}, headers=CSRF
    )
    assert allowed.status_code == 200


async def test_demo_sees_masked_contacts_of_real_leads(
    client: AsyncClient, site: Site, session: AsyncSession
) -> None:
    session.add_all(
        [
            Lead(site_id=site.id, name="Real", contact="+37491123456"),
            Lead(site_id=site.id, name="Sample", contact="@sample_user", sample=True),
        ]
    )
    await session.commit()
    await login(client, "demo@relay.example")

    leads = {
        lead["name"]: lead["contact"]
        for lead in (await client.get(f"/v1/admin/sites/{site.id}/leads")).json()
    }

    assert leads["Real"] == "+3••••••••56"
    assert leads["Sample"] == "@sample_user"


async def test_failed_logins_are_rate_limited(client: AsyncClient, site: Site) -> None:
    for _ in range(3):
        await login(client)
    for _ in range(5):
        await client.post(
            "/v1/admin/auth/login", json={"email": "owner@ohmsolder.test", "password": "x"}
        )
    response = await client.post(
        "/v1/admin/auth/login", json={"email": "owner@ohmsolder.test", "password": "correct horse"}
    )
    assert response.status_code == 429


async def test_demo_gets_no_telegram_link(client: AsyncClient, site: Site) -> None:
    await login(client, "demo@relay.example")
    data = (await client.get(f"/v1/admin/sites/{site.id}/telegram")).json()
    assert data["connect_link"] is None
