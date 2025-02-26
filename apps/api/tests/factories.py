import secrets

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import SourceKind, SourceStatus
from app.infra.db.models import Site, Source, Workspace


async def make_site(session: AsyncSession, **overrides: object) -> Site:
    workspace = Workspace(name="Ohm & Solder")
    session.add(workspace)
    await session.flush()
    site = Site(
        workspace_id=workspace.id,
        name="Ohm & Solder",
        public_key=f"pk_{secrets.token_hex(8)}",
        telegram_link_token=secrets.token_hex(8),
        allowed_domains=["ohmsolder.test"],
        widget={},
        **overrides,
    )
    session.add(site)
    await session.flush()
    return site


async def make_source(
    session: AsyncSession, site: Site, kind: SourceKind = SourceKind.URL, title: str = "Pages"
) -> Source:
    source = Source(site_id=site.id, kind=kind, title=title, status=SourceStatus.QUEUED)
    session.add(source)
    await session.flush()
    return source


def minimal_pdf(text: str) -> bytes:
    """Hand-rolled single-page PDF, enough for pypdf to extract the text."""
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    return bytes(out)
