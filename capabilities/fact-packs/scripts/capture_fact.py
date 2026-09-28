#!/usr/bin/env python3
"""Record a user's answer as an auditable fact and resolve its source question.

事实包在**项目根**的 `facts/`，这个脚本在系统根。--pack 相对项目根解释。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

_SYSTEM = next((p for p in Path(__file__).resolve().parents if (p / "project.py").is_file()), None)
if _SYSTEM is None:
    raise SystemExit("这个脚本只能在 hq-geo 系统根里运行（向上找不到 project.py）")
sys.path.insert(0, str(_SYSTEM))
from project import find_project  # noqa: E402

ALLOWED_OWNER_CATEGORIES = {"founder_viewpoint", "firsthand_experience", "internal_process", "product_intent"}


def capture(pack: Path, *, question_id: str, fact_id: str, claim: str, answer: str, category: str, scope: str = "feature", status: str = "verified") -> dict:
    if category not in ALLOWED_OWNER_CATEGORIES:
        raise ValueError(f"invalid owner statement category: {category}")
    manifest_path = pack / "manifest.json"
    facts_path = pack / "facts.jsonl"
    log_path = pack / "reviews" / "change-log.jsonl"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    facts = [json.loads(line) for line in facts_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if any(item.get("id") == fact_id for item in facts):
        raise ValueError(f"fact id already exists: {fact_id}")
    question = next((item for item in manifest.get("pending_questions", []) if item.get("id") == question_id), None)
    if not question:
        raise ValueError(f"question not found: {question_id}")
    if question.get("status") != "pending":
        raise ValueError(f"question is not pending: {question_id}")
    if question.get("answer_policy") != "owner_statement":
        raise ValueError("this tool only captures owner_statement questions")

    now = datetime.now().astimezone().isoformat(timespec="seconds")
    fact = {
        "id": fact_id,
        "claim": claim,
        "category": category,
        "evidence_type": "owner_statement",
        "status": status,
        "source_id": "src-owner-dialogue",
        "source_locator": f"reviews/change-log.jsonl#{question_id}",
        "verified_at": now if status == "verified" else None,
        "scope": scope,
    }
    if not any(source.get("id") == "src-owner-dialogue" for source in manifest.get("sources", [])):
        manifest.setdefault("sources", []).append({
            "id": "src-owner-dialogue",
            "type": "owner_dialogue",
            "title": "Conan 与 Agent 的事实确认对话",
            "locator": "reviews/change-log.jsonl",
            "accessed_at": now[:10],
        })
    question["status"] = "resolved"
    question["resolved_at"] = now
    question.setdefault("result_fact_ids", []).append(fact_id)
    if status == "verified":
        manifest.setdefault("protected_fact_ids", []).append(fact_id)
    manifest["updated_at"] = now[:10]
    change = {
        "event": "fact_captured_from_dialogue",
        "at": now,
        "actor": "owner_via_agent",
        "question_id": question_id,
        "question": question["question"],
        "answer_original": answer,
        "fact_id": fact_id,
        "claim": claim,
        "status": status,
    }

    facts_path.write_text(facts_path.read_text(encoding="utf-8").rstrip() + "\n" + json.dumps(fact, ensure_ascii=False) + "\n", encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(change, ensure_ascii=False) + "\n")
    return {"captured": fact_id, "resolved": question_id, "status": status}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pack", required=True)
    parser.add_argument("--question-id", required=True)
    parser.add_argument("--fact-id", required=True)
    parser.add_argument("--claim", required=True, help="Structured atomic statement")
    parser.add_argument("--answer", required=True, help="User's original answer")
    parser.add_argument("--category", required=True, choices=sorted(ALLOWED_OWNER_CATEGORIES))
    parser.add_argument("--scope", default="feature")
    parser.add_argument("--status", choices=("verified", "conflict"), default="verified")
    args = parser.parse_args()
    project = find_project()
    pack = (project / args.pack).resolve()
    if project not in pack.parents:
        raise SystemExit("pack must stay inside project root")
    try:
        result = capture(pack, question_id=args.question_id, fact_id=args.fact_id, claim=args.claim, answer=args.answer, category=args.category, scope=args.scope, status=args.status)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
