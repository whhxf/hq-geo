export type Topic = {
  id: string;
  title: string;
  collection: string;
  pillar: string;
  angle: string;
  proof: string;
  platforms: string[];
  source_status: string;
  stage: string;
  status: string;
  next_action: string;
  progress: number;
  updated_at: string;
  artifacts: string[];
};

export type Fact = {
  id: string;
  claim: string;
  status: "verified" | "needs_confirmation" | "conflict" | "expired" | "prohibited_claim";
  scope: string;
  category?: string;
  evidence_type?: string;
  source_id?: string;
};

export type FactSlot = {
  id: string;
  label: string;
  kind: string;
  status: "present" | "partial" | "missing";
  note?: string;
};

export type FactPack = {
  id: string;
  name: string;
  entity_type: string;
  path: string;
  status: string;
  updated_at: string;
  required_slots: FactSlot[];
  facts: Fact[];
  sources: Array<{ id: string; title: string; locator: string; type: string }>;
  media_assets: Array<{ id: string; kind: string; status: string; purpose: string; path?: string | null; url?: string | null }>;
  pending_questions: Array<{ id: string; question: string; reason: string; status: string; priority: number; blocks: string[] }>;
  gate: { verdict: string; creation_ready: boolean; completeness: number; errors: string[]; warnings: string[] };
};

export type WorkspaceData = {
  idea: {
    id: string;
    title: string;
    summary: string;
    audience: string;
    target_platforms: string[];
    stage: string;
    status: string;
    progress: number;
    selected_topic_id: string;
    next_action: string;
    source_thread_id: string;
    updated_at: string;
    facts: Fact[];
    blocked_by: string[];
  };
  topics: Topic[];
  selectedTopic: Topic;
  events: Array<{ event_id: string; at: string; type: string; summary: string }>;
  quality: { verdict: string; profile: string; passed: number; total: number } | null;
  factPacks: FactPack[];
  deliverables: Array<{ id: string; kind: string; channel: string; title: string; status: string; path: string; summary: string; content: string }>;
  contentProjects: Array<{
    topic: Topic;
    updated_at: string;
    deliverables: Array<{ id: string; kind: string; channel: string; title: string; status: string; path: string; summary: string; content: string }>;
  }>;
  counts: { total: number; longTerm: number; cantonFair: number; needsInput: number };
};
