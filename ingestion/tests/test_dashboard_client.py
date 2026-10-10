import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "dashboard"))

from metrics_client import build_command  # noqa: E402


def test_build_command_includes_every_option(tmp_path):
    cmd = build_command(
        ["prs_merged", "pr_merge_rate"],
        output_csv=tmp_path / "out.csv",
        group_by=["repo__repo_name"],
        start_time="2026-08-01",
        end_time="2026-10-01",
        order=["-prs_merged"],
        limit=25,
    )
    joined = " ".join(cmd)
    assert "--metrics prs_merged,pr_merge_rate" in joined
    assert "--group-by repo__repo_name" in joined
    assert "--start-time 2026-08-01" in joined
    assert "--end-time 2026-10-01" in joined
    assert "--order -prs_merged" in joined
    assert "--limit 25" in joined
    assert f"--csv {tmp_path / 'out.csv'}" in joined


def test_build_command_skips_unused_options(tmp_path):
    cmd = build_command(["contributions"], output_csv=tmp_path / "out.csv")
    assert "--group-by" not in cmd
    assert "--limit" not in cmd
