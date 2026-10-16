"""CLI：本地跑通三方校验流水线（默认不外发数据）。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# 允许以 python -m 或直接脚本方式运行
ROOT = Path(__file__).resolve().parents[1]
SRC = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC))

from rich.console import Console
from rich.table import Table

from orchestrator.pipeline import Orchestrator
from schemas.records import UnifiedHousehold

console = Console()


def load_samples(path: Path) -> list[UnifiedHousehold]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [UnifiedHousehold.model_validate(x) for x in data]


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    sample = ROOT / "samples" / "households_demo.json"
    if argv:
        sample = Path(argv[0])
    if not sample.exists():
        console.print(f"[red]样例不存在: {sample}[/red]")
        return 1

    console.print("[bold]三方数据校验设备[/bold] · 多模型统筹 · 本地优先（数据不外发）")
    orch = Orchestrator()
    households = load_samples(sample)
    results = orch.run_batch(households)

    table = Table(title="校验结果一览")
    table.add_column("户键")
    table.add_column("县域")
    table.add_column("偏差超阈")
    table.add_column("分类码")
    table.add_column("工单")
    table.add_column("审核")
    for r in results:
        codes = ",".join(c.value for c in r.classification.codes)
        wo = r.work_order.order_id if r.work_order else "-"
        au = (
            ("通过" if r.audit.approved else "退回")
            if r.audit
            else ("无需" if not r.work_order else "-")
        )
        table.add_row(
            r.household.household_key,
            r.household.county,
            "是" if r.deviation.exceeds_threshold else "否",
            codes,
            wo,
            au,
        )
    console.print(table)
    console.print(f"明细已写入: {orch.output_dir}")
    console.print(f"审计日志: {orch.audit_log}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
