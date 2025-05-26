import random
import re
import secrets
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.domain.enums import (
    ConversationStatus,
    GapStatus,
    LeadStatus,
    MessageRole,
    SourceKind,
    SourceStatus,
)
from app.domain.widget import WidgetSettings
from app.infra.db.models import (
    Conversation,
    FaqItem,
    KnowledgeGap,
    Lead,
    Message,
    Site,
    Source,
    UsageDaily,
    User,
    Workspace,
)
from app.infra.embeddings import Embedder
from app.infra.parsers import RawDocument, parse_file, parse_html
from app.seed import demo_script as script
from app.services.auth import password_hash
from app.services.indexing import IndexingService

STATIC_DIR = Path(__file__).resolve().parents[3] / "static"
DEMO_DIR = STATIC_DIR / "demo"
NARCISBIN_DIR = Path(__file__).resolve().parent / "content" / "narcisbin"

DEMO_KEY = "pk_demo_ohmsolder"
DEMO_BANNER = re.compile(r'<div class="demo-note">.*?</div>\s*</div>', re.DOTALL)
DEMO_PAGES = ["index", "prices", "warranty", "about"]

DEMO_FAQ = [
    (
        "Can you fix water damage?",
        "Often, yes. Switch the device off, don't charge it and bring it in the same day if you "
        "can. Water damage treatment costs €49 and takes about 24 hours. If the device can't be "
        "saved, you don't pay for the repair itself.",
    ),
    (
        "Do you repair game consoles?",
        "Yes: Nintendo Switch screens and Joy-Con drift, and HDMI ports on PlayStation 5 and Xbox "
        "Series X. Prices are on the prices page.",
    ),
    (
        "Can someone else pick up my device?",
        "Yes, if they bring the ticket number and tell us your name.",
    ),
    (
        "How long do you keep a repaired device?",
        "60 days after we tell you it's ready. Then we send a reminder and keep it for 30 more "
        "days.",
    ),
    (
        "Do you unlock phones locked to an Apple ID?",
        "No. We don't remove Apple ID or Google account locks. The owner has to do that through "
        "Apple or Google.",
    ),
]


class Seeder:
    def __init__(
        self,
        session: AsyncSession,
        indexer: IndexingService,
        embedder: Embedder,
        settings: Settings,
        storage_root: Path,
    ) -> None:
        self.session = session
        self.indexer = indexer
        self.embedder = embedder
        self.settings = settings
        self.storage_root = storage_root
        self.rng = random.Random(2417)

    def demo_url(self, page: str) -> str:
        return f"{self.settings.public_api_url.rstrip('/')}/demo/{page}.html"

    async def is_empty(self) -> bool:
        return await self.session.scalar(select(Workspace.id).limit(1)) is None

    async def reset_demo(self) -> Site:
        demo_workspaces = select(User.workspace_id).where(User.is_demo.is_(True))
        await self.session.execute(delete(Workspace).where(Workspace.id.in_(demo_workspaces)))
        await self.session.execute(delete(Site).where(Site.public_key == DEMO_KEY))
        await self.session.commit()
        return await self.seed_demo()

    async def seed_demo(self) -> Site:
        workspace = Workspace(name="Ohm & Solder")
        self.session.add(workspace)
        await self.session.flush()
        self.session.add(
            User(
                workspace_id=workspace.id,
                email=self.settings.demo_email,
                name="Inês",
                password_hash=password_hash.hash(self.settings.demo_password),
                is_demo=True,
            )
        )
        site = Site(
            workspace_id=workspace.id,
            name="Ohm & Solder",
            public_key=DEMO_KEY,
            telegram_link_token=secrets.token_urlsafe(12),
            allowed_domains=["ohmsolder.example"],
            confidence_threshold=0.35,
            monthly_token_budget=300_000,
            instructions=(
                "Sound like a friendly shop assistant. Keep prices in euros exactly as written. "
                "When a repair is quick, mention that people can just walk in."
            ),
            widget=WidgetSettings(
                title="Ohm & Solder",
                subtitle="Answers from our own pages",
                greeting=(
                    "Hi! Ask me about repair prices, how long things take or the warranty. "
                    "If I don't know, I'll pass you to Inês at the counter."
                ),
                accent="#0F5C4A",
                theme="light",
                quick_questions=[
                    "How much is an iPhone 15 screen?",
                    "Do I need an appointment?",
                    "What does the warranty cover?",
                    "Can you pick up my laptop?",
                ],
            ).model_dump(),
        )
        self.session.add(site)
        await self.session.flush()

        await self._index_demo_knowledge(site)
        await self._sample_traffic(site)
        await self.session.commit()
        return site

    async def _index_demo_knowledge(self, site: Site) -> None:
        pages = Source(
            site_id=site.id,
            kind=SourceKind.SITEMAP,
            title="ohmsolder.example sitemap",
            url=f"{self.settings.public_api_url.rstrip('/')}/demo/sitemap.xml",
            status=SourceStatus.INDEXING,
        )
        self.session.add(pages)
        await self.session.flush()
        documents = []
        for page in DEMO_PAGES:
            html = (DEMO_DIR / f"{page}.html").read_text(encoding="utf-8")
            # The "this is a demo" banner is for humans, not for the shop's knowledge base.
            html = DEMO_BANNER.sub("", html)
            parsed = parse_html(html, url=self.demo_url(page))
            documents.append(parsed)
        await self.indexer.ingest_documents(pages, documents)

        for filename in ("ohm-solder-price-list-2026.pdf", "ohm-solder-service-terms.docx"):
            data = (DEMO_DIR / filename).read_bytes()
            relative = Path(str(site.id)) / filename
            target = self.storage_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(DEMO_DIR / filename, target)
            source = Source(
                site_id=site.id,
                kind=SourceKind.FILE,
                title=filename,
                file_path=relative.as_posix(),
                status=SourceStatus.INDEXING,
            )
            self.session.add(source)
            await self.session.flush()
            parsed = parse_file(filename, data)
            await self.indexer.ingest_documents(
                source, [RawDocument(title=filename, text=parsed.text)]
            )

        for question, answer in DEMO_FAQ:
            item = FaqItem(site_id=site.id, question=question, answer=answer)
            self.session.add(item)
            await self.session.flush()
            await self.indexer.upsert_faq(item)

    def _when(self, days_back_max: int = 29) -> datetime:
        now = datetime.now(UTC)
        day = now - timedelta(days=self.rng.randint(0, days_back_max))
        hour = self.rng.choice([9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21])
        moment = day.replace(hour=hour, minute=self.rng.randint(0, 59), second=0, microsecond=0)
        return min(moment, now - timedelta(minutes=5))

    def _conversation(
        self, site: Site, language: str, started: datetime, page: str
    ) -> Conversation:
        return Conversation(
            site_id=site.id,
            visitor_token_hash=secrets.token_hex(32),
            language=language,
            page_url=self.demo_url(page),
            created_at=started,
            last_message_at=started,
        )

    def _source_card(self, page: str) -> dict[str, object]:
        if page == script.PRICE_LIST:
            return {"title": "ohm-solder-price-list-2026.pdf", "url": None, "snippet": ""}
        titles = {
            script.HOME: "Ohm & Solder · Phone and laptop repair in Lisbon",
            script.PRICES: "Repair prices · Ohm & Solder",
            script.WARRANTY: "Warranty and data policy · Ohm & Solder",
            script.ABOUT: "About us · Ohm & Solder",
        }
        return {"title": titles[page], "url": self.demo_url(page), "snippet": ""}

    def _add_messages(self, conversation: Conversation, messages: list[Message]) -> None:
        moment = conversation.created_at
        for message in messages:
            moment += timedelta(seconds=self.rng.randint(8, 70))
            message.created_at = moment
            conversation.messages.append(message)
        conversation.last_message_at = moment

    async def _sample_traffic(self, site: Site) -> None:
        tokens_by_day: dict[datetime, int] = {}

        for _ in range(96):
            exchange = self.rng.choice(script.ANSWERED)
            started = self._when()
            conversation = self._conversation(site, exchange.language, started, exchange.page)
            self._add_messages(
                conversation,
                [
                    Message(role=MessageRole.VISITOR, content=exchange.question),
                    Message(
                        role=MessageRole.BOT,
                        content=exchange.answer,
                        sources=[self._source_card(exchange.page)],
                        confidence=round(self.rng.uniform(0.62, 0.97), 3),
                        answered=True,
                        tokens_in=self.rng.randint(900, 1600),
                        tokens_out=self.rng.randint(40, 120),
                    ),
                ],
            )
            roll = self.rng.random()
            conversation.rating = 1 if roll < 0.42 else (-1 if roll > 0.95 else None)
            self.session.add(conversation)
            day = started.replace(hour=0, minute=0)
            tokens_by_day[day] = tokens_by_day.get(day, 0) + 1500

        for question, language, times in script.UNANSWERED:
            embedding = await self.embedder.embed_query(question)
            last = None
            for _ in range(times):
                started = self._when()
                last = max(last, started) if last else started
                conversation = self._conversation(site, language, started, "index")
                self._add_messages(
                    conversation,
                    [
                        Message(role=MessageRole.VISITOR, content=question),
                        Message(
                            role=MessageRole.BOT,
                            content=(
                                "I couldn't find a reliable answer to that in Ohm & Solder's "
                                "materials, and I'd rather not guess. I can pass your question "
                                "to a manager, or you can leave a contact and they'll get back "
                                "to you."
                                if language == "en"
                                else "В материалах Ohm & Solder нет точного ответа на этот "
                                "вопрос, а гадать я не хочу. Могу передать вопрос менеджеру "
                                "или оставьте контакт, вам ответят."
                            ),
                            confidence=round(self.rng.uniform(0.05, 0.4), 3),
                            answered=False,
                        ),
                    ],
                )
                self.session.add(conversation)
            self.session.add(
                KnowledgeGap(
                    site_id=site.id,
                    question=question,
                    embedding=embedding,
                    times_asked=times,
                    status=GapStatus.OPEN,
                    last_asked_at=last or datetime.now(UTC),
                )
            )

        for index, (question, reply) in enumerate(script.HANDOFFS):
            started = self._when(days_back_max=6 if index else 1)
            language = "ru" if any("а" <= ch <= "я" for ch in question.lower()) else "en"
            conversation = self._conversation(site, language, started, "index")
            conversation.handoff_requested_at = started + timedelta(minutes=1)
            conversation.manager_name = "Inês"
            conversation.status = (
                ConversationStatus.WAITING if index == 0 else ConversationStatus.CLOSED
            )
            messages = [
                Message(role=MessageRole.VISITOR, content=question),
                Message(
                    role=MessageRole.SYSTEM,
                    content="I've passed the conversation to a manager. They usually reply "
                    "within a few minutes during working hours, right here in this chat.",
                ),
            ]
            if index:
                messages.append(
                    Message(role=MessageRole.MANAGER, content=reply, author_name="Inês")
                )
            self._add_messages(conversation, messages)
            self.session.add(conversation)

        for name, contact, question in script.LEADS:
            started = self._when()
            self.session.add(
                Lead(
                    site_id=site.id,
                    name=name,
                    contact=contact,
                    question=question,
                    status=self.rng.choice(
                        [LeadStatus.NEW, LeadStatus.NEW, LeadStatus.IN_PROGRESS, LeadStatus.DONE]
                    ),
                    sample=True,
                    created_at=started,
                )
            )

        for day, tokens in tokens_by_day.items():
            self.session.add(
                UsageDaily(
                    site_id=site.id,
                    day=day.date(),
                    requests=tokens // 1500,
                    tokens_in=int(tokens * 0.93),
                    tokens_out=int(tokens * 0.07),
                )
            )

    async def seed_owner(self, email: str, password: str, site_key: str | None) -> Site | None:
        """Levon's own workspace with the narcisbin.com assistant."""
        if await self.session.scalar(select(User).where(User.email == email.lower())):
            return None
        workspace = Workspace(name="narcisbin")
        self.session.add(workspace)
        await self.session.flush()
        self.session.add(
            User(
                workspace_id=workspace.id,
                email=email.lower(),
                name="Levon",
                password_hash=password_hash.hash(password),
            )
        )
        site = Site(
            workspace_id=workspace.id,
            name="Levon Oganesian",
            public_key=site_key or f"pk_{secrets.token_urlsafe(12)}",
            telegram_link_token=secrets.token_urlsafe(12),
            allowed_domains=["narcisbin.com"],
            confidence_threshold=0.35,
            monthly_token_budget=500_000,
            instructions=(
                "You answer for Levon, a freelance full-stack developer, in the third person. "
                "Be concise and concrete. Never quote prices or deadlines: say the estimate "
                "comes after a short call, and point to Telegram @narcisbin."
            ),
            widget=WidgetSettings(
                title="Ask about Levon",
                subtitle="Answers from narcisbin.com",
                greeting=(
                    "Hi! I can tell you about Levon's projects, stack and how he works. For "
                    "anything else, I'll pass your message to him."
                ),
                accent="#2F5BD3",
                quick_questions=[
                    "What has Levon built with AI?",
                    "Does he build Telegram Mini Apps?",
                    "How does a project start?",
                    "How can I contact him?",
                ],
            ).model_dump(),
        )
        self.session.add(site)
        await self.session.flush()
        source = Source(
            site_id=site.id,
            kind=SourceKind.URL,
            title="narcisbin.com",
            url="https://narcisbin.com",
            status=SourceStatus.INDEXING,
        )
        self.session.add(source)
        await self.session.flush()
        documents = [
            RawDocument(
                title=path.stem.replace("-", " ").capitalize(),
                text=path.read_text(encoding="utf-8"),
                url=f"https://narcisbin.com/#{path.stem}",
            )
            for path in sorted(NARCISBIN_DIR.glob("*.md"))
        ]
        await self.indexer.ingest_documents(source, documents)
        await self.session.commit()
        return site
