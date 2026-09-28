# TVD-300 取水计量多方现场校验终端（实物设备）

本目录交付的是 **可研制的现场器物方案**：加固箱式校验终端 + 边缘固件，不是网页系统。

申报/真实台账仍只放本机 `private/`（gitignore），不入库。

## 先看这里

| 文档 | 内容 |
|------|------|
| [`hardware/PRODUCT.md`](hardware/PRODUCT.md) | 产品定义、与市面便携超声/RTU/信号源仪的差异 |
| [`hardware/bom/BOM_TVD300A.md`](hardware/bom/BOM_TVD300A.md) | 样机物料与费用量级 |
| [`hardware/mechanical/structure.md`](hardware/mechanical/structure.md) | 箱体分区与探头夹具 |
| [`hardware/electrical/architecture.md`](hardware/electrical/architecture.md) | 电气架构与同步采样 |
| [`hardware/patent/landscape_and_claims.md`](hardware/patent/landscape_and_claims.md) | 专利规避与可申请点 |
| [`hardware/prototype/build_plan.md`](hardware/prototype/build_plan.md) | 从黑盒联调→工程样机路线 |
| [`hardware/field_ops/SOP_field.md`](hardware/field_ops/SOP_field.md) | 现场操作指导书 |
| [`hardware/drawings/`](hardware/drawings/) | 爆炸/面板/电气示意图（SVG） |
| [`materials/PLAYBOOK.md`](materials/PLAYBOOK.md) | 器物级流程套路 |

## 设备做什么

1. **标准通道**：外夹时差超声，对比在用取水流量计  
2. **被检直采**：RS485 / 脉冲 / 4–20mA，核验“有监测≠监测可用”的链路  
3. **多方对齐**：许可 / 直报 / 税费摘要在机内对账（默认偏差阈 5%）  
4. **断面定位**：GNSS 核对是否法定取水口附近装表  
5. **边缘多模型**：规则优先 + 本地五角色编排，出销号建议与证据包  
6. **当场出单**：热敏打印 + 加密 U 盘导出（蜂窝默认物理关断）

## 边缘软件（装进箱子，不是网站）

`src/` 下的规则引擎与多模型编排，是主机内 `rule_engine` / `model_orchestrator` 的算法原型，可在无网环境跑通对账逻辑：

```bash
cd verify-device
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python src/cli.py samples/households_demo.json
python -m pytest tests -q
```

正式机载 UI 为本地触控向导，见 `hardware/firmware/architecture.md`。

## 隐私

见 [`PRIVACY.md`](PRIVACY.md)。原稿、实流原始波形、税务原文禁止入库与默认上云。
