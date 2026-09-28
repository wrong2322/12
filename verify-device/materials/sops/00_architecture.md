# 架构说明

## 组件

```
                    ┌─────────────────────────┐
   脱敏/结构化输入 →│     Orchestrator        │→ outputs/*.json
                    │  rules_first = true     │→ audit.jsonl
                    └───────────┬─────────────┘
          ┌─────────┬───────────┼──────────┬──────────┐
          ▼         ▼           ▼          ▼          ▼
     extractor  reconciler  classifier dispatcher  auditor
     (model)    (rules+模型) (rules锁强制) (模型)    (模型)
```

## 数据契约

`src/schemas/records.py` 定义 UnifiedHousehold 与工单/审核结构，保证五角色输入输出可编排、可测试。

## 扩展新模型

1. 在 `config/models.yaml` 增加 provider。  
2. 在 `models/adapters.py` 实现 `ModelAdapter`。  
3. 保持强制违规由 `rules/engine.py` 产出。
