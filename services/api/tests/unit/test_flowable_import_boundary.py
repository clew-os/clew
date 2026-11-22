# SPDX-FileCopyrightText: The Clew Authors
# SPDX-License-Identifier: Apache-2.0
"""Business routers and services never call Flowable (they emit outbox events). Only the worker,
bootstrap tools, the workflow package and the sysadmin admin modules may import the client."""

import ast
from pathlib import Path

APP = Path(__file__).resolve().parents[2] / "app"
CLIENT = "app.workflow.flowable_client"
ALLOWED = ("worker/", "bootstrap/", "workflow/", "services/admin_", "routers/admin_")


def _imports_client(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module == CLIENT or (
                node.module == "app.workflow" and any(a.name == "flowable_client" for a in node.names)
            ):
                return True
        elif isinstance(node, ast.Import) and any(a.name == CLIENT for a in node.names):
            return True
    return False


def test_only_allowed_modules_import_the_flowable_client():
    offenders = []
    for path in APP.rglob("*.py"):
        rel = path.relative_to(APP).as_posix()
        if not rel.startswith(ALLOWED) and _imports_client(ast.parse(path.read_text())):
            offenders.append(rel)
    assert offenders == [], f"business code must not call Flowable: {offenders}"


def test_the_check_sees_the_known_importers():
    seen = [p for p in APP.rglob("*.py") if _imports_client(ast.parse(p.read_text()))]
    assert any(p.name == "admin_workflow.py" for p in seen) and any(p.parent.name == "worker" for p in seen)
