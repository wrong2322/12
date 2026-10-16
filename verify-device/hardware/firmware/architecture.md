# 边缘固件架构（装进 TVD-300 主机）

软件不是产品本体，而是箱内边缘计算机上的 **现场固件/应用**。

## 进程

1. `hal_daq`：超声模块、测厚、RS485/脉冲/mA、GNSS、相机驱动  
2. `sync_sampler`：统一时基窗口采样，写环形缓冲  
3. `rule_engine`：示值误差、相对偏差、强制违规（复用 `src/rules`）  
4. `model_orchestrator`：五角色本地推理（复用 `src/orchestrator`，provider=local_rules/NPU）  
5. `evidence_vault`：照片、采样摘要、工单 PDF/JSON，加密落盘  
6. `ui_field`：触控作业向导（非网站；本地 GUI）  
7. `print_export`：热敏打印 + U 盘导出  

## 作业状态机

`IDLE → SITE_CHECK(GNSS) → PIPE_PARAM → STD_INSTALL → DUT_LINK → SAMPLE → RECONCILE → EVIDENCE → PRINT → ARCHIVE`

## 与仓库代码关系

- 现有 `verify-device/src` 作为 **RECONCILE/模型编排** 核心库移植进机  
- HAL/UI/打印为新增嵌入式层（本目录仅定义接口，样机可用 Python+Qt/Flutter 嵌入式先跑通）

## 接口文件（样机）

现场一次作业产出目录示例：

```text
/vault/jobs/2025Q4/DEMO-SS-002/
  meta.json          # 户键、坐标、操作员
  samples.csv        # 同步采样
  reconcile.json     # 规则+模型结果
  photos/            # 铭牌/断面/铅封
  order.pdf          # 打印同款
  checksum.sig       # 完整性签名
```
