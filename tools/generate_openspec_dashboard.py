"""Generate a read-only Chinese dashboard from the OpenSpec workspace."""

from __future__ import annotations

import argparse
import html
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

TASK_DONE = re.compile(r"^\s*- \[x\]\s+", re.IGNORECASE)
TASK_OPEN = re.compile(r"^\s*- \[ \]\s+", re.IGNORECASE)
ARCHIVE_NAME = re.compile(r"^(\d{4}-\d{2}-\d{2})-(.+)$")


@dataclass(frozen=True)
class Change:
    name: str
    path: Path
    done_tasks: int
    total_tasks: int
    archived_on: str | None = None

    @property
    def open_tasks(self) -> int:
        return self.total_tasks - self.done_tasks

    @property
    def status(self) -> str:
        if self.archived_on:
            return "已归档"
        if self.total_tasks == 0:
            return "规划中"
        if self.done_tasks == self.total_tasks:
            return "待归档"
        return "执行中"


def count_tasks(tasks_file: Path) -> tuple[int, int]:
    if not tasks_file.is_file():
        return 0, 0

    done = 0
    open_tasks = 0
    for line in tasks_file.read_text(encoding="utf-8").splitlines():
        if TASK_DONE.match(line):
            done += 1
        elif TASK_OPEN.match(line):
            open_tasks += 1
    return done, done + open_tasks


def read_summary(spec_file: Path) -> str:
    if not spec_file.is_file():
        return "已生效的 OpenSpec 能力规格。"

    lines = [line.strip() for line in spec_file.read_text(encoding="utf-8").splitlines()]
    purpose_index = next(
        (index for index, line in enumerate(lines) if line.lower() in {"## purpose", "## 目的"}),
        None,
    )
    candidate_lines = lines[purpose_index + 1 :] if purpose_index is not None else lines
    paragraph: list[str] = []
    for line in candidate_lines:
        if line.startswith("#") and paragraph:
            break
        if not line or line.startswith("#") or line.startswith("<!--"):
            continue
        paragraph.append(line)
        if len(" ".join(paragraph)) >= 160:
            break

    summary = " ".join(paragraph)
    if not summary or summary.startswith("TBD"):
        requirement = next(
            (
                line.removeprefix("### Requirement:").strip()
                for line in lines
                if line.startswith("### Requirement:")
            ),
            "已生效的 OpenSpec 能力规格。",
        )
        summary = requirement
    return summary[:180].rstrip() + ("..." if len(summary) > 180 else "")


def relative_link(source: Path, target: Path) -> str:
    try:
        relative = target.relative_to(source.parent)
    except ValueError:
        relative = Path(os.path.relpath(target, source.parent))
    return quote(relative.as_posix(), safe="/:#?=&")


def artifact_links(change: Change, output_file: Path) -> str:
    links: list[str] = []
    for filename, label in (
        ("proposal.md", "提案"),
        ("design.md", "设计"),
        ("tasks.md", "任务"),
        ("verification.md", "验证"),
    ):
        artifact = change.path / filename
        if artifact.is_file():
            links.append(f'<a href="{relative_link(output_file, artifact)}">{label}</a>')
    return '<span class="artifact-links">' + "".join(links) + "</span>"


def read_changes(changes_dir: Path) -> tuple[list[Change], list[Change]]:
    active_changes: list[Change] = []
    archived_changes: list[Change] = []

    if not changes_dir.is_dir():
        return active_changes, archived_changes

    for directory in sorted(changes_dir.iterdir(), key=lambda item: item.name):
        if not directory.is_dir():
            continue
        if directory.name == "archive":
            for archive in sorted(directory.iterdir(), key=lambda item: item.name, reverse=True):
                if not archive.is_dir():
                    continue
                done, total = count_tasks(archive / "tasks.md")
                match = ARCHIVE_NAME.match(archive.name)
                archived_changes.append(
                    Change(
                        name=archive.name,
                        path=archive,
                        done_tasks=done,
                        total_tasks=total,
                        archived_on=match.group(1) if match else None,
                    )
                )
            continue

        done, total = count_tasks(directory / "tasks.md")
        active_changes.append(Change(directory.name, directory, done, total))

    archived_changes.sort(key=lambda change: change.name, reverse=True)
    return active_changes, archived_changes


def capability_rows(specs_dir: Path, output_file: Path) -> str:
    rows: list[str] = []
    for capability in (
        sorted(specs_dir.iterdir(), key=lambda item: item.name) if specs_dir.is_dir() else []
    ):
        spec_file = capability / "spec.md"
        if not capability.is_dir() or not spec_file.is_file():
            continue
        rows.append(
            '<li class="capability-row">'
            "<div>"
            f"<code>{html.escape(capability.name)}</code>"
            f"<p>{html.escape(read_summary(spec_file))}</p>"
            "</div>"
            f'<a href="{relative_link(output_file, spec_file)}">查看规格</a>'
            "</li>"
        )
    return "".join(rows) or '<li class="empty-row">尚未发现正式能力规格。</li>'


def active_change_rows(changes: list[Change], output_file: Path) -> str:
    if not changes:
        return (
            '<div class="empty-state">'
            "<strong>当前没有进行中的 Change</strong>"
            "<span>下一项能力从 OpenSpec Explore 开始，再创建独立 Change。</span>"
            "</div>"
        )

    rows: list[str] = []
    for change in changes:
        progress = (
            "尚未拆分任务"
            if change.total_tasks == 0
            else f"{change.done_tasks}/{change.total_tasks} 项任务完成"
        )
        rows.append(
            '<article class="change-row">'
            "<div>"
            f"<code>{html.escape(change.name)}</code>"
            f"<p>{progress}</p>"
            "</div>"
            f'<span class="status {change.status}">{change.status}</span>'
            f"{artifact_links(change, output_file)}"
            "</article>"
        )
    return "".join(rows)


def archive_rows(changes: list[Change], output_file: Path) -> str:
    rows: list[str] = []
    for change in changes:
        task_label = (
            "未维护任务清单"
            if change.total_tasks == 0
            else f"{change.done_tasks}/{change.total_tasks} 项任务已完成"
        )
        date_label = change.archived_on or "未知日期"
        rows.append(
            '<details class="archive-item">'
            "<summary>"
            '<span class="archive-date">'
            f"{html.escape(date_label)}"
            "</span>"
            '<span class="archive-name">'
            f"<code>{html.escape(change.name)}</code>"
            "</span>"
            '<span class="archive-tasks">'
            f"{task_label}"
            "</span>"
            "</summary>"
            f'<div class="archive-links">{artifact_links(change, output_file)}</div>'
            "</details>"
        )
    return "".join(rows) or '<p class="empty-row">尚无归档 Change。</p>'


def render_dashboard(root: Path, output_file: Path) -> str:
    openspec_dir = root / "openspec"
    active_changes, archived_changes = read_changes(openspec_dir / "changes")
    completed_tasks = sum(change.done_tasks for change in archived_changes)
    total_archived_tasks = sum(change.total_tasks for change in archived_changes)
    capability_count = sum(
        1 for path in (openspec_dir / "specs").glob("*/spec.md") if path.is_file()
    )
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light dark">
  <title>OpenSpec 项目看板</title>
  <style>
    :root {{
      --canvas: #f4f6f8;
      --surface: #ffffff;
      --ink: #1f2933;
      --muted: #5c6875;
      --line: #d7dde4;
      --blue: #1f69bd;
      --blue-soft: #eaf2fb;
      --green: #16794c;
      --green-soft: #e7f5ed;
      --amber: #9b5a00;
      --amber-soft: #fff2db;
      --red: #b23a3a;
      --red-soft: #fae8e8;
    }}
    @media (prefers-color-scheme: dark) {{
      :root {{
        --canvas: #151a20;
        --surface: #202831;
        --ink: #edf2f7;
        --muted: #b3c0cc;
        --line: #394551;
        --blue: #78b7ff;
        --blue-soft: #1c3854;
        --green: #6bd59e;
        --green-soft: #1d4030;
        --amber: #f0bb6d;
        --amber-soft: #4b391d;
        --red: #f19a9a;
        --red-soft: #542b2b;
      }}
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--canvas);
      color: var(--ink);
      font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif;
      font-size: 15px;
      line-height: 1.55;
    }}
    a {{ color: var(--blue); text-decoration-thickness: 1px; text-underline-offset: 3px; }}
    a:hover {{ color: var(--green); }}
    code {{
      color: inherit;
      font-family: Consolas, "Courier New", monospace;
      font-size: 0.88em;
      overflow-wrap: anywhere;
    }}
    .topbar {{ background: var(--surface); border-bottom: 1px solid var(--line); }}
    .topbar-inner, main {{
      max-width: 1200px;
      margin: 0 auto;
      padding-left: 28px;
      padding-right: 28px;
    }}
    .topbar-inner {{
      min-height: 74px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 24px;
    }}
    .product-name {{ margin: 0; font-size: 20px; font-weight: 500; letter-spacing: 0; }}
    .product-meta {{ color: var(--muted); font-size: 13px; white-space: nowrap; }}
    main {{ padding-top: 30px; padding-bottom: 48px; }}
    .intro {{
      display: flex;
      align-items: end;
      justify-content: space-between;
      gap: 24px;
      margin-bottom: 24px;
    }}
    h1, h2 {{ margin: 0; font-weight: 500; letter-spacing: 0; }}
    h1 {{ font-size: 28px; }}
    h2 {{ font-size: 18px; }}
    .intro p {{ max-width: 680px; margin: 8px 0 0; color: var(--muted); }}
    .source-note {{ color: var(--muted); font-size: 13px; text-align: right; }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
      margin-bottom: 34px;
    }}
    .metric {{
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 16px;
      min-height: 108px;
    }}
    .metric dt {{ color: var(--muted); font-size: 13px; }}
    .metric dd {{ margin: 6px 0 0; font-size: 30px; font-weight: 500; line-height: 1.1; }}
    .metric small {{ display: block; margin-top: 8px; color: var(--muted); }}
    .section {{ margin-top: 34px; }}
    .section-head {{
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      gap: 16px;
      margin-bottom: 14px;
    }}
    .section-head p {{ margin: 0; color: var(--muted); font-size: 13px; }}
    .flow {{
      display: grid;
      grid-template-columns: repeat(6, minmax(0, 1fr));
      gap: 0;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--surface);
      overflow: hidden;
    }}
    .flow-step {{
      position: relative;
      min-height: 116px;
      padding: 18px 16px 16px;
      border-right: 1px solid var(--line);
    }}
    .flow-step:last-child {{ border-right: 0; }}
    .flow-index {{
      display: block;
      color: var(--blue);
      font-family: Consolas, monospace;
      font-size: 12px;
    }}
    .flow-step strong {{ display: block; margin-top: 8px; font-weight: 500; }}
    .flow-step span:last-child {{
      display: block;
      margin-top: 4px;
      color: var(--muted);
      font-size: 13px;
    }}
    .flow-step.next {{ background: var(--blue-soft); box-shadow: inset 0 3px 0 var(--blue); }}
    .content-grid {{
      display: grid;
      grid-template-columns: minmax(0, 1.25fr) minmax(320px, 0.75fr);
      gap: 24px;
      align-items: start;
    }}
    .ledger {{ border-top: 2px solid var(--ink); }}
    .capability-list {{ list-style: none; padding: 0; margin: 0; }}
    .capability-row {{
      display: flex;
      justify-content: space-between;
      gap: 20px;
      padding: 16px 0;
      border-bottom: 1px solid var(--line);
    }}
    .capability-row p {{ margin: 6px 0 0; color: var(--muted); font-size: 13px; }}
    .capability-row > a {{
      flex: 0 0 auto;
      align-self: start;
      font-size: 13px;
      white-space: nowrap;
    }}
    .empty-state {{
      min-height: 180px;
      display: grid;
      place-content: center;
      gap: 6px;
      padding: 26px;
      border-top: 2px solid var(--green);
      background: var(--green-soft);
      color: var(--ink);
    }}
    .empty-state strong {{ font-weight: 500; }}
    .empty-state span {{ color: var(--muted); font-size: 13px; }}
    .change-row {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto auto;
      gap: 14px;
      align-items: center;
      padding: 14px 0;
      border-bottom: 1px solid var(--line);
    }}
    .change-row p {{ margin: 4px 0 0; color: var(--muted); font-size: 13px; }}
    .status {{ padding: 3px 8px; border-radius: 4px; font-size: 12px; white-space: nowrap; }}
    .status.已归档 {{ color: var(--green); background: var(--green-soft); }}
    .status.规划中 {{ color: var(--amber); background: var(--amber-soft); }}
    .status.待归档 {{ color: var(--blue); background: var(--blue-soft); }}
    .status.执行中 {{ color: var(--red); background: var(--red-soft); }}
    .artifact-links {{ display: inline-flex; flex-wrap: wrap; gap: 10px; font-size: 13px; }}
    .archive-list {{ border-top: 2px solid var(--ink); }}
    .archive-item {{ border-bottom: 1px solid var(--line); }}
    .archive-item summary {{
      display: grid;
      grid-template-columns: 104px minmax(0, 1fr) auto;
      gap: 16px;
      align-items: center;
      padding: 15px 4px;
      cursor: pointer;
      list-style: none;
    }}
    .archive-item summary::-webkit-details-marker {{ display: none; }}
    .archive-item summary::before {{
      content: "+";
      color: var(--blue);
      font-family: Consolas, monospace;
      grid-column: 1;
      position: absolute;
      transform: translateX(-20px);
    }}
    .archive-item[open] summary::before {{ content: "-"; }}
    .archive-date, .archive-tasks {{ color: var(--muted); font-size: 13px; }}
    .archive-tasks {{ white-space: nowrap; }}
    .archive-links {{ padding: 0 4px 16px 108px; }}
    .empty-row {{ color: var(--muted); padding: 16px 0; }}
    .footer-note {{ margin: 28px 0 0; color: var(--muted); font-size: 13px; }}
    @media (max-width: 820px) {{
      .topbar-inner, .intro {{ align-items: flex-start; flex-direction: column; }}
      .product-meta, .source-note {{ white-space: normal; text-align: left; }}
      .metrics {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .flow {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
      .flow-step:nth-child(3) {{ border-right: 0; }}
      .flow-step:nth-child(-n + 3) {{ border-bottom: 1px solid var(--line); }}
      .content-grid {{ grid-template-columns: 1fr; }}
    }}
    @media (max-width: 540px) {{
      .topbar-inner, main {{ padding-left: 18px; padding-right: 18px; }}
      h1 {{ font-size: 24px; }}
      .flow {{ grid-template-columns: 1fr; }}
      .flow-step, .flow-step:nth-child(3) {{
        border-right: 0;
        border-bottom: 1px solid var(--line);
        min-height: auto;
      }}
      .flow-step:last-child {{ border-bottom: 0; }}
      .capability-row {{ flex-direction: column; gap: 8px; }}
      .archive-item summary {{ grid-template-columns: 1fr; gap: 3px; padding-left: 22px; }}
      .archive-item summary::before {{ transform: translateX(-18px); }}
      .archive-links {{ padding-left: 22px; }}
    }}
  </style>
</head>
<body>
  <header class="topbar">
    <div class="topbar-inner">
      <p class="product-name">Go Agent System</p>
      <span class="product-meta">OpenSpec 项目看板</span>
    </div>
  </header>
  <main>
    <section class="intro" aria-labelledby="dashboard-title">
      <div>
        <h1 id="dashboard-title">交付状态</h1>
        <p>当前状态直接从 OpenSpec 的正式规格、活动 Change 与归档记录生成。</p>
      </div>
      <div class="source-note">生成时间：{generated_at}<br>数据源：<code>openspec/</code></div>
    </section>

    <dl class="metrics" aria-label="OpenSpec 状态摘要">
      <div class="metric">
        <dt>活动 Change</dt><dd>{len(active_changes)}</dd><small>当前正在规划或实施</small>
      </div>
      <div class="metric">
        <dt>正式能力规格</dt><dd>{capability_count}</dd><small>已生效的行为基线</small>
      </div>
      <div class="metric">
        <dt>已归档 Change</dt><dd>{len(archived_changes)}</dd><small>包含验收与追溯材料</small>
      </div>
      <div class="metric">
        <dt>归档任务</dt><dd>{completed_tasks}/{total_archived_tasks}</dd>
        <small>归档 Change 中已勾选任务</small>
      </div>
    </dl>

    <section class="section" aria-labelledby="flow-title">
      <div class="section-head">
        <h2 id="flow-title">标准交付流程</h2><p>当前下一步：探索新的 Phase 4 能力边界</p>
      </div>
      <div class="flow" aria-label="OpenSpec 交付流程">
        <div class="flow-step next">
          <span class="flow-index">01</span><strong>Explore</strong><span>澄清问题与边界</span>
        </div>
        <div class="flow-step">
          <span class="flow-index">02</span><strong>Change</strong><span>创建独立变更</span>
        </div>
        <div class="flow-step">
          <span class="flow-index">03</span><strong>Artifacts</strong>
          <span>提案、设计、规格、任务</span>
        </div>
        <div class="flow-step">
          <span class="flow-index">04</span><strong>Apply</strong><span>实现与验证任务</span>
        </div>
        <div class="flow-step">
          <span class="flow-index">05</span><strong>Sync</strong><span>同步正式规格</span>
        </div>
        <div class="flow-step">
          <span class="flow-index">06</span><strong>Archive</strong><span>归档交付证据</span>
        </div>
      </div>
    </section>

    <div class="content-grid">
      <section class="section" aria-labelledby="capabilities-title">
        <div class="section-head">
          <h2 id="capabilities-title">当前生效能力</h2><p>来自 <code>openspec/specs/</code></p>
        </div>
        <div class="ledger">
          <ul class="capability-list">{capability_rows(openspec_dir / "specs", output_file)}</ul>
        </div>
      </section>
      <section class="section" aria-labelledby="changes-title">
        <div class="section-head">
          <h2 id="changes-title">活动 Change</h2><p>来自 <code>openspec/changes/</code></p>
        </div>
        <div class="ledger">{active_change_rows(active_changes, output_file)}</div>
      </section>
    </div>

    <section class="section" aria-labelledby="archive-title">
      <div class="section-head">
        <h2 id="archive-title">归档历史</h2><p>展开后可查看 Change 工件</p>
      </div>
      <div class="archive-list">{archive_rows(archived_changes, output_file)}</div>
    </section>

    <p class="footer-note">
      本页面为只读派生产物。更新 OpenSpec 后重新执行
      <code>python tools/generate_openspec_dashboard.py</code>。
    </p>
  </main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成 OpenSpec 中文项目看板")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="项目根目录，默认根据脚本位置推导。",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="输出 HTML 路径，默认写入 openspec/dashboard/index.html。",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = args.root.resolve()
    output_file = (args.output or root / "openspec" / "dashboard" / "index.html").resolve()
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(render_dashboard(root, output_file), encoding="utf-8")
    print(f"已生成 OpenSpec 看板：{output_file}")


if __name__ == "__main__":
    main()
