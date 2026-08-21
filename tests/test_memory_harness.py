import sys
from pathlib import Path

# Add script folder to path
sys.path.append(str(Path(__file__).parent.parent / ".agent" / "scripts"))

from test_memory_upgrade import (
    BM25Search,
    OrphanBranchSync,
    StateGraph,
    estimate_tokens_and_check,
    get_git_file_deltas,
)


def test_state_graph(tmp_path: Path) -> None:
    """Verifies that the State Graph writes and maps nodes correctly."""
    graph_file = tmp_path / "test_graph.json"
    sg = StateGraph(graph_file)
    assert len(sg.nodes) == 0
    sg.add_node("node-1", None, "init", ["file.txt"])
    assert "node-1" in sg.nodes
    assert sg.nodes["node-1"]["parent_id"] is None
    assert sg.nodes["node-1"]["affected_files"] == ["file.txt"]


def test_bm25_search() -> None:
    """Verifies that the BM25 Search ranks matching documents higher."""
    documents = [
        {
            "topic": "python async",
            "lesson": "Use asyncio.gather for concurrent tasks.",
            "tags": ["python", "async"],
        },
        {
            "topic": "react component",
            "lesson": "Use React.memo to prevent unnecessary re-renders.",
            "tags": ["react", "frontend"],
        },
    ]
    bm25 = BM25Search(documents)
    # Search for async - doc 0 should rank higher
    results = bm25.rank("async")
    assert len(results) > 0
    assert results[0][0] == 0
    # Search for react - doc 1 should rank higher
    results = bm25.rank("react")
    assert len(results) > 0
    assert results[0][0] == 1


def test_file_deltas() -> None:
    """Verifies that Git file deltas return a parseable dictionary."""
    deltas = get_git_file_deltas()
    assert isinstance(deltas, dict)


def test_context_compaction(tmp_path: Path) -> None:
    """Verifies that token estimation correctly checks threshold limits."""
    tokens, compact = estimate_tokens_and_check([tmp_path / "non_existent.json"], threshold=100)
    assert tokens == 0
    assert not compact

    # Estimate with mock file
    mock_file = tmp_path / "mock.json"
    mock_file.write_text("a" * 800, encoding="utf-8")
    tokens, compact = estimate_tokens_and_check([mock_file], threshold=100)
    assert tokens == 200  # 800 // 4
    assert compact


def test_orphan_branch_sync(tmp_path: Path) -> None:
    """Verifies that local mock remote setup executes correctly."""
    repo_dir = Path(__file__).parent.parent
    mock_remote_dir = tmp_path / "mock_remote"
    sync = OrphanBranchSync(repo_dir, mock_remote_dir)
    sync.setup_mock_remote()
    assert mock_remote_dir.exists()

    # Clean up mock remote repo
    import shutil

    if mock_remote_dir.exists():
        shutil.rmtree(mock_remote_dir)
