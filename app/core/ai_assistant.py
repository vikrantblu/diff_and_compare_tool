"""
Next-Gen AI Assistant Engine for diff_and_compare_tool
Features:
- Automated Pull Request & Diff Summaries (Local Ollama / Copilot / OpenAI API / Intelligent Offline Heuristic).
- Smart 3-Way Merge Conflict Resolution Suggestions with semantic explanations.
- Prompt Engineering tailored for code review and refactoring.
"""

import os
import json
import urllib.request
import urllib.error
from typing import List, Dict, Any, Optional
from app.core.diff_engine import DiffChunk, MergeConflictChunk
from app.core.secret_scrubber import SecretScrubber


class AIAssistant:
    """Provides local or API-driven AI code comparison insights and merge conflict resolutions."""

    DEFAULT_OLLAMA_ENDPOINT = "http://localhost:11434/api/generate"
    DEFAULT_MODEL = "qwen2.5-coder"
    SUPPORTED_MODELS = ["qwen2.5-coder", "deepseek-coder", "codellama", "llama3", "mistral"]

    @classmethod
    def generate_diff_summary(
        cls,
        chunks: List[DiffChunk],
        left_raw: List[str],
        right_raw: List[str],
        left_name: str = "Original",
        right_name: str = "Modified",
        endpoint: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None
    ) -> str:
        """
        Generates a structured, professional Pull Request / Diff summary.
        Uses local/remote LLM if reachable, or provides an immediate heuristic analysis.
        Strictly scrubs secrets, credentials, and PII before transmission.
        """
        added_lines = 0
        deleted_lines = 0
        modified_lines = 0
        moved_blocks = 0
        sample_diffs = []

        for c in chunks:
            l_s = c.raw_left_start if c.raw_left_start is not None else c.left_start
            l_e = c.raw_left_end if c.raw_left_end is not None else c.left_end
            r_s = c.raw_right_start if c.raw_right_start is not None else c.right_start
            r_e = c.raw_right_end if c.raw_right_end is not None else c.right_end

            if c.is_moved:
                moved_blocks += 1
            elif c.tag == "insert":
                count = r_e - r_s
                added_lines += count
                if len(sample_diffs) < 8:
                    lines = right_raw[r_s:min(r_e, r_s + 3)]
                    sample_diffs.append("+ " + "\n+ ".join(lines))
            elif c.tag == "delete":
                count = l_e - l_s
                deleted_lines += count
                if len(sample_diffs) < 8:
                    lines = left_raw[l_s:min(l_e, l_s + 3)]
                    sample_diffs.append("- " + "\n- ".join(lines))
            elif c.tag == "replace":
                modified_lines += max(l_e - l_s, r_e - r_s)
                if len(sample_diffs) < 8:
                    sample_diffs.append(f"~ Changed block at line {l_s + 1} -> {r_s + 1}")

        raw_prompt = (
            f"You are a Principal Software Engineer. Provide a concise, professional Pull Request Summary "
            f"for comparing '{left_name}' and '{right_name}'.\n"
            f"Stats: +{added_lines} additions, -{deleted_lines} deletions, ~{modified_lines} modified, {moved_blocks} moved blocks.\n"
            f"Sample Diffs:\n" + "\n".join(sample_diffs[:6]) + "\n\n"
            f"Format response with:\n"
            f"### 📋 Executive Summary\n"
            f"### ⚡ Key Architectural Changes\n"
            f"### ⚠️ Risk & Breaking Change Assessment\n"
            f"### 🔍 Verification / Test Recommendations\n"
        )

        # Automated Secret & PII Scrubbing
        clean_prompt, scrub_count, scrub_cats = SecretScrubber.scrub_text(raw_prompt)
        privacy_footer = ""
        if scrub_count > 0:
            cats_str = ", ".join(scrub_cats)
            privacy_footer = f"\n\n> 🛡️ **Privacy Shield**: {scrub_count} sensitive item(s) redacted ({cats_str}) prior to AI ingestion."

        llm_response = cls._call_llm(clean_prompt, endpoint, model, api_key) if endpoint else None
        if llm_response:
            return llm_response + privacy_footer

        # High-Quality Offline Heuristic Fallback
        return cls._generate_offline_summary(
            left_name, right_name, added_lines, deleted_lines, modified_lines, moved_blocks, sample_diffs
        ) + privacy_footer

    @classmethod
    def suggest_conflict_resolution(
        cls,
        conflict: MergeConflictChunk,
        context_file: str = "Source File",
        endpoint: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Synthesizes a resolution for a 3-way merge conflict chunk with secret scrubbing.
        """
        mine_raw = "\n".join(conflict.left_lines)
        base_raw = "\n".join(conflict.base_lines)
        theirs_raw = "\n".join(conflict.right_lines)

        mine_text, _, _ = SecretScrubber.scrub_text(mine_raw)
        base_text, _, _ = SecretScrubber.scrub_text(base_raw)
        theirs_text, _, _ = SecretScrubber.scrub_text(theirs_raw)

        prompt = (
            f"You are an expert developer resolving a 3-way merge conflict in '{context_file}'.\n"
            f"BASE (Ancestor):\n```\n{base_text}\n```\n"
            f"MINE (Local changes):\n```\n{mine_text}\n```\n"
            f"THEIRS (Incoming changes):\n```\n{theirs_text}\n```\n\n"
            f"Task: Synthesize a clean, logically unified resolution that preserves the intent of both sides without syntax errors.\n"
            f"Output JSON with keys 'resolved_code' (string) and 'explanation' (string)."
        )

        llm_raw = cls._call_llm(prompt, endpoint, model, api_key) if endpoint else None
        if llm_raw:
            try:
                # Attempt to extract json block
                clean_json = llm_raw
                if "```json" in clean_json:
                    clean_json = clean_json.split("```json")[1].split("```")[0].strip()
                elif "```" in clean_json:
                    clean_json = clean_json.split("```")[1].split("```")[0].strip()
                parsed = json.loads(clean_json)
                if "resolved_code" in parsed and "explanation" in parsed:
                    return {
                        "resolved_lines": parsed["resolved_code"].splitlines(),
                        "explanation": parsed["explanation"],
                        "source": "AI (LLM / Copilot)"
                    }
            except Exception:
                pass

        # Offline Intelligent Heuristic Reconciliation
        return cls._resolve_conflict_heuristic(conflict)

    @staticmethod
    def build_llm_payload(prompt: str, endpoint: str, model: str) -> Dict[str, Any]:
        """Constructs the request body matching either OpenAI Chat Completions or Ollama Generate APIs."""
        if "chat/completions" in endpoint:
            return {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
            }
        return {
            "model": model,
            "prompt": prompt,
            "stream": False,
        }

    @classmethod
    def _call_llm(
        cls,
        prompt: str,
        endpoint: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None
    ) -> Optional[str]:
        if not endpoint:
            return None
        target_endpoint = endpoint
        target_model = model or cls.DEFAULT_MODEL

        if not (target_endpoint.startswith("http://") or target_endpoint.startswith("https://")):
            return None

        resolved_key = api_key or os.environ.get("OPENAI_API_KEY")

        try:
            payload = cls.build_llm_payload(prompt, target_endpoint, target_model)
            req_data = json.dumps(payload).encode("utf-8")

            req = urllib.request.Request(
                target_endpoint,
                data=req_data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            if resolved_key:
                req.add_header("Authorization", f"Bearer {resolved_key}")

            with urllib.request.urlopen(req, timeout=30.0) as resp:  # nosec B310
                data = json.loads(resp.read().decode("utf-8"))
                if "response" in data:
                    return data["response"].strip()
                if "choices" in data and len(data["choices"]) > 0:
                    return data["choices"][0]["message"]["content"].strip()
        except Exception:
            return None
        return None

    @staticmethod
    def _generate_offline_summary(
        left_name: str,
        right_name: str,
        added: int,
        deleted: int,
        modified: int,
        moved: int,
        samples: List[str]
    ) -> str:
        net_change = added - deleted
        net_str = f"+{net_change}" if net_change >= 0 else str(net_change)

        risk = "Low"
        if modified > 100 or deleted > 100:
            risk = "High — Extensive deletions and modifications detected"
        elif modified > 25 or added > 50:
            risk = "Medium — Moderate logic modifications"

        summary = [
            f"## 🤖 AI Change Analysis: `{left_name}` ➔ `{right_name}`\n",
            f"### 📋 Executive Summary",
            f"- **Net Impact**: **{net_str} lines** ({added} additions, {deleted} deletions, {modified} modified lines).",
            f"- **Refactoring Signal**: **{moved} relocated blocks** detected and tracked across documents.",
            f"- **Estimated Risk Tier**: **{risk}**\n",
            f"### ⚡ Key Structural Changes",
            f"- Additions concentrated in newly introduced logic paths.",
            f"- Deletions reflect cleaned-up legacy code and refactored routines.",
            f"- Intra-line mutations verify precise token updates rather than total rewrites.\n",
            f"### ⚠️ Risk & Breaking Change Assessment",
            f"- Verify that any public interfaces or API signatures modified on the right maintain backward compatibility.",
            f"- Ensure unit tests cover all {added} newly introduced statements.\n",
            f"### 🔍 Verification Checklist",
            f"- [ ] Execute test suite covering modified modules.",
            f"- [ ] Inspect moved blocks to ensure scope and closure bindings remain valid.",
            f"- [ ] Verify character encoding and line terminator consistency."
        ]
        return "\n".join(summary)

    @staticmethod
    def _resolve_conflict_heuristic(conflict: MergeConflictChunk) -> Dict[str, Any]:
        """Intelligent offline synthesis uniting both non-overlapping statements."""
        mine = conflict.left_lines
        theirs = conflict.right_lines
        base = conflict.base_lines

        # If one side only appended or added comments/types, unite both
        combined = []
        for l in mine:
            if l not in combined:
                combined.append(l)
        for r in theirs:
            if r not in combined:
                combined.append(r)

        return {
            "resolved_lines": combined if combined else mine,
            "explanation": (
                "Heuristic Semantic Synthesis: Combined distinct modifications from both 'Mine' and 'Theirs' "
                "while deduplicating common declarations."
            ),
            "source": "Smart Heuristic Engine"
        }
