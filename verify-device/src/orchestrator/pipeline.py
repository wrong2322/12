"""多模型统筹流水线：抽取 → 对账 → 分类 → 派单 → 审核。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from models.adapters import build_adapter, ensure_rule_outputs, load_model_config
from rules.engine import load_thresholds
from schemas.records import (
    AnomalyCode,
    PipelineResult,
    UnifiedHousehold,
    WorkOrderDraft,
)


class Orchestrator:
    def __init__(self, config_dir: Path | None = None):
        root = Path(__file__).resolve().parents[2]
        self.root = root
        self.thr = load_thresholds(root / "config" / "thresholds.yaml")
        self.mcfg = load_model_config(root / "config" / "models.yaml")
        out = root / self.mcfg["orchestration"]["output_dir"]
        out.mkdir(parents=True, exist_ok=True)
        self.output_dir = out
        self.audit_log = root / self.mcfg["orchestration"]["audit_log"]
        self.audit_log.parent.mkdir(parents=True, exist_ok=True)
        self.adapters = {role: build_adapter(role, self.mcfg) for role in self.mcfg["roles"]}

    def _audit_write(self, event: str, data: dict[str, Any]) -> None:
        rec = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "data": data,
        }
        with self.audit_log.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def run_one(
        self,
        household: UnifiedHousehold,
        seq: str = "001",
        submitted_evidence: list[str] | None = None,
    ) -> PipelineResult:
        # 1) 抽取角色：输入已是结构化时透传；也可接受 dict
        extracted = self.adapters["extractor"].run({"household": household.model_dump(mode="json")})
        h = UnifiedHousehold.model_validate(extracted)
        self._audit_write("extract", {"household_key": h.household_key})

        # 2) 规则优先对账 + 分类
        dev, cls = ensure_rule_outputs(h, self.thr)
        # 3) 模型复核分类（不可消除 mandatory）
        cls_model = self.adapters["classifier"].run(
            {
                "household": h.model_dump(mode="json"),
                "deviation": dev.model_dump(mode="json"),
                "classification": cls.model_dump(mode="json"),
            }
        )
        from schemas.records import ClassificationResult

        cls2 = ClassificationResult.model_validate(cls_model)
        if cls.mandatory:
            # 强制码不可被模型删掉
            merged = list({*cls.codes, *cls2.codes})
            cls2.codes = merged
            cls2.mandatory = True
            cls2.severity = cls.severity

        # reconciler 角色留痕（规则结果为主）
        self.adapters["reconciler"].run({"deviation": dev.model_dump(mode="json")})
        self._audit_write(
            "reconcile_classify",
            {"household_key": h.household_key, "codes": [c.value for c in cls2.codes]},
        )

        work_order = None
        audit = None
        if AnomalyCode.WITHIN_THRESHOLD not in cls2.codes or cls2.mandatory or dev.exceeds_threshold:
            if not (len(cls2.codes) == 1 and cls2.codes[0] == AnomalyCode.WITHIN_THRESHOLD):
                wo_raw = self.adapters["dispatcher"].run(
                    {
                        "household": h.model_dump(mode="json"),
                        "deviation": dev.model_dump(mode="json"),
                        "classification": cls2.model_dump(mode="json"),
                        "seq": seq,
                    }
                )
                work_order = WorkOrderDraft.model_validate(wo_raw)
                self._audit_write("dispatch", {"order_id": work_order.order_id})

                evidence = submitted_evidence or []
                audit_raw = self.adapters["auditor"].run(
                    {
                        "work_order": work_order.model_dump(mode="json"),
                        "submitted_evidence": evidence,
                    }
                )
                from schemas.records import AuditVerdict

                audit = AuditVerdict.model_validate(audit_raw)
                self._audit_write(
                    "audit",
                    {"order_id": audit.order_id, "approved": audit.approved},
                )

        result = PipelineResult(
            household=h,
            deviation=dev,
            classification=cls2,
            work_order=work_order,
            audit=audit,
        )
        out_path = self.output_dir / f"{h.household_key}_{seq}.json"
        out_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
        return result

    def run_batch(self, households: Iterable[UnifiedHousehold]) -> list[PipelineResult]:
        results: list[PipelineResult] = []
        for i, h in enumerate(households, start=1):
            results.append(self.run_one(h, seq=f"{i:03d}"))
        summary = {
            "total": len(results),
            "work_orders": sum(1 for r in results if r.work_order),
            "mandatory": sum(1 for r in results if r.classification.mandatory),
            "within_threshold": sum(
                1
                for r in results
                if AnomalyCode.WITHIN_THRESHOLD in r.classification.codes
                and not r.classification.mandatory
            ),
        }
        (self.output_dir / "batch_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        self._audit_write("batch_done", summary)
        return results
