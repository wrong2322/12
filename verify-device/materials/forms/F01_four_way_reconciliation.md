# 表单 F01 — 四方对账底表（户级）

> 复制为县内工作表使用。真实数据仅保存在 `private/` 或内网系统。

| 字段 | 填写说明 | 示例（脱敏） |
|------|----------|--------------|
| 县域 | 实施单元 | 样例县B |
| 户键 | 内部唯一键 | DEMO-SS-002 |
| 许可编号 | 电子证照 | P-B-2002 |
| 取水口编码 | 与监测点对齐 | INT-B-002 |
| 统计名录ID | 直报名录 | ST-B-002 |
| 周期 | 对齐后的统计周期 | 2025-Q4 |
| 监测水量 m³ | 修正后优先 | 18500 |
| 直报水量 m³ | | 4477.5 |
| 纳税水量 m³ | | 4500 |
| 年许可水量 m³ | | 200000 |
| 直报vs监测偏差% | 自动或手算 | |
| 直报vs税费偏差% | | |
| 是否超5% | 是/否 | |
| 装表是否在法定断面 | 是/否 | |
| 转供入/出 m³ | 公共供水必填 | |
| 异常现象 | 跳表/离线/… | |
| 主办人 | | |
| 拟出口 | 见出口枚举 | |

CSV 头（可另存）：

```text
county,household_key,permit_id,intake_code,stat_roster_id,period,monitor_m3,direct_m3,tax_m3,quota_m3,dev_dm_pct,dev_dt_pct,over5,legal_section,transfer_in,transfer_out,flags,owner,exit_code
```
