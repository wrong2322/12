"""端到端与规则引擎测试（全部使用脱敏合成数据）。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from orchestrator.pipeline import Orchestrator
from rules.engine import load_thresholds, reconcile_household, relative_deviation
from schemas.records import AnomalyCode, UnifiedHousehold


def test_relative_deviation_basic():
    assert abs(relative_deviation(100, 115) - 13.043478) < 0.01


def test_demo_batch_produces_expected_patterns():
    orch = Orchestrator()
    data = json.loads((ROOT / "samples" / "households_demo.json").read_text(encoding="utf-8"))
    households = [UnifiedHousehold.model_validate(x) for x in data]
    results = orch.run_batch(households)
    assert len(results) == 4

    by_key = {r.household.household_key: r for r in results}

    r1 = by_key["DEMO-PS-001"]
    assert r1.deviation.exceeds_threshold
    assert AnomalyCode.SOURCE_METER_MISPLACE in r1.classification.codes
    assert r1.work_order is not None

    r2 = by_key["DEMO-SS-002"]
    assert r2.classification.mandatory
    assert AnomalyCode.PERMIT_EXPIRED in r2.classification.codes
    assert r2.work_order is not None

    r3 = by_key["DEMO-SS-003"]
    assert AnomalyCode.WITHIN_THRESHOLD in r3.classification.codes
    assert r3.work_order is None

    r4 = by_key["DEMO-SS-004"]
    assert AnomalyCode.ID_MISMATCH in r4.classification.codes
    assert r4.deviation.exceeds_threshold


def test_thresholds_file_loads():
    thr = load_thresholds(ROOT / "config" / "thresholds.yaml")
    assert thr["relative_deviation_pct"] == 5.0
    assert "PERMIT_EXPIRED" in thr["mandatory_violation_codes"]


def test_reconcile_over_permit():
    thr = load_thresholds(ROOT / "config" / "thresholds.yaml")
    h = UnifiedHousehold.model_validate(
        {
            "household_key": "T-1",
            "county": "样例县",
            "use_type": "self_supply",
            "permit": {
                "permit_id": "P",
                "intake_code": "I",
                "holder_name": "X",
                "use_type": "self_supply",
                "annual_quota_m3": 1200,
                "valid_from": "2024-01-01",
                "valid_to": "2029-01-01",
                "status": "active",
                "county": "样例县",
            },
            "monitor": {
                "intake_code": "I",
                "period": "2025-01",
                "volume_m3": 500,
            },
            "direct_report": {
                "stat_roster_id": "S",
                "intake_code": "I",
                "period": "2025-01",
                "volume_m3": 500,
                "reporter": "X",
            },
        }
    )
    # 月配额 100（年1200/12），监测 500 → 超许可
    dev = reconcile_household(h, thr)
    assert dev.over_permit_meter is True
    assert dev.details["period_quota_estimate_m3"] == 100.0
