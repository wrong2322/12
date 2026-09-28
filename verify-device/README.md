# 三方数据校验设备（多模型统筹）

本地优先的取水计量 **许可 / 监测 / 直报 / 税费** 交叉校验编排器。  
默认使用 `local_rules`，**数据不外发**；真实材料放在仓库外的 `private/`（已 gitignore）。

## 快速开始

```bash
cd verify-device
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python src/cli.py samples/households_demo.json
```

查看：`outputs/` 单户结果、`outputs/batch_summary.json`、`outputs/audit.jsonl`。

## 流程套路（五段流水线）

```
抽取 extractor → 对账 reconciler（规则）→ 分类 classifier
        → 派单 dispatcher → 审核 auditor → 销号/退回
```

硬规则见 `config/thresholds.yaml`（默认相对偏差 5%、强制违规码不可被模型覆盖）。

## 内容材料索引

| 类型 | 路径 |
|------|------|
| 总规程 | `materials/sops/01_master_process.md` |
| 公共供水闭合 | `materials/sops/02_public_supply_closure.md` |
| 规上协同销号 | `materials/sops/03_self_supply_collaborative_closure.md` |
| 核算-公报衔接 | `materials/sops/04_accounting_bulletin_link.md` |
| 对账/转供/证据表单 | `materials/forms/` |
| 检查清单 | `materials/checklists/` |
| 工单模板 | `materials/work_orders/` |
| 角色提示词 | `prompts/*.md` |
| 脱敏样例 | `samples/households_demo.json` |

## 切换真实模型（可选）

1. 复制 `.env.example` → `.env`（勿提交）。  
2. `config/models.yaml` 将对应 role 的 `provider` 改为 `openai_compatible`。  
3. 保持 `send_raw_records: false`。

## 隐私

详见 [PRIVACY.md](./PRIVACY.md)。原稿、真实台账、导出包 **禁止 push**。

## 测试

```bash
cd verify-device && python -m pytest tests -q
```
