"""README.md が構成変更に追従しているかの簡易チェック（Spark 不要・高速）。

構成変更・機能拡張のたびに README.md の更新を忘れる、という事故の
一次検知用。`resources/*.yml` / `pipelines/*.py` / `notebooks/*.py` /
`tests/*.py` / `scripts/*.py` / `dashboards/*.json` / `apps/**/*.py` の
ファイル名が README.md 本文のどこかに出現しているかだけを確認する
簡易チェックであり、記述内容の正しさまでは保証しない。

このテストが落ちたら、CLAUDE.md の指示どおり README.md の
「構成」ツリー・POC 表・アーキテクチャ図などを見直すこと。
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README_TEXT = (ROOT / "README.md").read_text(encoding="utf-8")

# README への記載を必須とするファイル群。
# ここに新しいディレクトリ・拡張子を追加すればチェック対象を増やせる。
TRACKED_GLOBS = [
    "resources/*.yml",
    "pipelines/*.py",
    "notebooks/*.py",
    "tests/*.py",
    "scripts/*.py",
    "dashboards/*.json",
    "apps/**/*.py",
]


def test_tracked_files_are_mentioned_in_readme():
    missing = []
    for pattern in TRACKED_GLOBS:
        for path in sorted(ROOT.glob(pattern)):
            if path.name not in README_TEXT:
                missing.append(str(path.relative_to(ROOT)))

    assert not missing, (
        "以下のファイルが README.md に記載されていません。"
        " 構成変更・機能拡張をしたら README.md（構成ツリー・POC表・"
        " アーキテクチャ図など）も更新してください（CLAUDE.md 参照）:\n"
        + "\n".join(missing)
    )
