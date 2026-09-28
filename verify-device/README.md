# TVD-Gate / TVD-300

## 主方案（你要的）：现场加装 → 常驻三方校验

见 **[`hardware/addon/PRODUCT_ADDON.md`](hardware/addon/PRODUCT_ADDON.md)**  

**TVD-Gate**：取水口加装「外夹核查表 + 原表只听分接 + 校验控制器」，7×24 做  
`独立计量 ↔ 监测镜像 ↔ 直报/税费` 三方校验（许可作约束）。  
不是派人到场比测。

| 文档 | 路径 |
|------|------|
| 加装产品定义 | `hardware/addon/PRODUCT_ADDON.md` |
| 安装工艺 | `hardware/addon/install/INSTALL.md` |
| 电气 | `hardware/addon/electrical/architecture.md` |
| 单点 BOM | `hardware/addon/bom/BOM_GATE_S.md` |
| 拓扑图 | `hardware/addon/drawings/gate_topology.svg` |
| 专利差异 | `hardware/addon/patent/notes.md` |
| 流程一页纸 | `materials/PLAYBOOK.md` |

## 辅方案：便携比测箱 TVD-300

仅用于抽检、验收、对 Gate 核查通道复核。见 `hardware/PRODUCT.md`（降级为运维工具）。

## 箱内/汇聚端算法原型

`src/` 规则与多模型编排可部署在 Gate 控制器或县级汇聚机，默认本地、不外发原始台账。

```bash
cd verify-device && source .venv/bin/activate
python src/cli.py samples/households_demo.json
```

## 隐私

真实申报材料只放本机 `private/`（gitignore）。见 `PRIVACY.md`。
