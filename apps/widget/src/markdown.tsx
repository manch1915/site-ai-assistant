import type { ComponentChildren, JSX } from "preact";

/**
 * Just enough Markdown for chat answers: paragraphs, lists, quotes, bold, links and [n]
 * citations. Builds VNodes directly, so model output never reaches innerHTML.
 */

const INLINE =
  /(\*\*[^*]+\*\*|\[[^\]]+\]\((https?:\/\/[^)\s]+)\)|https?:\/\/[^\s<>)]+|\[\d{1,2}\])/g;

export function safeUrl(url: string): string | null {
  try {
    const parsed = new URL(url);
    return parsed.protocol === "http:" || parsed.protocol === "https:" ? parsed.href : null;
  } catch {
    return null;
  }
}

export function renderInline(text: string, onCite?: (index: number) => void): ComponentChildren[] {
  const out: ComponentChildren[] = [];
  let last = 0;
  for (const match of text.matchAll(INLINE)) {
    const token = match[0];
    const start = match.index ?? 0;
    if (start > last) out.push(text.slice(last, start));
    last = start + token.length;

    if (token.startsWith("**")) {
      out.push(<strong>{token.slice(2, -2)}</strong>);
    } else if (/^\[\d{1,2}\]$/.test(token)) {
      const index = Number(token.slice(1, -1));
      out.push(
        <button
          type="button"
          class="cite"
          onClick={() => onCite?.(index)}
          aria-label={`Source ${index}`}
        >
          {index}
        </button>,
      );
    } else if (token.startsWith("[")) {
      const label = token.slice(1, token.indexOf("]("));
      const href = safeUrl(match[2] ?? "");
      out.push(
        href ? (
          <a href={href} target="_blank" rel="noopener noreferrer">
            {label}
          </a>
        ) : (
          label
        ),
      );
    } else {
      const href = safeUrl(token);
      out.push(
        href ? (
          <a href={href} target="_blank" rel="noopener noreferrer">
            {token}
          </a>
        ) : (
          token
        ),
      );
    }
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

interface ListBlock {
  kind: "ul" | "ol";
  items: string[];
}
interface TextBlock {
  kind: "p" | "quote";
  lines: string[];
}
type Block = ListBlock | TextBlock;

const isList = (block: Block): block is ListBlock => block.kind === "ul" || block.kind === "ol";

export function parseBlocks(source: string): Block[] {
  const blocks: Block[] = [];
  for (const raw of source.replace(/\r\n/g, "\n").split("\n")) {
    const line = raw.trimEnd();
    const current = blocks[blocks.length - 1];
    const bullet = /^\s*[-*•]\s+(.*)$/.exec(line);
    const numbered = /^\s*\d+[.)]\s+(.*)$/.exec(line);
    const quote = /^>\s?(.*)$/.exec(line);
    if (!line.trim()) {
      blocks.push({ kind: "p", lines: [] });
    } else if (bullet?.[1] !== undefined) {
      if (current?.kind === "ul") current.items.push(bullet[1]);
      else blocks.push({ kind: "ul", items: [bullet[1]] });
    } else if (numbered?.[1] !== undefined) {
      if (current?.kind === "ol") current.items.push(numbered[1]);
      else blocks.push({ kind: "ol", items: [numbered[1]] });
    } else if (quote?.[1] !== undefined) {
      if (current?.kind === "quote") current.lines.push(quote[1]);
      else blocks.push({ kind: "quote", lines: [quote[1]] });
    } else if (current?.kind === "p") {
      current.lines.push(line);
    } else {
      blocks.push({ kind: "p", lines: [line] });
    }
  }
  return blocks.filter((b) => (isList(b) ? b.items.length : b.lines.length));
}

export function Markdown(props: { text: string; onCite?: (index: number) => void }): JSX.Element {
  const { text, onCite } = props;
  return (
    <>
      {parseBlocks(text).map((block) => {
        if (isList(block)) {
          const List = block.kind;
          return (
            <List>
              {block.items.map((item) => (
                <li>{renderInline(item, onCite)}</li>
              ))}
            </List>
          );
        }
        const content = block.lines.flatMap((line, i) => [
          ...(i ? [<br />] : []),
          ...renderInline(line, onCite),
        ]);
        return block.kind === "quote" ? <blockquote>{content}</blockquote> : <p>{content}</p>;
      })}
    </>
  );
}
