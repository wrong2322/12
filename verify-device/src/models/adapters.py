"""模型适配器：本地规则推理 + OpenAI 兼容接口（默认不外发原始台账）。"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import yaml

from rules.engine import reconcile_household, rule_classify
from schemas.records import (
    AnomalyCode,
    AuditVerdict,
    ClassificationResult,
    ClosureExit,
    DeviationResult,
    Severity,
    UnifiedHousehold,
    WorkOrderDraft,
)


class ModelAdapter(ABC):
    role: str

    @abstractmethod
    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError


def load_model_config(path: Path | None = None) -> dict[str, Any]:
    cfg = path or Path(__file__).resolve().parents[2] / "config" / "models.yaml"
    with cfg.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


class LocalRulesAdapter(ModelAdapter):
    """离线演示适配器：基于规则+模板生成结构化输出，数据不出本机。"""

    def __init__(self, role: str):
        self.role = role

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self.role == "extractor":
            return payload["household"]
        if self.role == "reconciler":
            return payload["deviation"]
        if self.role == "classifier":
            base: ClassificationResult = ClassificationResult.model_validate(payload["classification"])
            # 模型补充：对 UNKNOWN 给出倾向性说明（仍不改强制码）
            if AnomalyCode.UNKNOWN in base.codes:
                base.rationale += "；建议优先核对抄表周期与监测累计周期是否错位"
            return base.model_dump(mode="json")
        if self.role == "dispatcher":
            return self._dispatch(payload)
        if self.role == "auditor":
            return self._audit(payload)
        raise ValueError(f"unknown role: {self.role}")

    def _dispatch(self, payload: dict[str, Any]) -> dict[str, Any]:
        h = UnifiedHousehold.model_validate(payload["household"])
        cls = ClassificationResult.model_validate(payload["classification"])
        exits: list[ClosureExit] = []
        checklist: list[str] = [
            "核对电子证照、取水口编码、统计名录三者一致性",
            "核对抄表周期、监测累计周期、税期是否对齐",
            "留存原始读数、修正记录与现场照片/校验报告",
        ]
        if AnomalyCode.SOURCE_METER_MISPLACE in cls.codes:
            exits.append(ClosureExit.FIX_METER_OR_SIGNAL)
            checklist.append("确认法定取水断面装表或完善漏损计入手续")
        if AnomalyCode.TRANSFER_IMBALANCE in cls.codes:
            exits.append(ClosureExit.UPDATE_TRANSFER_RELATION)
            checklist.append("填写县域转供对账表并完成闭合复核")
        if AnomalyCode.OVER_PERMIT_METER in cls.codes or AnomalyCode.OVER_PERMIT_STAT in cls.codes:
            exits.append(ClosureExit.ADJUST_PERMIT_OR_PLAN)
            checklist.append("启动许可/计划用水指标依法调整或查处程序")
        if AnomalyCode.PERMIT_EXPIRED in cls.codes:
            exits.append(ClosureExit.ADJUST_PERMIT_OR_PLAN)
            checklist.append("证照失效查处并停止违法取水")
        if any(
            c in cls.codes
            for c in (
                AnomalyCode.JUMP_METER,
                AnomalyCode.DEVICE_OFFLINE,
                AnomalyCode.FLOWMETER_FAULT,
                AnomalyCode.ABNORMAL_SPIKE,
            )
        ):
            exits.append(ClosureExit.FIX_METER_OR_SIGNAL)
        if AnomalyCode.OUTAGE_UNMARKED in cls.codes:
            exits.append(ClosureExit.MARK_OUTAGE_OR_MAINT)
        if payload.get("deviation", {}).get("direct_vs_monitor_pct") or payload.get(
            "deviation", {}
        ).get("direct_vs_tax_pct"):
            exits.append(ClosureExit.CORRECT_DIRECT_REPORT)
            exits.append(ClosureExit.REQUEST_TAX_REVIEW)

        # 去重保序
        seen: set[str] = set()
        uniq_exits: list[ClosureExit] = []
        for e in exits:
            if e.value not in seen:
                seen.add(e.value)
                uniq_exits.append(e)
        if not uniq_exits and cls.codes == [AnomalyCode.WITHIN_THRESHOLD]:
            uniq_exits = []

        lead = "县级水行政主管部门"
        support = ["取用水户/供水企业"]
        if ClosureExit.REQUEST_TAX_REVIEW in uniq_exits:
            support.append("税务机关（跨部门复核）")
        if AnomalyCode.TRANSFER_IMBALANCE in cls.codes:
            support.append("市级（跨区域事项核实）")

        due = 15 if cls.mandatory else (10 if cls.severity in (Severity.HIGH, Severity.CRITICAL) else 20)
        summary = (
            f"【{h.county}】{h.household_key} 触发 {','.join(c.value for c in cls.codes)}；"
            f"建议出口：{','.join(e.value for e in uniq_exits) or '无需工单'}"
        )
        order = WorkOrderDraft(
            order_id=f"WO-{h.county}-{h.household_key}-{payload.get('seq', '001')}",
            household_key=h.household_key,
            county=h.county,
            codes=cls.codes,
            severity=cls.severity,
            lead_org=lead,
            support_orgs=support,
            due_days=due,
            suggested_exits=uniq_exits,
            checklist=checklist,
            summary=summary,
        )
        return order.model_dump(mode="json")

    def _audit(self, payload: dict[str, Any]) -> dict[str, Any]:
        order = WorkOrderDraft.model_validate(payload["work_order"])
        submitted = set(payload.get("submitted_evidence", []))
        required = set(order.checklist)
        missing = sorted(required - submitted)
        approved = len(missing) == 0 and (
            AnomalyCode.WITHIN_THRESHOLD in order.codes or bool(order.suggested_exits)
        )
        # 强制违规必须有对应出口，禁止“仅说明”
        if order.severity == Severity.CRITICAL and ClosureExit.ARCHIVE_EXPLAIN_ONLY in order.suggested_exits:
            approved = False
            missing.append("强制违规不得以 ARCHIVE_EXPLAIN_ONLY 销号")
        verdict = AuditVerdict(
            order_id=order.order_id,
            approved=approved,
            missing_items=missing,
            recommended_exit=order.suggested_exits[0] if order.suggested_exits else None,
            comment="材料齐全，允许销号" if approved else "材料不齐或出口不合规，退回补正",
        )
        return verdict.model_dump(mode="json")


class OpenAICompatibleAdapter(ModelAdapter):
    """可选云端模型。默认仅发送结构化摘要，禁止 send_raw_records。"""

    def __init__(self, role: str, model: str, base_url: str, api_key: str, send_raw: bool = False):
        self.role = role
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.send_raw = send_raw

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.send_raw and "raw_text" in payload:
            payload = {k: v for k, v in payload.items() if k != "raw_text"}
        # 未配置密钥时回退本地
        if not self.api_key:
            return LocalRulesAdapter(self.role).run(payload)
        try:
            import httpx
        except ImportError as e:
            raise RuntimeError("httpx required for openai_compatible provider") from e

        prompt_path = Path(__file__).resolve().parents[2] / "prompts" / f"{self.role}.md"
        system = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else f"You are {self.role}."
        body = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            "response_format": {"type": "json_object"},
        }
        with httpx.Client(timeout=60) as client:
            r = client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=body,
            )
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]
            return json.loads(content)


def build_adapter(role: str, cfg: dict[str, Any] | None = None) -> ModelAdapter:
    cfg = cfg or load_model_config()
    role_cfg = cfg["roles"][role]
    provider_name = role_cfg.get("provider") or cfg["default_provider"]
    provider = cfg["providers"][provider_name]
    ptype = provider["type"]
    if ptype == "local_rules":
        return LocalRulesAdapter(role)
    if ptype == "openai_compatible":
        return OpenAICompatibleAdapter(
            role=role,
            model=role_cfg.get("model") or provider.get("default_model", "gpt-4o-mini"),
            base_url=os.getenv(provider.get("base_url_env", "VERIFY_BASE_URL"), "https://api.openai.com/v1"),
            api_key=os.getenv(provider.get("api_key_env", "VERIFY_API_KEY"), ""),
            send_raw=bool(provider.get("send_raw_records", False)),
        )
    raise ValueError(f"unsupported provider type: {ptype}")


def ensure_rule_outputs(
    household: UnifiedHousehold, thr: dict[str, Any]
) -> tuple[DeviationResult, ClassificationResult]:
    """规则优先：对账与强制分类在调用模型前完成。"""
    dev = reconcile_household(household, thr)
    cls = rule_classify(household, dev, thr)
    return dev, cls
