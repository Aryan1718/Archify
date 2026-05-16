import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from archify_engine.build import build_graph
from archify_engine.cluster import cluster_graph
from archify_engine.config import normalize_config
from archify_engine.dedup import deduplicate_graph
from archify_engine.analyze import analyze_graph
from archify_engine.architecture_context import build_architecture_context
from archify_engine.engine import analyze


class BuildGraphTests(unittest.TestCase):
    def test_build_is_stable_and_skips_dangling_edges(self) -> None:
        extraction = {
            "nodes": [
                {"id": "file_src_app_py", "label": "src\\app.py", "file_type": "code", "source_file": "src\\app.py", "kind": "file"},
                {"id": "symbol_src_app_py_function_run", "label": "run()", "file_type": "code", "source_file": "src\\app.py", "kind": "function"},
            ],
            "edges": [
                {"source": "file_src_app_py", "target": "symbol_src_app_py_function_run", "relation": "contains", "confidence": "EXTRACTED", "source_file": "src\\app.py"},
                {"from": "file_src_app_py", "to": "missing_node", "relation": "imports", "confidence": "AMBIGUOUS", "source_file": "src\\app.py"},
            ],
            "hyperedges": [{"id": "h1", "nodes": ["file_src_app_py", "symbol_src_app_py_function_run"]}],
        }

        first = build_graph(extraction)
        second = build_graph(extraction)

        self.assertEqual(first["summary"]["nodeCount"], second["summary"]["nodeCount"])
        self.assertEqual(first["summary"]["edgeCount"], second["summary"]["edgeCount"])
        self.assertEqual(first["edges"][0]["source"], "file_src_app_py")
        self.assertEqual(first["edges"][0]["target"], "symbol_src_app_py_function_run")
        self.assertTrue(first["edges"][0]["directed"])
        self.assertEqual(first["hyperedges"], extraction["hyperedges"])
        self.assertEqual(first["summary"]["danglingEdgeCount"], 1)
        self.assertEqual(first["nodes"][0]["source_file"], "src/app.py")


class DedupGraphTests(unittest.TestCase):
    def test_dedup_collapses_duplicate_ids_and_compatible_labels(self) -> None:
        graph = {
            "nodes": [
                {"id": "a", "label": "Users", "file_type": "concept", "source_file": "db/one.sql", "kind": "sql_table"},
                {"id": "a", "label": "Users", "file_type": "concept", "source_file": "db/one.sql", "kind": "sql_table", "language": "sql"},
                {"id": "b", "label": "users", "file_type": "concept", "source_file": "db/two.sql", "kind": "sql_table"},
                {"id": "c", "label": "users", "file_type": "concept", "source_file": "src/app.py", "kind": "sql_table"},
            ],
            "edges": [
                {"source": "a", "target": "b", "relation": "references", "confidence": "EXTRACTED", "source_file": "db/one.sql"},
                {"source": "b", "target": "a", "relation": "references", "confidence": "EXTRACTED", "source_file": "db/two.sql"},
                {"source": "a", "target": "b", "relation": "references", "confidence": "EXTRACTED", "source_file": "db/one.sql"},
                {"source": "b", "target": "b", "relation": "references", "confidence": "EXTRACTED", "source_file": "db/two.sql"},
            ],
            "hyperedges": [],
            "warnings": [],
        }

        deduped = deduplicate_graph(graph)

        self.assertEqual([node["id"] for node in deduped["nodes"]], ["a", "c"])
        self.assertEqual(len(deduped["edges"]), 0)
        self.assertEqual(deduped["dedup"]["duplicateNodeIdCount"], 1)
        self.assertEqual(deduped["dedup"]["mergedLabelGroupCount"], 1)
        self.assertEqual(deduped["dedup"]["duplicateEdgeCount"], 0)
        self.assertEqual(deduped["dedup"]["droppedSelfLoopCount"], 4)


class ClusterGraphTests(unittest.TestCase):
    def test_cluster_empty_graph(self) -> None:
        clustered = cluster_graph({"nodes": [], "edges": [], "hyperedges": [], "warnings": []})
        self.assertEqual(clustered["communities"], {})
        self.assertEqual(clustered["clustering"]["communityCount"], 0)

    def test_cluster_assigns_isolates_and_stable_order(self) -> None:
        graph = {
            "nodes": [
                {"id": "n1", "label": "n1", "file_type": "code", "source_file": "src/a.py", "kind": "file"},
                {"id": "n2", "label": "n2", "file_type": "code", "source_file": "src/b.py", "kind": "file"},
                {"id": "n3", "label": "n3", "file_type": "code", "source_file": "src/c.py", "kind": "file"},
            ],
            "edges": [],
            "hyperedges": [],
            "warnings": [],
        }

        clustered = cluster_graph(graph)

        self.assertEqual(clustered["communities"]["0"]["nodes"], ["n1"])
        self.assertEqual(clustered["communities"]["1"]["nodes"], ["n2"])
        self.assertEqual(clustered["communities"]["2"]["nodes"], ["n3"])

    def test_cluster_directed_graph_uses_fallback_when_backends_missing(self) -> None:
        graph = {
            "nodes": [
                {"id": "n1", "label": "n1", "file_type": "code", "source_file": "src/a.py", "kind": "file"},
                {"id": "n2", "label": "n2", "file_type": "code", "source_file": "src/a.py", "kind": "function"},
                {"id": "n3", "label": "n3", "file_type": "code", "source_file": "src/b.py", "kind": "function"},
            ],
            "edges": [
                {"source": "n1", "target": "n2", "relation": "contains", "confidence": "EXTRACTED", "source_file": "src/a.py", "directed": True},
                {"source": "n2", "target": "n3", "relation": "calls", "confidence": "INFERRED", "source_file": "src/a.py", "directed": True},
            ],
            "hyperedges": [],
            "warnings": [],
        }

        with mock.patch("archify_engine.cluster._partition_with_leiden", return_value=None), mock.patch(
            "archify_engine.cluster._partition_with_networkx", return_value=None
        ):
            clustered = cluster_graph(graph)

        self.assertEqual(clustered["clustering"]["backend"], "deterministic_components")
        self.assertEqual(clustered["clustering"]["communityCount"], 1)
        self.assertTrue(all("community" in node for node in clustered["nodes"]))


class EngineIntegrationTests(unittest.TestCase):
    def test_analyze_writes_phase4_graph_and_stable_counts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "db").mkdir()
            (root / "src" / "util.py").write_text("def helper():\n    return 1\n", encoding="utf8")
            (root / "src" / "app.py").write_text(
                "from util import helper\n\n\ndef run():\n    return helper()\n",
                encoding="utf8",
            )
            (root / "db" / "001_init.sql").write_text("create table users(id int primary key);\nselect * from users;\n", encoding="utf8")
            (root / "archify.config.json").write_text(json.dumps({"defaults": {"outputDir": ".archify"}}), encoding="utf8")

            config = normalize_config(str(root), str(root), {"defaults": {"outputDir": ".archify"}})
            first = analyze(str(root), config)
            second = analyze(str(root), config)

            graph = json.loads((root / ".archify" / "graph.json").read_text(encoding="utf8"))
            facts = json.loads((root / ".archify" / "facts.json").read_text(encoding="utf8"))
            manifest = json.loads((root / ".archify" / "manifest.json").read_text(encoding="utf8"))
            report = (root / ".archify" / "GRAPH_REPORT.md").read_text(encoding="utf8")
            architecture_context = json.loads((root / ".archify" / "architecture-context.json").read_text(encoding="utf8"))
            architecture_markdown = (root / ".archify" / "architecture-context.md").read_text(encoding="utf8")
            modules = json.loads((root / ".archify" / "modules.json").read_text(encoding="utf8"))
            routes = json.loads((root / ".archify" / "routes.json").read_text(encoding="utf8"))
            database = json.loads((root / ".archify" / "database.json").read_text(encoding="utf8"))
            services = json.loads((root / ".archify" / "services.json").read_text(encoding="utf8"))
            dependencies = json.loads((root / ".archify" / "dependencies.json").read_text(encoding="utf8"))
            docs_summary = json.loads((root / ".archify" / "docs-summary.json").read_text(encoding="utf8"))

            self.assertEqual(graph["status"], "ready")
            self.assertEqual(graph["phase"], "analyze")
            self.assertEqual(first["mode"], "full")
            self.assertEqual(second["mode"], "incremental")
            self.assertIsNone(second["fallbackReason"])
            self.assertEqual(second["changedFileCount"], 0)
            self.assertEqual(second["deletedFileCount"], 0)
            self.assertGreaterEqual(second["reusedFileCount"], 1)
            self.assertEqual(graph["summary"]["communityCount"], first["communityCount"])
            self.assertEqual(graph["dedup"]["duplicateNodeCount"], first["deduplicatedNodeCount"])
            self.assertIn("communities", graph)
            self.assertIn("analysis", graph)
            self.assertTrue(all("community" in node for node in graph["nodes"]))
            self.assertEqual(facts["graphSummary"]["nodeCount"], graph["summary"]["nodeCount"])
            self.assertEqual(facts["phase"], "analyze")
            self.assertIn("analysis", facts)
            self.assertIn("confirmedFindings", facts)
            self.assertIn("inferredFindings", facts)
            self.assertGreaterEqual(len(facts["confirmedFindings"]), 1)
            self.assertTrue(all(item["evidence"] for item in facts["confirmedFindings"]))
            self.assertEqual(manifest["graphSummary"]["communityCount"], graph["summary"]["communityCount"])
            self.assertEqual(manifest["phase"], "analyze")
            self.assertIn("analysisSummary", manifest)
            self.assertIn("architectureContextSummary", manifest)
            self.assertEqual(first["nodeCount"], second["nodeCount"])
            self.assertEqual(first["communityCount"], second["communityCount"])
            self.assertEqual(sorted(graph["communities"]), sorted(json.loads((root / ".archify" / "graph.json").read_text(encoding="utf8"))["communities"]))
            self.assertIn("architectureContextSummary", first)
            self.assertEqual(first["architectureContextSummary"], second["architectureContextSummary"])
            self.assertIn("## God Nodes", report)
            self.assertIn("## Suggested Questions", report)
            self.assertIn("system", architecture_context)
            self.assertIn("subsystems", architecture_context)
            self.assertIn("interfaces", architecture_context)
            self.assertIn("data_flows", architecture_context)
            self.assertIn("cross_cutting_concerns", architecture_context)
            self.assertIn("key_entrypoints", architecture_context)
            self.assertIn("external_dependencies", architecture_context)
            self.assertIn("evidence", architecture_context)
            self.assertIn("open_questions", architecture_context)
            self.assertGreaterEqual(len(architecture_context["subsystems"]), 1)
            self.assertEqual(
                architecture_context,
                json.loads((root / ".archify" / "architecture-context.json").read_text(encoding="utf8")),
            )
            self.assertIn("## System", architecture_markdown)
            self.assertIn("## Subsystem Inventory", architecture_markdown)
            self.assertIn("## Interfaces", architecture_markdown)
            self.assertIn("## Key Flows", architecture_markdown)
            self.assertIn("## Open Questions", architecture_markdown)
            self.assertEqual(modules["status"], "ready")
            self.assertGreaterEqual(len(modules["modules"]), 1)
            self.assertTrue(all(item["evidence"] for item in modules["modules"]))
            self.assertEqual(routes["status"], "ready")
            self.assertIn("confirmedRoutes", routes)
            self.assertIn("inferredRoutes", routes)
            self.assertEqual(database["status"], "ready")
            self.assertGreaterEqual(database["summary"]["tableCount"], 1)
            self.assertEqual(services["status"], "ready")
            self.assertGreaterEqual(len(services["services"]), 1)
            self.assertEqual(dependencies["status"], "ready")
            self.assertIn("internalDependencies", dependencies)
            self.assertEqual(docs_summary["status"], "ready")
            self.assertIn("detectedDocs", docs_summary)
            self.assertIn("readmeLikeDocs", docs_summary["confirmedFacts"])

    def test_analyze_incremental_updates_only_changed_code_and_prunes_deleted_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "util.py").write_text("def helper():\n    return 1\n", encoding="utf8")
            (root / "src" / "app.py").write_text("from util import helper\n\ndef run():\n    return helper()\n", encoding="utf8")

            config = normalize_config(str(root), str(root), {"defaults": {"outputDir": ".archify"}})
            first = analyze(str(root), config)

            (root / "src" / "app.py").write_text(
                "from util import helper\n\ndef run():\n    return helper() + 1\n",
                encoding="utf8",
            )
            second = analyze(str(root), config)
            manifest = json.loads((root / ".archify" / "manifest.json").read_text(encoding="utf8"))

            self.assertEqual(first["mode"], "full")
            self.assertEqual(second["mode"], "incremental")
            self.assertEqual(second["changedFileCount"], 1)
            self.assertEqual(second["deletedFileCount"], 0)
            self.assertFalse(second["semanticSkipped"])
            self.assertEqual(manifest["incremental"]["changed_code_files"], ["src/app.py"])

            (root / "src" / "util.py").unlink()
            third = analyze(str(root), config)
            graph = json.loads((root / ".archify" / "graph.json").read_text(encoding="utf8"))
            manifest = json.loads((root / ".archify" / "manifest.json").read_text(encoding="utf8"))

            self.assertEqual(third["mode"], "incremental")
            self.assertEqual(third["deletedFileCount"], 1)
            self.assertIn("src/util.py", manifest["incremental"]["deleted_files"])
            self.assertNotIn("src/util.py", manifest["files"])
            self.assertFalse(any(node.get("source_file") == "src/util.py" for node in graph["nodes"]))

    def test_analyze_falls_back_to_full_on_corrupt_or_incompatible_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "app.py").write_text("def run():\n    return 1\n", encoding="utf8")

            config = normalize_config(str(root), str(root), {"defaults": {"outputDir": ".archify"}})
            analyze(str(root), config)

            (root / ".archify" / "manifest.json").write_text("{not json", encoding="utf8")
            rerun = analyze(str(root), config)
            self.assertEqual(rerun["mode"], "full")
            self.assertEqual(rerun["fallbackReason"], "missing_prior_state")

            changed_config = normalize_config(
                str(root),
                str(root),
                {
                    "defaults": {"outputDir": ".archify"},
                    "analysis": {"semantic": {"enabled": True, "backend": "none"}},
                },
            )
            rerun_changed_config = analyze(str(root), changed_config)
            self.assertEqual(rerun_changed_config["mode"], "full")
            self.assertEqual(rerun_changed_config["fallbackReason"], "semantic_enabled_changed")

    def test_analyze_incremental_semantic_reuse_and_doc_refresh(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "docs").mkdir()
            (root / "src" / "app.py").write_text("def run():\n    return 1\n", encoding="utf8")
            (root / "docs" / "architecture.md").write_text(
                "# Architecture\n\nUse `src/app.py` as the application entrypoint.\n",
                encoding="utf8",
            )

            config = normalize_config(
                str(root),
                str(root),
                {
                    "defaults": {"outputDir": ".archify"},
                    "analysis": {"semantic": {"enabled": True, "backend": "none"}},
                },
            )
            analyze(str(root), config)

            (root / "src" / "app.py").write_text("def run():\n    return 2\n", encoding="utf8")
            code_only = analyze(str(root), config)
            self.assertEqual(code_only["mode"], "incremental")
            self.assertTrue(code_only["semanticSkipped"])

            (root / "docs" / "architecture.md").write_text(
                "# Architecture\n\nUse `src/app.py` as the application entrypoint.\n\n## Data\nDatabase access is planned.\n",
                encoding="utf8",
            )
            doc_change = analyze(str(root), config)
            docs_summary = json.loads((root / ".archify" / "docs-summary.json").read_text(encoding="utf8"))

            self.assertEqual(doc_change["mode"], "incremental")
            self.assertFalse(doc_change["semanticSkipped"])
            self.assertGreaterEqual(docs_summary["summary"]["processedDocumentCount"], 1)

    def test_analyze_recovers_stale_lock_and_rejects_live_lock(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "app.py").write_text("def run():\n    return 1\n", encoding="utf8")

            config = normalize_config(str(root), str(root), {"defaults": {"outputDir": ".archify"}})
            output_dir = root / ".archify"
            output_dir.mkdir()

            (output_dir / "analyze.lock").write_text(
                json.dumps({"pid": 999999, "startedAt": "2026-01-01T00:00:00+00:00", "targetPath": str(root)}),
                encoding="utf8",
            )
            analyze(str(root), config)
            manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf8"))
            self.assertIn("staleLockRecovered", manifest)

            (output_dir / "analyze.lock").write_text(
                json.dumps({"pid": os.getpid(), "startedAt": "2026-01-01T00:00:00+00:00", "targetPath": str(root)}),
                encoding="utf8",
            )
            with self.assertRaisesRegex(RuntimeError, "ANALYZE_IN_PROGRESS"):
                analyze(str(root), config)


class AnalyzeGraphTests(unittest.TestCase):
    def test_analyze_graph_produces_ranked_metadata(self) -> None:
        graph = {
            "nodes": [
                {"id": "file_a", "label": "src/a.py", "file_type": "code", "source_file": "src/a.py", "kind": "file", "community": 0},
                {"id": "svc", "label": "Service", "file_type": "code", "source_file": "src/a.py", "kind": "class", "community": 0},
                {"id": "run", "label": "run()", "file_type": "code", "source_file": "src/a.py", "kind": "method", "community": 0},
                {"id": "repo", "label": "Repo", "file_type": "code", "source_file": "src/b.py", "kind": "class", "community": 1},
            ],
            "edges": [
                {"source": "file_a", "target": "svc", "relation": "contains", "confidence": "EXTRACTED", "source_file": "src/a.py"},
                {"source": "svc", "target": "run", "relation": "contains", "confidence": "EXTRACTED", "source_file": "src/a.py"},
                {"source": "run", "target": "repo", "relation": "calls", "confidence": "AMBIGUOUS", "source_file": "src/a.py"},
            ],
            "hyperedges": [],
            "warnings": [],
            "communities": {
                "0": {"id": 0, "size": 3, "nodes": ["file_a", "svc", "run"], "cohesion": 0.67},
                "1": {"id": 1, "size": 1, "nodes": ["repo"], "cohesion": 1.0},
            },
        }

        analysis = analyze_graph(graph)

        self.assertEqual(analysis["godNodes"][0]["label"], "Service")
        self.assertEqual(analysis["surprisingConnections"][0]["source"], "run()")
        self.assertEqual(analysis["ambiguitySummary"]["ambiguousEdgeCount"], 1)
        self.assertGreaterEqual(len(analysis["suggestedQuestions"]), 1)


class ArchitectureContextTests(unittest.TestCase):
    def test_build_architecture_context_splits_subsystems_on_path_boundaries(self) -> None:
        graph = {
            "nodes": [
                {"id": "file_api", "label": "src/api/app.py", "file_type": "code", "source_file": "src/api/app.py", "kind": "file", "community": 0},
                {"id": "run", "label": "run()", "file_type": "code", "source_file": "src/api/app.py", "kind": "function", "community": 0},
                {"id": "handle", "label": "handle_request()", "file_type": "code", "source_file": "src/api/app.py", "kind": "function", "community": 0},
                {"id": "file_data", "label": "src/data/repo.py", "file_type": "code", "source_file": "src/data/repo.py", "kind": "file", "community": 0},
                {"id": "repo", "label": "Repo", "file_type": "code", "source_file": "src/data/repo.py", "kind": "class", "community": 0},
                {"id": "save", "label": "save()", "file_type": "code", "source_file": "src/data/repo.py", "kind": "method", "community": 0},
            ],
            "edges": [
                {"source": "file_api", "target": "run", "relation": "contains", "confidence": "EXTRACTED", "source_file": "src/api/app.py"},
                {"source": "run", "target": "handle", "relation": "calls", "confidence": "EXTRACTED", "source_file": "src/api/app.py"},
                {"source": "file_data", "target": "repo", "relation": "contains", "confidence": "EXTRACTED", "source_file": "src/data/repo.py"},
                {"source": "repo", "target": "save", "relation": "contains", "confidence": "EXTRACTED", "source_file": "src/data/repo.py"},
                {"source": "handle", "target": "repo", "relation": "calls", "confidence": "INFERRED", "source_file": "src/api/app.py"},
            ],
            "hyperedges": [],
            "warnings": [],
            "communities": {
                "0": {"id": 0, "size": 6, "nodes": ["file_api", "run", "handle", "file_data", "repo", "save"], "cohesion": 0.4},
            },
        }
        analysis = analyze_graph(graph)
        detection = {
            "inventory": [
                {"path": "src/api/app.py", "architectureTags": ["entrypoint", "route"]},
                {"path": "src/data/repo.py", "architectureTags": ["database"]},
            ],
            "totals": {"byArchitectureTag": {"entrypoint": 1}},
        }
        extraction_summary = {"nodeCount": 6}

        context = build_architecture_context(
            graph,
            analysis,
            detection,
            extraction_summary,
            {"processedDocumentCount": 0},
            "/tmp/project",
        )

        self.assertEqual(len(context["subsystems"]), 2)
        self.assertEqual([item["name"] for item in context["subsystems"]], ["src/api", "src/data"])
        self.assertEqual(len(context["data_flows"]), 1)
        self.assertEqual(context["data_flows"][0]["source_subsystem_id"], context["subsystems"][0]["id"])
        self.assertEqual(context["data_flows"][0]["target_subsystem_id"], context["subsystems"][1]["id"])

    def test_build_architecture_context_detects_interfaces_and_entrypoints(self) -> None:
        graph = {
            "nodes": [
                {"id": "file_cli", "label": "src/cli.py", "file_type": "code", "source_file": "src/cli.py", "kind": "file", "community": 0},
                {"id": "main", "label": "main()", "file_type": "code", "source_file": "src/cli.py", "kind": "function", "community": 0},
                {"id": "service", "label": "Service", "file_type": "code", "source_file": "src/service.py", "kind": "class", "community": 0},
            ],
            "edges": [
                {"source": "file_cli", "target": "main", "relation": "contains", "confidence": "EXTRACTED", "source_file": "src/cli.py"},
                {"source": "main", "target": "service", "relation": "calls", "confidence": "EXTRACTED", "source_file": "src/cli.py"},
            ],
            "hyperedges": [],
            "warnings": [],
            "communities": {
                "0": {"id": 0, "size": 3, "nodes": ["file_cli", "main", "service"], "cohesion": 0.67},
            },
        }
        analysis = analyze_graph(graph)
        detection = {
            "inventory": [
                {"path": "src/cli.py", "architectureTags": ["entrypoint"]},
                {"path": "src/service.py", "architectureTags": []},
            ],
            "totals": {"byArchitectureTag": {"entrypoint": 1}},
        }
        extraction_summary = {"nodeCount": 3}

        context = build_architecture_context(
            graph,
            analysis,
            detection,
            extraction_summary,
            {"processedDocumentCount": 0},
            "/tmp/project",
        )

        self.assertTrue(any(item["kind"] in {"entrypoint", "cli"} for item in context["interfaces"]))
        self.assertTrue(any(item["name"] == "main()" for item in context["key_entrypoints"]))

    def test_build_architecture_context_detects_concerns_and_open_questions(self) -> None:
        graph = {
            "nodes": [
                {"id": "file_auth", "label": "src/auth/session.py", "file_type": "code", "source_file": "src/auth/session.py", "kind": "file", "community": 0},
                {"id": "session", "label": "SessionAuth", "file_type": "code", "source_file": "src/auth/session.py", "kind": "class", "community": 0},
                {"id": "file_api", "label": "src/api/auth_handler.py", "file_type": "code", "source_file": "src/api/auth_handler.py", "kind": "file", "community": 1},
                {"id": "handler", "label": "auth_handler()", "file_type": "code", "source_file": "src/api/auth_handler.py", "kind": "function", "community": 1},
                {"id": "file_store", "label": "src/store/repo.py", "file_type": "code", "source_file": "src/store/repo.py", "kind": "file", "community": 2},
                {"id": "repo", "label": "Repo", "file_type": "code", "source_file": "src/store/repo.py", "kind": "class", "community": 2},
            ],
            "edges": [
                {"source": "file_auth", "target": "session", "relation": "contains", "confidence": "EXTRACTED", "source_file": "src/auth/session.py"},
                {"source": "file_api", "target": "handler", "relation": "contains", "confidence": "EXTRACTED", "source_file": "src/api/auth_handler.py"},
                {"source": "file_store", "target": "repo", "relation": "contains", "confidence": "EXTRACTED", "source_file": "src/store/repo.py"},
                {"source": "handler", "target": "session", "relation": "calls", "confidence": "AMBIGUOUS", "source_file": "src/api/auth_handler.py"},
                {"source": "session", "target": "repo", "relation": "calls", "confidence": "AMBIGUOUS", "source_file": "src/auth/session.py"},
            ],
            "hyperedges": [],
            "warnings": [],
            "communities": {
                "0": {"id": 0, "size": 2, "nodes": ["file_auth", "session"], "cohesion": 1.0},
                "1": {"id": 1, "size": 2, "nodes": ["file_api", "handler"], "cohesion": 1.0},
                "2": {"id": 2, "size": 2, "nodes": ["file_store", "repo"], "cohesion": 1.0},
            },
        }
        analysis = analyze_graph(graph)
        detection = {
            "inventory": [
                {"path": "src/auth/session.py", "architectureTags": []},
                {"path": "src/api/auth_handler.py", "architectureTags": ["route"]},
                {"path": "src/store/repo.py", "architectureTags": ["database"]},
            ],
            "totals": {"byArchitectureTag": {"entrypoint": 0}},
        }
        extraction_summary = {"nodeCount": 6}

        context = build_architecture_context(
            graph,
            analysis,
            detection,
            extraction_summary,
            {"processedDocumentCount": 0},
            "/tmp/project",
        )

        self.assertTrue(any(item["name"] == "auth" for item in context["cross_cutting_concerns"]))
        self.assertGreaterEqual(len(context["open_questions"]), 1)
        self.assertTrue(any(question["confidence"] == "low" for question in context["open_questions"]))


class SemanticPhaseTests(unittest.TestCase):
    def test_semantic_enabled_enriches_graph_and_docs_summary_deterministically(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "docs").mkdir()
            (root / "src" / "app.py").write_text(
                "def run():\n    return 1\n",
                encoding="utf8",
            )
            (root / "src" / "worker.py").write_text(
                "from app import run\n\n\ndef start():\n    return run()\n",
                encoding="utf8",
            )
            (root / "docs" / "architecture.md").write_text(
                "\n".join(
                    [
                        "# Architecture",
                        "",
                        "The runtime entrypoint lives in `src/app.py` and calls `run()`.",
                        "",
                        "## Flow",
                        "",
                        "The worker in `src/worker.py` coordinates startup.",
                        "",
                        "```python",
                        "from app import run",
                        "```",
                    ]
                )
                + "\n",
                encoding="utf8",
            )

            config_data = {
                "defaults": {"outputDir": ".archify"},
                "analysis": {"semantic": {"enabled": True}},
            }
            config = normalize_config(str(root), str(root), config_data)

            first = analyze(str(root), config)
            second = analyze(str(root), config)

            graph = json.loads((root / ".archify" / "graph.json").read_text(encoding="utf8"))
            docs_summary = json.loads((root / ".archify" / "docs-summary.json").read_text(encoding="utf8"))
            manifest = json.loads((root / ".archify" / "manifest.json").read_text(encoding="utf8"))
            architecture_context = json.loads((root / ".archify" / "architecture-context.json").read_text(encoding="utf8"))

            doc_nodes = [node for node in graph["nodes"] if node.get("file_type") == "document"]
            self.assertGreaterEqual(len(doc_nodes), 3)
            self.assertTrue(any(node["kind"] == "doc_section" for node in doc_nodes))
            self.assertTrue(any(edge["relation"] == "references" and edge["source_file"] == "docs/architecture.md" for edge in graph["edges"]))
            self.assertEqual(docs_summary["status"], "ready")
            self.assertEqual(docs_summary["semantic"]["backend"], "none")
            self.assertTrue(docs_summary["semantic"]["providerEnrichmentSkipped"])
            self.assertEqual(docs_summary["summary"]["processedDocumentCount"], 1)
            self.assertEqual(docs_summary["confirmedFacts"]["processedDocuments"][0]["path"], "docs/architecture.md")
            self.assertGreaterEqual(len(docs_summary["inferredAlignments"]["docToSubsystem"]), 1)
            self.assertEqual(first["semanticDocumentCount"], 1)
            self.assertEqual(first["semanticSummary"], second["semanticSummary"])
            self.assertEqual(manifest["files"]["docs/architecture.md"]["semantic"]["status"], "ready")
            self.assertGreaterEqual(architecture_context["summary"]["processedDocumentCount"], 1)
            self.assertTrue(any(subsystem["doc_evidence_node_ids"] for subsystem in architecture_context["subsystems"]))

            second_graph = json.loads((root / ".archify" / "graph.json").read_text(encoding="utf8"))
            self.assertEqual(
                [node["id"] for node in doc_nodes],
                [node["id"] for node in second_graph["nodes"] if node.get("file_type") == "document"],
            )

    def test_semantic_enabled_handles_code_only_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "app.py").write_text("def run():\n    return 1\n", encoding="utf8")

            config = normalize_config(
                str(root),
                str(root),
                {"defaults": {"outputDir": ".archify"}, "analysis": {"semantic": {"enabled": True}}},
            )
            result = analyze(str(root), config)
            docs_summary = json.loads((root / ".archify" / "docs-summary.json").read_text(encoding="utf8"))

            self.assertEqual(result["semanticDocumentCount"], 0)
            self.assertEqual(docs_summary["status"], "ready")
            self.assertEqual(docs_summary["summary"]["processedDocumentCount"], 0)
            self.assertEqual(docs_summary["summary"]["detectedDocumentCount"], 0)
            self.assertEqual(docs_summary["inferredAlignments"]["unresolvedDocuments"], [])

    def test_semantic_skips_oversized_and_malformed_documents_with_warnings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "docs").mkdir()
            (root / "src" / "app.py").write_text("def run():\n    return 1\n", encoding="utf8")
            (root / "docs" / "oversized.md").write_text("# Big\n\n" + ("content\n" * 200), encoding="utf8")
            (root / "docs" / "broken.txt").write_bytes(b"\xff\xfe\x00\x00")

            config = normalize_config(
                str(root),
                str(root),
                {
                    "defaults": {"outputDir": ".archify"},
                    "analysis": {
                        "semantic": {
                            "enabled": True,
                            "maxDocumentBytes": 64,
                        }
                    },
                },
            )
            analyze(str(root), config)

            docs_summary = json.loads((root / ".archify" / "docs-summary.json").read_text(encoding="utf8"))
            manifest = json.loads((root / ".archify" / "manifest.json").read_text(encoding="utf8"))
            graph = json.loads((root / ".archify" / "graph.json").read_text(encoding="utf8"))

            skipped = {item["path"]: item["reason"] for item in docs_summary["confirmedFacts"]["skippedDocuments"]}
            self.assertEqual(skipped["docs/oversized.md"], "max_document_bytes_exceeded")
            self.assertEqual(skipped["docs/broken.txt"], "decode_error")
            self.assertEqual(manifest["files"]["docs/oversized.md"]["semantic"]["status"], "skipped")
            self.assertEqual(manifest["files"]["docs/broken.txt"]["semantic"]["status"], "skipped")
            self.assertGreaterEqual(graph["semantic"]["warningCount"], 2)


if __name__ == "__main__":
    unittest.main()
