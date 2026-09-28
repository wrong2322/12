"""确定性规则引擎：阈值与强制违规，模型不得覆盖。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from schemas.records import (
    AnomalyCode,
    ClassificationResult,
    DeviationResult,
    Severity,
    UnifiedHousehold,
)


def load_thresholds(path: Path | None = None) -> dict[str, Any]:
    cfg = path or Path(__file__).resolve().parents[2] / "config" / "thresholds.yaml"
    with cfg.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def relative_deviation(a: float | None, b: float | None) -> float | None:
    if a is None or b is None:
        return None
    denom = max(abs(a), abs(b), 1e-9)
    return abs(a - b) / denom * 100.0


def period_quota_share(annual_quota: float, period: str) -> float:
    """按周期分摊年许可：Qn→/4，YYYY-MM→/12，其他→整年。正式环境应改用计划用水指标。"""
    p = (period or "").upper()
    if "-Q" in p or p.endswith("Q1") or p.endswith("Q2") or p.endswith("Q3") or p.endswith("Q4"):
        return annual_quota / 4.0
    if len(p) >= 7 and p[4] == "-":
        return annual_quota / 12.0
    return annual_quota


def reconcile_household(h: UnifiedHousehold, thr: dict[str, Any]) -> DeviationResult:
    mon = h.monitor.volume_m3 if h.monitor else None
    if h.monitor and h.monitor.corrected_volume_m3 is not None:
        mon = h.monitor.corrected_volume_m3
    direct = h.direct_report.volume_m3 if h.direct_report else None
    tax = h.tax.taxable_volume_m3 if h.tax else None
    quota = h.permit.annual_quota_m3 if h.permit else None
    period = (
        (h.direct_report.period if h.direct_report else None)
        or (h.monitor.period if h.monitor else None)
        or (h.tax.tax_period if h.tax else "unknown")
    )
    period_quota = period_quota_share(quota, period) if quota is not None else None

    d_m = relative_deviation(direct, mon)
    d_t = relative_deviation(direct, tax)
    m_t = relative_deviation(mon, tax)
    limit = float(thr["relative_deviation_pct"])

    over_meter = bool(period_quota is not None and mon is not None and mon > period_quota)
    over_stat = bool(period_quota is not None and direct is not None and direct > period_quota)

    transfer_gap = None
    if h.use_type.value == "public_supply":
        transfer_gap = abs((h.transfer_in_m3 or 0) - (h.transfer_out_m3 or 0))

    exceeds = any(
        x is not None and x > limit for x in (d_m, d_t, m_t)
    ) or over_meter or over_stat

    return DeviationResult(
        household_key=h.household_key,
        period=period,
        monitor_m3=mon,
        direct_m3=direct,
        tax_m3=tax,
        permit_quota_m3=quota,
        direct_vs_monitor_pct=d_m,
        direct_vs_tax_pct=d_t,
        monitor_vs_tax_pct=m_t,
        over_permit_meter=over_meter,
        over_permit_stat=over_stat,
        transfer_imbalance_m3=transfer_gap,
        exceeds_threshold=exceeds,
        details={
            "threshold_pct": limit,
            "meter_at_legal_section": h.meter_at_legal_section,
            "permit_status": h.permit.status if h.permit else None,
            "period_quota_estimate_m3": period_quota,
        },
    )


def rule_classify(h: UnifiedHousehold, dev: DeviationResult, thr: dict[str, Any]) -> ClassificationResult:
    codes: list[AnomalyCode] = []
    notes: list[str] = []

    if h.permit and h.permit.status == "expired":
        codes.append(AnomalyCode.PERMIT_EXPIRED)
        notes.append("证照状态为 expired，仍存在取水记录")

    if not h.meter_at_legal_section:
        codes.append(AnomalyCode.SOURCE_METER_MISPLACE)
        notes.append("计量表未安装在法定取水断面")

    if h.monitor:
        flags = set(h.monitor.flags or [])
        mapping = {
            "jump": AnomalyCode.JUMP_METER,
            "offline": AnomalyCode.DEVICE_OFFLINE,
            "spike": AnomalyCode.ABNORMAL_SPIKE,
            "fault": AnomalyCode.FLOWMETER_FAULT,
            "outage_unmarked": AnomalyCode.OUTAGE_UNMARKED,
        }
        for k, code in mapping.items():
            if k in flags:
                codes.append(code)
        if (
            h.monitor.corrected_volume_m3 is not None
            and h.monitor.volume_m3 > 0
            and abs(h.monitor.corrected_volume_m3) / max(abs(h.monitor.volume_m3), 1e-9)
            >= float(thr["monitor_correction_order_of_magnitude"])
        ):
            codes.append(AnomalyCode.ABNORMAL_SPIKE)
            notes.append("监测修正前后相差达到数量级")

    if dev.over_permit_meter:
        codes.append(AnomalyCode.OVER_PERMIT_METER)
    if dev.over_permit_stat:
        codes.append(AnomalyCode.OVER_PERMIT_STAT)

    if (
        h.use_type.value == "public_supply"
        and dev.transfer_imbalance_m3 is not None
        and dev.transfer_imbalance_m3 > 0
        and (
            (dev.direct_vs_monitor_pct or 0) > float(thr["public_supply_balance_pct"])
            or abs(dev.transfer_imbalance_m3) > 0
        )
    ):
        # 转供差额显著或闭合偏差超阈值
        if (dev.direct_vs_monitor_pct or 0) > float(thr["public_supply_balance_pct"]) or abs(
            (h.transfer_in_m3 or 0) - (h.transfer_out_m3 or 0)
        ) > max((dev.monitor_m3 or 0) * 0.05, 100):
            codes.append(AnomalyCode.TRANSFER_IMBALANCE)

    # 名录/证照/取水口编码不一致风险
    if h.permit and h.monitor and h.permit.intake_code != h.monitor.intake_code:
        codes.append(AnomalyCode.ID_MISMATCH)
    if h.direct_report and h.permit and h.direct_report.intake_code != h.permit.intake_code:
        codes.append(AnomalyCode.ID_MISMATCH)

    if not codes and not dev.exceeds_threshold:
        codes.append(AnomalyCode.WITHIN_THRESHOLD)
        notes.append("各方相对偏差未超阈值，且无强制违规线索")
    elif not codes and dev.exceeds_threshold:
        codes.append(AnomalyCode.UNKNOWN)
        notes.append("偏差超阈值，但规则未能归类具体原因，交模型补充研判")

    mandatory_set = set(thr.get("mandatory_violation_codes", []))
    mandatory = any(c.value in mandatory_set for c in codes)

    if mandatory:
        severity = Severity.CRITICAL
    elif AnomalyCode.ABNORMAL_SPIKE in codes or AnomalyCode.TRANSFER_IMBALANCE in codes:
        severity = Severity.HIGH
    elif dev.exceeds_threshold:
        severity = Severity.WARN
    else:
        severity = Severity.INFO

    return ClassificationResult(
        household_key=h.household_key,
        codes=codes,
        severity=severity,
        rationale="；".join(notes) if notes else "规则引擎分类完成",
        mandatory=mandatory,
    )
