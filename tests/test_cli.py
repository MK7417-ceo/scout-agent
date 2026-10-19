"""CLI tests — all in --mock mode, fully offline."""

from scout.cli import main


def test_cli_mock_writes_report_file(tmp_path, monkeypatch):
    out = tmp_path / "report.md"
    monkeypatch.chdir(tmp_path)
    rc = main(
        ["What is retrieval-augmented generation?", "--mock", "--output", str(out)]
    )
    assert rc == 0
    text = out.read_text(encoding="utf-8")
    assert text.startswith("# Research report:")
    assert "## Sources" in text
    assert "arxiv.org" in text  # mock sources are cited


def test_cli_mock_stdout(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    rc = main(["Some topic", "--mock"])
    assert rc == 0
    assert "## Key findings" in capsys.readouterr().out


def test_cli_without_key_and_without_mock_fails_gracefully(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    rc = main(["Some topic"])
    assert rc == 2
