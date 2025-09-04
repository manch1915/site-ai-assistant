"""Maintenance commands: `seed [--if-empty]` and `reset-demo`, run as `python -m app.cli`."""

import argparse
import asyncio
import logging
from pathlib import Path

from sqlalchemy import select

from app.container import Container, get_container
from app.infra.db.models import Site
from app.seed.calibration import ANSWERABLE, UNANSWERABLE
from app.seed.runner import DEMO_KEY, Seeder
from app.services.indexing import IndexingService
from app.services.retrieval import RetrievalService

log = logging.getLogger("relay.cli")


async def run_seed(container: Container, action: str, if_empty: bool) -> None:
    settings = container.settings
    async with container.database.session() as session:
        indexer = IndexingService(session, container.embedder, container.crawler, container.storage)
        seeder = Seeder(session, indexer, container.embedder, settings, Path(settings.upload_dir))
        if action == "reset-demo":
            await seeder.reset_demo()
            log.info("Demo workspace recreated")
            return
        if if_empty and not await seeder.is_empty():
            log.info("Database already has data, skipping seed")
            return
        await seeder.reset_demo()
        log.info("Demo workspace ready, widget key pk_demo_ohmsolder")
        if settings.owner_email and settings.owner_password:
            site = await seeder.seed_owner(
                settings.owner_email, settings.owner_password, settings.owner_site_key or None
            )
            if site:
                log.info("Owner workspace ready, widget key %s", site.public_key)


async def calibrate(container: Container) -> None:
    settings = container.settings
    async with container.database.session() as session:
        site = await session.scalar(select(Site).where(Site.public_key == DEMO_KEY))
        if site is None:
            raise SystemExit("Seed the demo first")
        retrieval = RetrievalService(
            session, container.embedder, settings.similarity_floor, settings.similarity_ceiling
        )
        threshold = site.confidence_threshold
        correct = 0
        for expected, questions in ((True, ANSWERABLE), (False, UNANSWERABLE)):
            for question in questions:
                found = await retrieval.search(site.id, question)
                passes = found.confidence >= threshold
                correct += passes == expected
                mark = "ok " if passes == expected else "MISS"
                verdict = "answer" if expected else "refuse"
                print(f"{mark} {found.confidence:5.2f}  {verdict}  {question}")
        total = len(ANSWERABLE) + len(UNANSWERABLE)
        print(f"{correct}/{total} on the right side of threshold {threshold}")


async def link_telegram(container: Container, site_key: str, chat_id: int, title: str) -> None:
    """For bots that don't read updates (shared tokens), where the /start link can't work."""
    async with container.database.session() as session:
        site = await session.scalar(select(Site).where(Site.public_key == site_key))
        if site is None:
            raise SystemExit(f"No site with key {site_key}")
        site.telegram_chat_id = chat_id
        site.telegram_chat_title = title
        await session.commit()
        log.info("Handoffs from %s now go to the Telegram chat %s", site.name, title)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(prog="relay")
    commands = parser.add_subparsers(dest="command", required=True)
    seed = commands.add_parser("seed", help="Create the demo shop and the owner workspace")
    seed.add_argument("--if-empty", action="store_true", help="Do nothing if data exists")
    commands.add_parser("reset-demo", help="Recreate the public demo workspace")
    commands.add_parser("calibrate", help="Check the confidence threshold on sample questions")
    link = commands.add_parser(
        "link-telegram", help="Send a site's handoffs to a Telegram chat without the /start link"
    )
    link.add_argument("site_key")
    link.add_argument("chat_id", type=int)
    link.add_argument("--title", default="Managers")
    args = parser.parse_args()
    container = get_container()
    if args.command == "calibrate":
        asyncio.run(calibrate(container))
        return
    if args.command == "link-telegram":
        asyncio.run(link_telegram(container, args.site_key, args.chat_id, args.title))
        return
    asyncio.run(run_seed(container, args.command, getattr(args, "if_empty", False)))


if __name__ == "__main__":
    main()
