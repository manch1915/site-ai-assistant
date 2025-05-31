import { describe, expect, it } from "vitest";

import { parseBlock, readSse } from "../src/sse";

function streamOf(...chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
}

async function collect(stream: ReadableStream<Uint8Array>) {
  const events = [];
  for await (const event of readSse(stream)) events.push(event);
  return events;
}

describe("readSse", () => {
  it("reassembles events split across network chunks", async () => {
    const events = await collect(
      streamOf(
        'event: token\ndata: {"text":',
        ' "Hi"}\n\nevent: do',
        'ne\ndata: {"mode":"llm"}\n\n',
      ),
    );
    expect(events).toEqual([
      { event: "token", data: '{"text": "Hi"}' },
      { event: "done", data: '{"mode":"llm"}' },
    ]);
  });

  it("handles CRLF line endings and a missing final blank line", async () => {
    const events = await collect(streamOf("event: start\r\ndata: 1\r\n\r\ndata: 2"));
    expect(events).toEqual([
      { event: "start", data: "1" },
      { event: "message", data: "2" },
    ]);
  });
});

describe("parseBlock", () => {
  it("skips comments used as keep-alive pings", () => {
    expect(parseBlock(": ping")).toBeNull();
  });

  it("joins multi-line data", () => {
    expect(parseBlock("data: a\ndata: b")).toEqual({ event: "message", data: "a\nb" });
  });
});
