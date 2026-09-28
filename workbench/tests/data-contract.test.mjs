import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";

const root = path.resolve(import.meta.dirname, "../..");
const load = async (file) => JSON.parse(await readFile(path.join(root, file), "utf8"));

test("video album imports every source topic exactly once", async () => {
  const data = await load("topics/video-album/topics.json");
  assert.equal(data.topics.length, 91);
  assert.equal(new Set(data.topics.map((topic) => topic.id)).size, 91);
  assert.equal(data.topics.filter((topic) => topic.collection === "长期选题").length, 43);
  assert.equal(data.topics.filter((topic) => topic.collection === "广交会专题").length, 48);
});

test("selected topic and idea state remain aligned", async () => {
  const [idea, data] = await Promise.all([
    load("data/ideas/video-album.json"),
    load("topics/video-album/topics.json"),
  ]);
  assert.equal(idea.selected_topic_id, data.selected_topic_id);
  const selected = data.topics.find((topic) => topic.id === idea.selected_topic_id);
  assert.ok(selected);
  assert.equal(selected.status, "needs_input");
  assert.equal(selected.stage, "canonical");
  assert.ok(idea.facts.some((fact) => fact.status === "needs_confirmation"));
});

test("every topic exposes the fields required by the workbench", async () => {
  const data = await load("topics/video-album/topics.json");
  const required = ["id", "title", "collection", "pillar", "angle", "proof", "platforms", "stage", "status", "next_action", "progress"];
  for (const topic of data.topics) {
    for (const field of required) assert.ok(field in topic, `${topic.id} missing ${field}`);
    assert.ok(topic.title.length > 0);
    assert.ok(topic.progress >= 0 && topic.progress <= 100);
  }
});

test("video album fact pack exposes required facts and honest media gaps", async () => {
  const packRoot = "facts/feature/video-album--feature-video-album";
  const [manifest, report, factText] = await Promise.all([
    load(`${packRoot}/manifest.json`),
    load(`${packRoot}/reviews/gate-report.json`),
    readFile(path.join(root, packRoot, "facts.jsonl"), "utf8"),
  ]);
  const facts = factText.trim().split("\n").map(JSON.parse);
  assert.equal(manifest.id, "feature-video-album");
  assert.deepEqual(manifest.required_slots.map((slot) => slot.id), ["company", "online-ui", "image-introduction", "method", "scenarios", "step-video", "operations"]);
  assert.ok(manifest.protected_fact_ids.every((id) => facts.some((fact) => fact.id === id)));
  assert.equal(report.verdict, "PASS");
  assert.equal(report.creation_ready, false);
  const resolvedQuestion = manifest.pending_questions.find((question) => question.id === "va-q-first-version-evidence");
  assert.equal(resolvedQuestion.status, "resolved");
  assert.ok(resolvedQuestion.result_fact_ids.every((id) => facts.some((fact) => fact.id === id)));
  for (const asset of manifest.media_assets.filter((item) => item.status === "missing")) {
    assert.equal(asset.path, null);
    assert.equal(asset.url, null);
  }
});

test("G1-02 exposes reviewable creation outputs, not only a topic", async () => {
  const files = [
    "content/briefs/video-album/G1-02/script.md",
    "content/packages/channels/video-album/G1-02/copy.md",
    "content/packages/douyin/video-album/G1-02/copy.md",
    "content/packages/xhs/video-album/G1-02/copy.md",
    "content/packages/blog/video-album/G1-02/article.md",
  ];
  for (const file of files) {
    const content = await readFile(path.join(root, file), "utf8");
    assert.ok(content.length > 120, `${file} is not a substantive deliverable`);
  }
  const script = await readFile(path.join(root, files[0]), "utf8");
  assert.match(script, /产品合不合适/);
  assert.match(script, /你做什么产品/);
});

test("P1-06 exposes a complete review set and safe causal boundaries", async () => {
  const files = [
    "content/briefs/video-album/P1-06/script.md",
    "content/briefs/video-album/P1-06/production-brief.json",
    "content/packages/channels/video-album/P1-06/copy.md",
    "content/packages/douyin/video-album/P1-06/copy.md",
    "content/packages/xhs/video-album/P1-06/copy.md",
    "content/packages/blog/video-album/P1-06/article.md",
  ];
  for (const file of files) {
    const content = await readFile(path.join(root, file), "utf8");
    assert.ok(content.length > 120, `${file} is not a substantive deliverable`);
  }
  const brief = await load(files[1]);
  assert.equal(brief.status, "blocked");
  assert.equal(brief.handoff.ready, false);
  assert.ok(brief.prohibited_claims.some((claim) => claim.includes("都是宣传片造成")));
});

test("creation workspace has multiple switchable topic result sets", async () => {
  const topicIds = ["G1-02", "P1-06"];
  for (const topicId of topicIds) {
    const brief = await load(`content/briefs/video-album/${topicId}/production-brief.json`);
    assert.equal(brief.topic_id, topicId);
    const channels = ["channels", "douyin", "xhs", "blog"];
    for (const channel of channels) {
      const filename = channel === "blog" ? "article.md" : "copy.md";
      const content = await readFile(path.join(root, `content/packages/${channel}/video-album/${topicId}/${filename}`), "utf8");
      assert.ok(content.length > 120, `${topicId}/${channel} missing reviewable content`);
    }
  }
});

test("creation workspace uses one searchable result selector without duplicate tabs", async () => {
  const component = await readFile(path.join(root, "workbench/components/creator-workbench.tsx"), "utf8");
  assert.match(component, /placeholder="搜索编号、标题或内容角度"/);
  assert.match(component, /filteredContentProjects\.map/);
  assert.match(component, /function openCreatedTopic\(topicId: string\)/);
  assert.doesNotMatch(component, /TabsTrigger value="created"/);
});
