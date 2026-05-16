"""Deterministic community assignment for Phase 3."""

from __future__ import annotations

import inspect
from collections import defaultdict, deque
from typing import Any


_MAX_COMMUNITY_FRACTION = 0.25
_MIN_SPLIT_SIZE = 10
_COHESION_SPLIT_THRESHOLD = 0.05
_COHESION_SPLIT_MIN_SIZE = 50


def _build_adjacency(graph: dict[str, Any]) -> dict[str, set[str]]:
    adjacency = {node["id"]: set() for node in graph.get("nodes", [])}
    for edge in graph.get("edges", []):
        source = edge["source"]
        target = edge["target"]
        if source not in adjacency or target not in adjacency:
            continue
        adjacency[source].add(target)
        adjacency[target].add(source)
    return adjacency


def _connected_components(adjacency: dict[str, set[str]], nodes: list[str]) -> list[list[str]]:
    remaining = set(nodes)
    components: list[list[str]] = []
    while remaining:
        start = min(remaining)
        queue = deque([start])
        remaining.remove(start)
        component = [start]
        while queue:
            node = queue.popleft()
            for neighbor in sorted(adjacency.get(node, ())):
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    queue.append(neighbor)
                    component.append(neighbor)
        components.append(sorted(component))
    return components


def _chunk_nodes(nodes: list[str], size: int) -> list[list[str]]:
    ordered = sorted(nodes)
    return [ordered[index:index + size] for index in range(0, len(ordered), size)]


def _split_community(nodes: list[str], node_index: dict[str, dict[str, Any]], max_size: int) -> list[list[str]]:
    by_source: dict[str, list[str]] = defaultdict(list)
    for node_id in nodes:
        by_source[node_index[node_id].get("source_file", "")].append(node_id)
    source_groups = [sorted(group) for _, group in sorted(by_source.items()) if group]
    if len(source_groups) > 1 and len(source_groups) < len(nodes):
        return source_groups

    by_kind: dict[str, list[str]] = defaultdict(list)
    for node_id in nodes:
        by_kind[node_index[node_id].get("kind", "")].append(node_id)
    kind_groups = [sorted(group) for _, group in sorted(by_kind.items()) if group]
    if len(kind_groups) > 1 and len(kind_groups) < len(nodes):
        return kind_groups

    return _chunk_nodes(nodes, max_size)


def _cohesion_score(adjacency: dict[str, set[str]], nodes: list[str]) -> float:
    if len(nodes) <= 1:
        return 1.0
    node_set = set(nodes)
    actual = 0
    for node in nodes:
        actual += sum(1 for neighbor in adjacency.get(node, ()) if neighbor in node_set)
    actual //= 2
    possible = len(nodes) * (len(nodes) - 1) / 2
    if possible == 0:
        return 0.0
    return round(actual / possible, 2)


def _partition_with_leiden(adjacency: dict[str, set[str]]) -> list[list[str]] | None:
    try:
        import igraph  # type: ignore
        import leidenalg  # type: ignore
    except ImportError:
        return None

    ordered_nodes = sorted(adjacency)
    graph = igraph.Graph()
    graph.add_vertices(ordered_nodes)
    edges = []
    for node in ordered_nodes:
        for neighbor in sorted(adjacency[node]):
            if node < neighbor:
                edges.append((node, neighbor))
    graph.add_edges(edges)
    if not edges:
        return [[node] for node in ordered_nodes]
    partition = leidenalg.find_partition(graph, leidenalg.ModularityVertexPartition)
    communities = [[ordered_nodes[index] for index in membership] for membership in partition]
    return [sorted(nodes) for nodes in communities]


def _partition_with_networkx(adjacency: dict[str, set[str]]) -> list[list[str]] | None:
    try:
        import networkx as nx  # type: ignore
    except ImportError:
        return None

    graph = nx.Graph()
    for node in sorted(adjacency):
        graph.add_node(node)
    for node in sorted(adjacency):
        for neighbor in sorted(adjacency[node]):
            if node < neighbor:
                graph.add_edge(node, neighbor)

    if graph.number_of_edges() == 0:
        return [[node] for node in sorted(graph.nodes())]

    kwargs: dict[str, Any] = {"seed": 42, "threshold": 1e-4}
    if "max_level" in inspect.signature(nx.community.louvain_communities).parameters:
        kwargs["max_level"] = 10
    communities = nx.community.louvain_communities(graph, **kwargs)
    return [sorted(community) for community in communities]


def cluster_graph(graph: dict[str, Any]) -> dict[str, Any]:
    adjacency = _build_adjacency(graph)
    node_ids = sorted(adjacency)
    node_index = {node["id"]: dict(node) for node in graph.get("nodes", [])}
    total_nodes = len(node_ids)

    if not node_ids:
        return {
            **graph,
            "nodes": [],
            "communities": {},
            "clustering": {
                "backend": "none",
                "usedFallback": True,
                "communityCount": 0,
                "isolateCount": 0,
            },
        }

    isolates = [node_id for node_id in node_ids if not adjacency[node_id]]
    connected_nodes = [node_id for node_id in node_ids if adjacency[node_id]]

    backend = "deterministic_components"
    raw_communities: list[list[str]] = []
    if connected_nodes:
        connected_adjacency = {node_id: adjacency[node_id] for node_id in connected_nodes}
        leiden = _partition_with_leiden(connected_adjacency)
        if leiden is not None:
            backend = "leiden"
            raw_communities.extend(leiden)
        else:
            louvain = _partition_with_networkx(connected_adjacency)
            if louvain is not None:
                backend = "networkx_louvain"
                raw_communities.extend(louvain)
            else:
                raw_communities.extend(_connected_components(adjacency, connected_nodes))
    raw_communities.extend([[node_id] for node_id in isolates])

    max_size = max(_MIN_SPLIT_SIZE, int(total_nodes * _MAX_COMMUNITY_FRACTION))
    split_once: list[list[str]] = []
    for community in raw_communities:
        if len(community) > max_size:
            split_once.extend(_split_community(community, node_index, max_size))
        else:
            split_once.append(sorted(community))

    final_communities: list[list[str]] = []
    for community in split_once:
        if len(community) >= _COHESION_SPLIT_MIN_SIZE and _cohesion_score(adjacency, community) < _COHESION_SPLIT_THRESHOLD:
            final_communities.extend(_split_community(community, node_index, max_size))
        else:
            final_communities.append(sorted(community))

    final_communities = [sorted(community) for community in final_communities if community]
    final_communities.sort(key=lambda nodes: (-len(nodes), nodes))

    community_map: dict[int, list[str]] = {index: community for index, community in enumerate(final_communities)}
    node_to_community = {
        node_id: community_id
        for community_id, members in community_map.items()
        for node_id in members
    }

    clustered_nodes: list[dict[str, Any]] = []
    for node in graph.get("nodes", []):
        clustered = dict(node)
        clustered["community"] = node_to_community[node["id"]]
        clustered_nodes.append(clustered)

    communities_payload = {
        str(community_id): {
            "id": community_id,
            "size": len(members),
            "nodes": members,
            "cohesion": _cohesion_score(adjacency, members),
        }
        for community_id, members in community_map.items()
    }

    return {
        **graph,
        "nodes": clustered_nodes,
        "communities": communities_payload,
        "clustering": {
            "backend": backend,
            "usedFallback": backend not in {"leiden", "networkx_louvain"},
            "communityCount": len(community_map),
            "isolateCount": len(isolates),
            "maxCommunitySize": max((len(members) for members in community_map.values()), default=0),
        },
    }
