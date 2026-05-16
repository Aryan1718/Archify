"""Markdown report renderer for Phase 4."""

from __future__ import annotations

from datetime import date
from typing import Any


def render_report(
    *,
    graph: dict[str, Any],
    analysis: dict[str, Any],
    detection: dict[str, Any],
    extraction_summary: dict[str, Any],
    target_path: str,
) -> str:
    today = date.today().isoformat()
    summary = graph.get("summary", {})
    ambiguity = analysis.get("ambiguitySummary", {})
    communities = analysis.get("communitySummary", {})
    gaps = analysis.get("knowledgeGaps", {})

    total_edges = max(int(summary.get("edgeCount", 0)), 1)
    ambiguous_edge_count = int(ambiguity.get("ambiguousEdgeCount", 0))
    ambiguous_pct = round((ambiguous_edge_count / total_edges) * 100)

    lines = [
        f"# Graph Report - {target_path} ({today})",
        "",
        "## Corpus Check",
    ]

    if detection.get("warning"):
        lines.append(f"- {detection['warning']}")
    else:
        totals = detection.get("totals", {})
        lines.append(f"- {totals.get('files', 0)} files scanned")
        lines.append(f"- {extraction_summary.get('extractedFiles', 0)} code files contributed grounded graph fragments")
        lines.append("- Verdict: graph analysis is available without LLM synthesis.")

    lines.extend(
        [
            "",
            "## Summary",
            f"- {summary.get('nodeCount', 0)} nodes · {summary.get('edgeCount', 0)} edges · {communities.get('communityCount', 0)} communities",
            f"- Warnings: {summary.get('warningCount', 0)} · Ambiguous edges: {ambiguous_edge_count} ({ambiguous_pct}%)",
            f"- Top hubs: {len(analysis.get('godNodes', []))} · Surprises: {len(analysis.get('surprisingConnections', []))} · Suggested questions: {len(analysis.get('suggestedQuestions', []))}",
        ]
    )

    lines.extend(["", "## God Nodes"])
    if analysis.get("godNodes"):
        for index, node in enumerate(analysis["godNodes"], start=1):
            lines.append(
                f"{index}. `{node['label']}` - degree {node['degree']} · community {node.get('community', 'unknown')} · {node.get('sourceFile', '')}"
            )
    else:
        lines.append("- No grounded hub nodes were strong enough to rank.")

    lines.extend(["", "## Surprising Connections"])
    if analysis.get("surprisingConnections"):
        for item in analysis["surprisingConnections"]:
            lines.append(
                f"- `{item['source']}` --{item['relation']}--> `{item['target']}` [{item['confidence']}]"
            )
            lines.append(f"  {item['sourceFiles'][0]} -> {item['sourceFiles'][1]} · {item['why']}")
    else:
        lines.append("- No cross-boundary or non-obvious grounded links were detected.")

    lines.extend(["", f"## Communities ({communities.get('communityCount', 0)} total)"])
    if communities.get("communities"):
        for community in communities["communities"]:
            labels = ", ".join(community.get("sampleLabels", [])) or "no non-file members"
            lines.append(
                f"- Community {community['id']}: {community['size']} nodes · cohesion {community['cohesion']} · {labels}"
            )
    else:
        lines.append("- No communities were produced.")

    lines.extend(["", "## Ambiguous Edges"])
    if ambiguity.get("samples"):
        for sample in ambiguity["samples"]:
            lines.append(
                f"- `{sample['source']}` -> `{sample['target']}` · relation `{sample['relation']}` · {sample['sourceFile']}"
            )
    else:
        lines.append("- No ambiguous edges were recorded.")

    lines.extend(["", "## Knowledge Gaps"])
    lines.append(
        f"- Isolated grounded nodes: {gaps.get('isolatedNodeCount', 0)}"
    )
    if gaps.get("thinCommunities"):
        lines.append(f"- Thin communities: {', '.join(str(value) for value in gaps['thinCommunities'])}")
    else:
        lines.append("- Thin communities: none")
    if gaps.get("isolatedNodes"):
        labels = ", ".join(f"`{item['label']}`" for item in gaps["isolatedNodes"][:5])
        lines.append(f"- Sample isolated nodes: {labels}")

    lines.extend(["", "## Suggested Questions"])
    for item in analysis.get("suggestedQuestions", []):
        lines.append(f"- **{item['question']}**")
        lines.append(f"  {item['why']}")

    return "\n".join(lines) + "\n"
