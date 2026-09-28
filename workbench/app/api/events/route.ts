import { promises as fs } from "node:fs";
import path from "node:path";

export const dynamic = "force-dynamic";

const ROOT = path.resolve(process.cwd(), "..");
const WATCHED = [
  "data/ideas/video-album.json",
  "topics/video-album/topics.json",
  "data/events/video-album.jsonl",
  "facts/feature/video-album--feature-video-album/manifest.json",
  "facts/feature/video-album--feature-video-album/facts.jsonl",
  "facts/feature/video-album--feature-video-album/reviews/gate-report.json",
  "content/briefs/video-album/G1-02/production-brief.json",
  "content/briefs/video-album/G1-02/script.md",
  "content/packages/channels/video-album/G1-02/copy.md",
  "content/packages/douyin/video-album/G1-02/copy.md",
  "content/packages/xhs/video-album/G1-02/copy.md",
  "content/packages/blog/video-album/G1-02/article.md",
  "content/briefs/video-album/P1-06/production-brief.json",
  "content/briefs/video-album/P1-06/script.md",
  "content/packages/channels/video-album/P1-06/copy.md",
  "content/packages/douyin/video-album/P1-06/copy.md",
  "content/packages/xhs/video-album/P1-06/copy.md",
  "content/packages/blog/video-album/P1-06/article.md",
];

async function signature() {
  const values = await Promise.all(WATCHED.map(async (file) => {
    try { return (await fs.stat(path.join(ROOT, file))).mtimeMs; } catch { return 0; }
  }));
  return values.join(":");
}

export async function GET(request: Request) {
  const encoder = new TextEncoder();
  let previous = await signature();
  let timer: ReturnType<typeof setInterval> | undefined;
  const stream = new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode("event: ready\ndata: connected\n\n"));
      timer = setInterval(async () => {
        const current = await signature();
        if (current !== previous) {
          previous = current;
          controller.enqueue(encoder.encode(`event: workspace\ndata: ${Date.now()}\n\n`));
        } else {
          controller.enqueue(encoder.encode(": heartbeat\n\n"));
        }
      }, 1200);
      request.signal.addEventListener("abort", () => {
        if (timer) clearInterval(timer);
        try { controller.close(); } catch {}
      });
    },
    cancel() { if (timer) clearInterval(timer); },
  });
  return new Response(stream, { headers: { "Content-Type": "text/event-stream", "Cache-Control": "no-cache, no-transform", Connection: "keep-alive" } });
}
