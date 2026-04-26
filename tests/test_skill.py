"""Tests for skill.py runtime behavior — CLI dispatch and env var propagation."""
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# run_cli() — env var and subprocess dispatch
# ---------------------------------------------------------------------------


def test_run_cli_sets_paper_fetcher_cwd():
    """run_cli must set PAPER_FETCHER_CWD in the subprocess environment."""
    import skill

    with patch("skill.subprocess.run") as mock_run:
        skill.run_cli("search", "test topic")

        assert mock_run.called, "subprocess.run was not called"
        _, kwargs = mock_run.call_args
        env = kwargs.get("env", os.environ)
        assert "PAPER_FETCHER_CWD" in env, (
            "PAPER_FETCHER_CWD missing from subprocess env"
        )
        assert env["PAPER_FETCHER_CWD"] == skill._LAUNCH_CWD, (
            f"Expected {skill._LAUNCH_CWD}, got {env['PAPER_FETCHER_CWD']}"
        )


def test_run_cli_uses_cwd_project_root():
    """run_cli must run subprocess with cwd=PROJECT_ROOT."""
    import skill

    with patch("skill.subprocess.run") as mock_run:
        skill.run_cli("search", "test topic")

        _, kwargs = mock_run.call_args
        assert kwargs.get("cwd") == skill.PROJECT_ROOT, (
            f"Expected cwd={skill.PROJECT_ROOT}, got {kwargs.get('cwd')}"
        )


def test_run_cli_search_cmd():
    """search action produces correct command."""
    import skill

    with patch("skill.subprocess.run") as mock_run:
        skill.run_cli("search", "machine learning")

        args, _ = mock_run.call_args
        cmd = args[0]
        assert cmd[-1] == "machine learning" or "--topic" in cmd, (
            f"Unexpected cmd: {cmd}"
        )


def test_run_cli_download_adds_all_flag():
    """download action adds --all flag for non-TTY skill invocations."""
    import skill

    with patch("skill.subprocess.run") as mock_run:
        skill.run_cli("download", "test topic")

        args, _ = mock_run.call_args
        cmd = args[0]
        assert "--all" in cmd, (
            f"download cmd missing --all: {cmd}"
        )


def test_run_cli_list_no_topic():
    """list action passes no --topic flag."""
    import skill

    with patch("skill.subprocess.run") as mock_run:
        skill.run_cli("list", None)

        args, _ = mock_run.call_args
        cmd = args[0]
        assert cmd[-1] == "list", f"Expected 'list' at end, got {cmd}"
        assert "--topic" not in cmd, f"list cmd should not have --topic: {cmd}"


def test_run_cli_extra_args_passed_through():
    """extra_args are appended to the CLI command."""
    import skill

    with patch("skill.subprocess.run") as mock_run:
        skill.run_cli("search", None, ["--topic", "foo", "--new-topic"])

        args, _ = mock_run.call_args
        cmd = args[0]
        assert "--new-topic" in cmd, f"extra_args missing --new-topic: {cmd}"
        # Verify --topic came from extra_args, not from the 'topic' param
        assert "--topic" in cmd, f"extra_args missing --topic: {cmd}"


# ---------------------------------------------------------------------------
# CLI-style argument detection in main()
# ---------------------------------------------------------------------------


def test_main_detects_cli_style_search():
    """main() detects 'search --topic ...' as CLI-style and dispatches."""
    import skill

    with (
        patch("skill._bootstrap") as mock_bootstrap,
        patch("skill.run_cli") as mock_run_cli,
        patch.object(sys, "argv", ["skill.py", "search", "--topic", "医学影像", "--new-topic"]),
    ):
        skill.main()

        mock_bootstrap.assert_called_once()
        mock_run_cli.assert_called_once_with(
            "search", None, ["--topic", "医学影像", "--new-topic"]
        )


def test_main_detects_cli_style_download():
    """main() detects 'download --topic ...' as CLI-style."""
    import skill

    with (
        patch("skill._bootstrap") as mock_bootstrap,
        patch("skill.run_cli") as mock_run_cli,
        patch.object(sys, "argv", ["skill.py", "download", "--topic", "test"]),
    ):
        skill.main()

        mock_run_cli.assert_called_once_with(
            "download", None, ["--topic", "test"]
        )


def test_main_passes_natural_language_to_detect():
    """main() uses detect_intent for natural language args."""
    import skill

    with (
        patch("skill._bootstrap"),
        patch("skill.run_cli") as mock_run_cli,
        patch.object(sys, "argv", ["skill.py", "search papers on NLP"]),
    ):
        skill.main()

        mock_run_cli.assert_called_once()
        args, _ = mock_run_cli.call_args
        assert args[0] == "search", f"Expected search action, got {args[0]}"
        assert args[1] is not None, "Expected extracted topic"


def test_main_natural_language_list():
    """'list' or 'show' triggers list action."""
    import skill

    with (
        patch("skill._bootstrap"),
        patch("skill.run_cli") as mock_run_cli,
        patch.object(sys, "argv", ["skill.py", "show my topics"]),
    ):
        skill.main()

        mock_run_cli.assert_called_once_with("list", None)


# ---------------------------------------------------------------------------
# _LAUNCH_CWD picks up PAPER_FETCHER_CWD
# ---------------------------------------------------------------------------


def test_module_launch_cwd_from_env_var():
    """_LAUNCH_CWD uses PAPER_FETCHER_CWD when set (tested via run_cli)."""
    with tempfile.TemporaryDirectory() as fake_cwd:
        with patch.dict(os.environ, {"PAPER_FETCHER_CWD": fake_cwd}, clear=False):
            # Re-import to re-evaluate _LAUNCH_CWD
            import importlib
            import skill as skill_mod
            importlib.reload(skill_mod)

            assert skill_mod._LAUNCH_CWD == fake_cwd, (
                f"Expected {fake_cwd}, got {skill_mod._LAUNCH_CWD}"
            )

            with patch("skill.subprocess.run") as mock_run:
                skill_mod.run_cli("search", "test")
                _, kwargs = mock_run.call_args
                env = kwargs["env"]
                assert env["PAPER_FETCHER_CWD"] == fake_cwd, (
                    f"Expected {fake_cwd}, got {env['PAPER_FETCHER_CWD']}"
                )
