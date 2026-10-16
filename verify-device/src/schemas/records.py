"""统一数据契约：许可 / 监测 / 直报 / 税费 四方字段。"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class WaterUseType(str, Enum):
    PUBLIC_SUPPLY = "public_supply"  # 城镇/农村公共供水
    SELF_SUPPLY = "self_supply"  # 规上自备
    AGRICULTURE = "agriculture"
    OTHER = "other"


class AnomalyCode(str, Enum):
    JUMP_METER = "JUMP_METER"
    DEVICE_OFFLINE = "DEVICE_OFFLINE"
    ABNORMAL_SPIKE = "ABNORMAL_SPIKE"
    FLOWMETER_FAULT = "FLOWMETER_FAULT"
    OUTAGE_UNMARKED = "OUTAGE_UNMARKED"
    OVER_PERMIT_METER = "OVER_PERMIT_METER"
    OVER_PERMIT_STAT = "OVER_PERMIT_STAT"
    PERMIT_EXPIRED = "PERMIT_EXPIRED"
    OVER_CONTROL_INDEX = "OVER_CONTROL_INDEX"
    SOURCE_METER_MISPLACE = "SOURCE_METER_MISPLACE"
    TRANSFER_IMBALANCE = "TRANSFER_IMBALANCE"
    PERIOD_MISALIGN = "PERIOD_MISALIGN"
    ID_MISMATCH = "ID_MISMATCH"
    WITHIN_THRESHOLD = "WITHIN_THRESHOLD"
    UNKNOWN = "UNKNOWN"


class Severity(str, Enum):
    INFO = "info"
    WARN = "warn"
    HIGH = "high"
    CRITICAL = "critical"


class ClosureExit(str, Enum):
    CORRECT_DIRECT_REPORT = "CORRECT_DIRECT_REPORT"
    REQUEST_TAX_REVIEW = "REQUEST_TAX_REVIEW"
    ADJUST_PERMIT_OR_PLAN = "ADJUST_PERMIT_OR_PLAN"
    FIX_METER_OR_SIGNAL = "FIX_METER_OR_SIGNAL"
    UPDATE_TRANSFER_RELATION = "UPDATE_TRANSFER_RELATION"
    MARK_OUTAGE_OR_MAINT = "MARK_OUTAGE_OR_MAINT"
    ARCHIVE_EXPLAIN_ONLY = "ARCHIVE_EXPLAIN_ONLY"


class PermitRecord(BaseModel):
    permit_id: str
    intake_code: str
    holder_name: str
    use_type: WaterUseType
    annual_quota_m3: float
    valid_from: str
    valid_to: str
    status: str = "active"  # active | expired | revoked
    county: str


class MonitorRecord(BaseModel):
    intake_code: str
    period: str  # YYYY-MM 或 YYYY-Qn
    volume_m3: float
    corrected_volume_m3: Optional[float] = None
    signal_type: str = "digital"  # digital | analog
    online_rate_pct: float = 100.0
    flags: list[str] = Field(default_factory=list)


class DirectReportRecord(BaseModel):
    stat_roster_id: str
    intake_code: str
    period: str
    volume_m3: float
    reporter: str


class TaxRecord(BaseModel):
    tax_period: str
    intake_code: str
    taxable_volume_m3: float
    taxpayer: str
    review_requested: bool = False


class UnifiedHousehold(BaseModel):
    """抽取模型输出的统一户级对象。"""

    household_key: str
    county: str
    use_type: WaterUseType
    permit: Optional[PermitRecord] = None
    monitor: Optional[MonitorRecord] = None
    direct_report: Optional[DirectReportRecord] = None
    tax: Optional[TaxRecord] = None
    transfer_in_m3: float = 0.0
    transfer_out_m3: float = 0.0
    meter_at_legal_section: bool = True
    notes: list[str] = Field(default_factory=list)


class DeviationResult(BaseModel):
    household_key: str
    period: str
    monitor_m3: Optional[float] = None
    direct_m3: Optional[float] = None
    tax_m3: Optional[float] = None
    permit_quota_m3: Optional[float] = None
    direct_vs_monitor_pct: Optional[float] = None
    direct_vs_tax_pct: Optional[float] = None
    monitor_vs_tax_pct: Optional[float] = None
    over_permit_meter: bool = False
    over_permit_stat: bool = False
    transfer_imbalance_m3: Optional[float] = None
    exceeds_threshold: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class ClassificationResult(BaseModel):
    household_key: str
    codes: list[AnomalyCode]
    severity: Severity
    rationale: str
    mandatory: bool = False


class WorkOrderDraft(BaseModel):
    order_id: str
    household_key: str
    county: str
    codes: list[AnomalyCode]
    severity: Severity
    lead_org: str
    support_orgs: list[str] = Field(default_factory=list)
    due_days: int
    suggested_exits: list[ClosureExit]
    checklist: list[str]
    summary: str


class AuditVerdict(BaseModel):
    order_id: str
    approved: bool
    missing_items: list[str] = Field(default_factory=list)
    recommended_exit: Optional[ClosureExit] = None
    comment: str = ""


class PipelineResult(BaseModel):
    household: UnifiedHousehold
    deviation: DeviationResult
    classification: ClassificationResult
    work_order: Optional[WorkOrderDraft] = None
    audit: Optional[AuditVerdict] = None

    @field_validator("household")
    @classmethod
    def _nonempty_key(cls, v: UnifiedHousehold) -> UnifiedHousehold:
        if not v.household_key:
            raise ValueError("household_key required")
        return v
