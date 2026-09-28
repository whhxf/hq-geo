"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Archive, BookOpen, Check, CircleAlert, Clipboard, FileOutput, FileText, Flame, FolderOpen, Image, Library, Link2, MessageSquareText, PackageCheck, Radio, Search, Sparkles, Video } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { Topic, WorkspaceData } from "@/lib/types";
import { cn } from "@/lib/utils";

const stages = [
  ["research", "调研"], ["topic_ready", "选题"], ["fact_lock", "事实"], ["canonical", "母稿"],
  ["voice_review", "作者化"], ["platform_render", "平台版本"], ["assets", "素材"], ["preflight", "预检"], ["publish", "发布"],
];

const nav = [
  { id: "today", label: "今日需要你", icon: Flame },
  { id: "topics", label: "全部选题", icon: Library },
  { id: "content", label: "创作成果", icon: FileOutput },
  { id: "facts", label: "事实基础", icon: BookOpen },
  { id: "publish", label: "发布准备", icon: PackageCheck },
];

function StatusBadge({ status }: { status: string }) {
  if (status === "needs_input") return <Badge variant="warning">需要你</Badge>;
  if (status === "verified" || status === "pass") return <Badge variant="success">已核验</Badge>;
  if (status === "needs_confirmation") return <Badge variant="warning">待确认</Badge>;
  if (status === "present") return <Badge variant="success">已有</Badge>;
  if (status === "partial") return <Badge variant="warning">部分</Badge>;
  if (status === "missing") return <Badge variant="outline">缺失</Badge>;
  if (status === "prohibited_claim") return <Badge variant="outline">禁止宣称</Badge>;
  if (status === "ready_for_review") return <Badge variant="success">可审阅</Badge>;
  if (status === "draft") return <Badge variant="outline">草稿</Badge>;
  if (status === "blocked") return <Badge variant="warning">受阻</Badge>;
  return <Badge variant="outline">{status}</Badge>;
}

function StageRail({ current }: { current: string }) {
  const currentIndex = stages.findIndex(([id]) => id === current);
  return <div className="stage-rail" aria-label="创作进度">
    {stages.map(([id, label], index) => <div className={cn("stage-step", index < currentIndex && "done", index === currentIndex && "current")} key={id}>
      <span className="stage-dot">{index < currentIndex ? <Check size={11} /> : index + 1}</span>
      <span>{label}</span>
    </div>)}
  </div>;
}

function cleanMarkdown(value: string) {
  return value.replace(/\*\*(.*?)\*\*/g, "$1").replace(/`([^`]+)`/g, "$1");
}

function ReadableMarkdown({ content }: { content: string }) {
  const lines = content.split("\n");
  let inFrontmatter = lines[0]?.trim() === "---";
  return <div className="readable-document">{lines.map((raw, index) => {
    const line = raw.trim();
    if (index === 0 && inFrontmatter) return null;
    if (inFrontmatter) {
      if (line === "---") inFrontmatter = false;
      return null;
    }
    if (!line) return <span className="document-space" key={index} />;
    if (line.startsWith("### ")) return <h4 key={index}>{cleanMarkdown(line.slice(4))}</h4>;
    if (line.startsWith("## ")) return <h3 key={index}>{cleanMarkdown(line.slice(3))}</h3>;
    if (line.startsWith("# ")) return <h2 key={index}>{cleanMarkdown(line.slice(2))}</h2>;
    if (line.startsWith("> ")) return <blockquote key={index}>{cleanMarkdown(line.slice(2))}</blockquote>;
    if (/^[-*] /.test(line)) return <p className="document-bullet" key={index}>{cleanMarkdown(line.slice(2))}</p>;
    const numbered = line.match(/^(\d+)\.\s+(.*)$/);
    if (numbered) return <p className="document-number" key={index}><b>{numbered[1]}</b>{cleanMarkdown(numbered[2])}</p>;
    return <p key={index}>{cleanMarkdown(line)}</p>;
  })}</div>;
}

export function CreatorWorkbench() {
  const [data, setData] = useState<WorkspaceData | null>(null);
  const [view, setView] = useState("today");
  const [query, setQuery] = useState("");
  const [collection, setCollection] = useState("全部");
  const [inspectedTopic, setInspectedTopic] = useState<Topic | null>(null);
  const [copied, setCopied] = useState(false);
  const [selectedDeliverableId, setSelectedDeliverableId] = useState("");
  const [selectedContentTopicId, setSelectedContentTopicId] = useState("");
  const [contentPickerOpen, setContentPickerOpen] = useState(false);
  const [contentQuery, setContentQuery] = useState("");

  const load = useCallback(async () => {
    const response = await fetch("/api/workspace", { cache: "no-store" });
    if (!response.ok) throw new Error("无法读取工作台数据");
    setData(await response.json());
  }, []);

  useEffect(() => {
    load();
    const stream = new EventSource("/api/events");
    stream.addEventListener("workspace", load);
    return () => stream.close();
  }, [load]);

  const filtered = useMemo(() => data?.topics.filter((topic) => {
    const matchCollection = collection === "全部" || topic.collection === collection;
    const haystack = `${topic.id} ${topic.title} ${topic.pillar} ${topic.angle}`.toLowerCase();
    return matchCollection && haystack.includes(query.toLowerCase());
  }) ?? [], [data, collection, query]);
  const filteredContentProjects = useMemo(() => data?.contentProjects.filter((project) => {
    const haystack = `${project.topic.id} ${project.topic.title} ${project.topic.collection} ${project.topic.pillar} ${project.topic.angle}`.toLowerCase();
    return haystack.includes(contentQuery.trim().toLowerCase());
  }) ?? [], [data, contentQuery]);

  if (!data) return <div className="loading-shell"><Flame className="pulse" /><span>正在恢复创作现场…</span></div>;
  const selected = inspectedTopic ?? data.selectedTopic;
  const factPack = data.factPacks[0];
  const selectedContentProject = data.contentProjects.find((project) => project.topic.id === selectedContentTopicId) ?? data.contentProjects.find((project) => project.topic.id === data.selectedTopic.id) ?? data.contentProjects[0];
  const selectedDeliverable = selectedContentProject.deliverables.find((item) => item.id === selectedDeliverableId) ?? selectedContentProject.deliverables[0];
  const nextFactQuestion = factPack?.pending_questions.filter((item) => item.status === "pending").sort((a, b) => a.priority - b.priority)[0];
  const prompt = `继续推进“视频画册”创作。当前选题：${selected.id}｜${selected.title}。请读取项目状态和事实基础，从当前阶段继续，不要重新开始。`;

  async function copyPrompt() {
    await navigator.clipboard.writeText(prompt);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  }

  function openCreatedTopic(topicId: string) {
    const topic = data?.topics.find((item) => item.id === topicId);
    if (topic) setInspectedTopic(topic);
    setSelectedContentTopicId(topicId);
    setSelectedDeliverableId("");
    setContentPickerOpen(false);
    setContentQuery("");
  }

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><span className="brand-mark"><Flame size={18} /></span><div><strong>燃点</strong><small>创作工作台</small></div></div>
      <nav>{nav.map((item) => <button key={item.id} onClick={() => setView(item.id)} className={cn("nav-item", view === item.id && "active")}><item.icon size={17} /><span>{item.label}</span>{item.id === "today" && <em>1</em>}</button>)}</nav>
      <div className="sidebar-bottom">
        <div className="sync-line"><Radio size={13} /><span>正在监听项目文件</span></div>
        <div className="quality-line"><span>质量门禁</span><StatusBadge status={data.quality?.verdict ?? "unknown"} /></div>
      </div>
    </aside>

    <main className="main-area">
      <header className="topbar">
        <div><span className="eyebrow">当前主题</span><h1>{data.idea.title}</h1></div>
        <div className="top-actions"><Badge variant="outline">{data.counts.total} 个备选选题</Badge><Button variant="outline" size="sm" onClick={() => setView("topics")}><Search size={14} />查找选题</Button></div>
      </header>

      {view === "today" && <section className="content-view">
        <div className="section-heading"><div><span className="eyebrow">今天只处理这一件事</span><h2>让第一条内容拥有你的判断</h2><p>研究和选题已经完成。系统卡在事实锁定，因为这一步不能替你编。</p></div><StatusBadge status="needs_input" /></div>

        <div className="focus-panel">
          <div className="focus-number">{data.selectedTopic.id}</div>
          <div className="focus-main">
            <div className="focus-title-row"><h3>{data.selectedTopic.title}</h3><Badge variant="secondary">广交会专题</Badge></div>
            <p className="thesis">{data.selectedTopic.angle}</p>
            <div className="decision-box"><MessageSquareText size={18} /><div><strong>现在需要你</strong><p>{data.idea.next_action}</p></div></div>
            <div className="action-row">
              <Button asChild><a href={`codex://threads/${data.idea.source_thread_id}`}><Sparkles size={16} />回到 Codex 继续创作</a></Button>
              <Button variant="outline" onClick={copyPrompt}>{copied ? <Check size={16} /> : <Clipboard size={16} />}{copied ? "已复制" : "复制续接提示"}</Button>
            </div>
          </div>
          <div className="focus-proof"><span>必备演示</span><strong>{data.selectedTopic.proof}</strong><small>素材确认后，AI 才会生成母内容和三个平台版本。</small></div>
        </div>

        <div className="progress-section"><div className="progress-copy"><span>总体进度</span><strong>{data.idea.progress}%</strong></div><Progress value={data.idea.progress} /><StageRail current={data.idea.stage} /></div>

        <div className="two-column">
          <div className="plain-section"><div className="subheading"><h3>已经做好</h3><span>{data.events.length} 条进展记录</span></div><div className="event-list">{data.events.map((event) => <div className="event" key={event.event_id}><span className="event-check"><Check size={12} /></span><div><strong>{event.summary}</strong><small>{new Date(event.at).toLocaleString("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" })}</small></div></div>)}</div></div>
          <div className="plain-section"><div className="subheading"><h3>接下来由系统完成</h3><span>你不用管理这些步骤</span></div><ol className="next-list"><li>补齐选题事实与个人观点</li><li>生成平台无关的母内容</li><li>完成作者化检查，减少机械表达</li><li>派生视频号、抖音、小红书版本</li><li>准备分镜、封面、字幕与发布预检</li></ol></div>
        </div>
        <div className="deliverable-section"><div className="subheading"><h3>实际创作交付</h3><span>选题不计入完成</span></div><div className="deliverable-grid">{data.deliverables.map((item) => <div className="deliverable-card" key={item.id}><span>{item.kind}</span><StatusBadge status={item.status} /><strong>{item.title}</strong><small>{item.summary}</small></div>)}</div></div>
      </section>}

      {view === "topics" && <section className="content-view">
        <div className="section-heading"><div><span className="eyebrow">创意库</span><h2>所有备选选题</h2><p>长期选题 {data.counts.longTerm} 条，广交会专题 {data.counts.cantonFair} 条。选择一条查看为什么值得做。</p></div></div>
        <div className="toolbar"><label className="searchbox"><Search size={16} /><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="搜索问题、场景或编号" /></label><div className="filter-group">{["全部", "广交会专题", "长期选题"].map((item) => <Button key={item} size="sm" variant={collection === item ? "secondary" : "ghost"} onClick={() => setCollection(item)}>{item}</Button>)}</div></div>
        <div className="topic-layout"><div className="topic-table"><div className="table-head"><span>选题</span><span>内容角度</span><span>进度</span></div>{filtered.map((topic) => <button className={cn("topic-row", selected.id === topic.id && "selected")} key={topic.id} onClick={() => setInspectedTopic(topic)}><span className="topic-name"><em>{topic.id}</em><strong>{topic.title}</strong><small>{topic.pillar}</small></span><span className="topic-angle">{topic.angle}</span><span className="topic-status">{topic.status === "needs_input" ? <Badge variant="warning">需要你</Badge> : <Badge variant="outline">待推进</Badge>}</span></button>)}</div>
          <aside className="topic-inspector"><span className="eyebrow">{selected.id} · {selected.collection}</span><h3>{selected.title}</h3><p>{selected.angle}</p><dl><div><dt>需要证明</dt><dd>{selected.proof}</dd></div><div><dt>优先平台</dt><dd>{selected.platforms.join(" · ")}</dd></div><div><dt>下一步</dt><dd>{selected.next_action}</dd></div></dl><Button className="w-full" onClick={copyPrompt}>{copied ? <Check size={16} /> : <Clipboard size={16} />}{copied ? "已复制续接提示" : "复制到 Codex 继续"}</Button></aside>
        </div>
      </section>}

      {view === "content" && <section className="content-view">
        <div className="section-heading"><div><span className="eyebrow">选题之后的实际产物</span><h2>创作成果</h2><p>先选一条创作任务，再查看它的母脚本、文章和渠道版本。</p></div><Badge variant="outline">{data.contentProjects.length} 条已创作</Badge></div>
        <div className="selected-project-bar">
          <div className="selected-project-id">{selectedContentProject.topic.id}</div>
          <div className="selected-project-copy"><span>{selectedContentProject.topic.collection} · {selectedContentProject.topic.pillar}</span><strong>{selectedContentProject.topic.title}</strong></div>
          <div className="project-combobox">
            <span>切换创作成果</span>
            <button className="project-combobox-trigger" type="button" aria-haspopup="listbox" aria-expanded={contentPickerOpen} onClick={() => setContentPickerOpen((open) => !open)}><span>{selectedContentProject.topic.id} · {selectedContentProject.topic.title}</span><Search size={14} /></button>
            {contentPickerOpen && <div className="project-combobox-popover"><label><Search size={15} /><input autoFocus value={contentQuery} onChange={(event) => setContentQuery(event.target.value)} onKeyDown={(event) => { if (event.key === "Escape") setContentPickerOpen(false); }} placeholder="搜索编号、标题或内容角度" /></label><div className="project-combobox-list" role="listbox" aria-label="创作成果搜索结果">{filteredContentProjects.length > 0 ? filteredContentProjects.map((project) => <button type="button" role="option" aria-selected={project.topic.id === selectedContentProject.topic.id} key={project.topic.id} onClick={() => openCreatedTopic(project.topic.id)}><em>{project.topic.id}</em><span><strong>{project.topic.title}</strong><small>{project.topic.collection} · {project.topic.pillar} · {project.deliverables.length} 份成果</small></span>{project.topic.id === selectedContentProject.topic.id && <Check size={14} />}</button>) : <p>没有匹配的已创作选题</p>}</div></div>}
            <small>{selectedContentProject.deliverables.length} 份可查看成果</small>
          </div>
        </div>
        <div className="creation-layout"><div className="creation-list"><div className="rail-label">选择版本</div>{selectedContentProject.deliverables.map((item) => <button className={cn("creation-item", selectedDeliverable.id === item.id && "active")} key={item.id} onClick={() => setSelectedDeliverableId(item.id)}><span>{item.channel}</span><strong>{item.kind}</strong><small>{item.summary}</small><StatusBadge status={item.status} /></button>)}</div><article className="creation-preview"><div className="preview-head"><div><span className="eyebrow">{selectedContentProject.topic.id} · {selectedDeliverable.channel} · {selectedDeliverable.kind}</span><h3>{selectedDeliverable.title}</h3><small>{selectedDeliverable.path}</small></div><StatusBadge status={selectedDeliverable.status} /></div><ReadableMarkdown content={selectedDeliverable.content} /></article></div>
      </section>}

      {view === "facts" && <section className="content-view">
        <div className="section-heading"><div><span className="eyebrow">可审计的创作上下文</span><h2>事实基础</h2><p>每个对象都是一个带来源、文本、图片、视频和审核结果的文件夹。缺少真实证据时，系统会明确停住。</p></div>{factPack && <StatusBadge status={factPack.gate.creation_ready ? "verified" : "needs_confirmation"} />}</div>
        {factPack && <>
          <div className="fact-pack-head"><div className="pack-identity"><span className="pack-icon"><FolderOpen size={22} /></span><div><span className="eyebrow">{factPack.entity_type} · {factPack.id}</span><h3>{factPack.name}</h3><code>{factPack.path}/</code></div></div><div className="pack-score"><strong>{factPack.gate.completeness}%</strong><span>事实包完整度</span><Progress value={factPack.gate.completeness} /></div></div>
          {nextFactQuestion && <div className="fact-question"><MessageSquareText size={19} /><div><span className="eyebrow">Agent 下一次会问</span><strong>{nextFactQuestion.question}</strong><small>{nextFactQuestion.reason}</small></div><Badge variant="warning">阻塞当前创作</Badge></div>}
          <div className="slot-grid">{factPack.required_slots.map((slot) => { const Icon = slot.kind === "image" ? Image : slot.kind === "video" ? Video : slot.kind === "link" ? Link2 : FileText; return <div className={`slot-card ${slot.status}`} key={slot.id}><div className="slot-top"><Icon size={17} /><StatusBadge status={slot.status} /></div><strong>{slot.label}</strong><small>{slot.note ?? (slot.status === "present" ? "已进入事实包并通过结构校验" : "等待补充")}</small></div>; })}</div>
          <div className="fact-section-heading"><div><h3>可用于创作的原子事实</h3><span>{factPack.facts.filter((fact) => fact.status === "verified").length} 条已核验 · {factPack.facts.filter((fact) => fact.status === "prohibited_claim").length} 条表达禁区</span></div></div>
          <div className="fact-stack">{factPack.facts.map((fact) => <div className="fact-row" key={fact.id}><StatusBadge status={fact.status} /><div><strong>{fact.claim}</strong><small>{fact.category} · {fact.evidence_type} · {fact.source_id}</small></div></div>)}</div>
          <div className="source-panel"><h3>来源与媒体台账</h3><div className="source-grid"><div><span>事实来源</span>{factPack.sources.map((source) => <a key={source.id} href={source.locator.startsWith("http") ? source.locator : undefined} target="_blank" rel="noreferrer"><Link2 size={13} />{source.title}<small>{source.type}</small></a>)}</div><div><span>媒体事实</span>{factPack.media_assets.map((asset) => <div className="asset-row" key={asset.id}>{asset.kind === "image" ? <Image size={14} /> : <Video size={14} />}<p><strong>{asset.purpose}</strong><small>{asset.status === "missing" ? "尚无真实文件，不可用于创作" : "已登记"}</small></p><StatusBadge status={asset.status} /></div>)}</div></div></div>
          {factPack.gate.warnings.length > 0 && <div className="blocked-panel"><CircleAlert size={18} /><div><strong>事实门禁尚未放行</strong>{factPack.gate.warnings.map((item) => <p key={item}>{item.replace("required slot missing: ", "缺失：").replace("required slot partial: ", "待补全：")}</p>)}</div></div>}
        </>}
      </section>}

      {view === "publish" && <section className="content-view">
        <div className="section-heading"><div><span className="eyebrow">三平台发布包</span><h2>还没有到发布</h2><p>事实确认和母内容完成后，系统会在这里生成三个不同任务的版本。</p></div><Badge variant="outline">未就绪</Badge></div>
        <Tabs defaultValue="channels"><TabsList><TabsTrigger value="channels">视频号</TabsTrigger><TabsTrigger value="douyin">抖音</TabsTrigger><TabsTrigger value="xhs">小红书</TabsTrigger></TabsList>{[["channels","视频号","观点、信任和完整解释"],["douyin","抖音","动态证据和快速理解"],["xhs","小红书","搜索、清单和收藏"]].map(([id,name,task]) => <TabsContent value={id} key={id}><div className="empty-package"><Archive size={28} /><h3>{name}版本等待母内容</h3><p>平台任务：{task}。当前不会拿一篇稿子机械改短。</p><span>完成事实锁定后自动开始</span></div></TabsContent>)}</Tabs>
      </section>}
    </main>
  </div>;
}
