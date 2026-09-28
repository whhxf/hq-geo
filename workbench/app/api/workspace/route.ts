import { promises as fs } from "node:fs";
import path from "node:path";
import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

const ROOT = path.resolve(process.cwd(), "..");

async function json(file: string) {
  return JSON.parse(await fs.readFile(path.join(ROOT, file), "utf8"));
}

async function jsonl(file: string) {
  const content = await fs.readFile(path.join(ROOT, file), "utf8");
  return content.split("\n").filter(Boolean).map((line) => JSON.parse(line));
}

async function text(file: string) {
  return fs.readFile(path.join(ROOT, file), "utf8");
}

async function exists(file: string) {
  try { await fs.access(path.join(ROOT, file)); return true; } catch { return false; }
}

async function factPacks() {
  const factsRoot = path.join(ROOT, "facts");
  const types = await fs.readdir(factsRoot, { withFileTypes: true });
  const packs = [];
  for (const type of types.filter((entry) => entry.isDirectory() && !["schemas", "scripts", "tests"].includes(entry.name))) {
    const typeRoot = path.join(factsRoot, type.name);
    for (const entry of await fs.readdir(typeRoot, { withFileTypes: true })) {
      if (!entry.isDirectory()) continue;
      const relative = path.join("facts", type.name, entry.name);
      try {
        const [manifest, facts, gate] = await Promise.all([
          json(path.join(relative, "manifest.json")),
          jsonl(path.join(relative, "facts.jsonl")),
          json(path.join(relative, "reviews/gate-report.json")),
        ]);
        packs.push({ ...manifest, path: relative, facts, gate });
      } catch {}
    }
  }
  return packs;
}

async function contentProjects(topics: Array<Record<string, any>>) {
  const briefsRoot = path.join(ROOT, "content/briefs/video-album");
  const entries = await fs.readdir(briefsRoot, { withFileTypes: true });
  const projects = [];
  for (const entry of entries.filter((item) => item.isDirectory())) {
    const topic = topics.find((item) => item.id === entry.name);
    const briefPath = `content/briefs/video-album/${entry.name}/production-brief.json`;
    if (!topic || !(await exists(briefPath))) continue;
    const brief = await json(briefPath);
    const candidates = [
      { id: brief.id, kind: "母脚本", channel: "视频", title: brief.title, status: "ready_for_review", path: `content/briefs/video-album/${entry.name}/script.md`, summary: `${brief.target_duration_seconds.min}–${brief.target_duration_seconds.max} 秒口播` },
      { id: `${entry.name}-channels`, kind: "渠道版本", channel: "视频号", title: topic.title, status: "draft", path: `content/packages/channels/video-album/${entry.name}/copy.md`, summary: "经营判断、信任与完整解释" },
      { id: `${entry.name}-douyin`, kind: "渠道版本", channel: "抖音", title: topic.title, status: "draft", path: `content/packages/douyin/video-album/${entry.name}/copy.md`, summary: "画面对比与快速理解" },
      { id: `${entry.name}-xhs`, kind: "渠道版本", channel: "小红书", title: topic.title, status: "draft", path: `content/packages/xhs/video-album/${entry.name}/copy.md`, summary: "搜索、清单与收藏" },
      { id: `${entry.name}-blog`, kind: "文章成稿", channel: "博客", title: topic.title, status: "ready_for_review", path: `content/packages/blog/video-album/${entry.name}/article.md`, summary: "完整论证与事实边界" },
    ];
    const deliverables = [];
    for (const item of candidates) if (await exists(item.path)) deliverables.push({ ...item, content: await text(item.path) });
    const stat = await fs.stat(path.join(ROOT, briefPath));
    projects.push({ topic, updated_at: stat.mtime.toISOString(), deliverables });
  }
  return projects.sort((a, b) => b.updated_at.localeCompare(a.updated_at));
}

export async function GET() {
  const idea = await json("data/ideas/video-album.json");
  const topicData = await json("topics/video-album/topics.json");
  const eventText = await fs.readFile(path.join(ROOT, "data/events/video-album.jsonl"), "utf8");
  const events = eventText.trim().split("\n").filter(Boolean).map((line) => JSON.parse(line)).reverse();
  let quality = null;
  const topicId = idea.selected_topic_id;
  const selectedTopic = topicData.topics.find((topic: { id: string }) => topic.id === topicId);
  const projects = await contentProjects(topicData.topics);
  const currentProject = projects.find((project) => project.topic.id === topicId) ?? projects[0];
  try {
    const report = await json("test/reports/latest.json");
    quality = { verdict: report.verdict, profile: report.profile, passed: report.passed, total: report.total };
  } catch {}
  const topics = topicData.topics;
  return NextResponse.json({
    idea,
    topics,
    selectedTopic,
    events,
    quality,
    factPacks: await factPacks(),
    deliverables: currentProject?.deliverables ?? [],
    contentProjects: projects,
    counts: {
      total: topics.length,
      longTerm: topics.filter((topic: { collection: string }) => topic.collection === "长期选题").length,
      cantonFair: topics.filter((topic: { collection: string }) => topic.collection === "广交会专题").length,
      needsInput: topics.filter((topic: { status: string }) => topic.status === "needs_input").length,
    },
  }, { headers: { "Cache-Control": "no-store" } });
}
