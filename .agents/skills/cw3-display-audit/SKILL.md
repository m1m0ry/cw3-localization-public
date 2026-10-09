---
name: cw3-display-audit
description: 定位 CW3 漏译、错位绑定或新增显示目标，核对原版资源身份和 IL 消费链，判断是否需要显示 hook；不用于仅修改已有译文或发布安装。
---

# CW3 显示目标审计

从仓库根目录工作，读取 [AGENTS](../../../AGENTS.md) 和任务采用的配置。输入可为原文、现有截图、候选快照或资源/方法位置；先确认当前源码与问题对应版本，不把旧记录当现状。遵守本次任务范围；skill 不授权启动游戏、启用调试、调用翻译服务、推送、发布、安装或外部上传。

## 定位与判断

- 先搜 `translations/zh-CN.json`，区别译文错误、绑定缺失、原文漂移和渲染问题。同一句可能有不同显示位置，已绑定译文只需修改 `translation`；新增目标需要源码证据与基础补丁重建。
- 资源路径核对原版文件/哈希、资源键、对象身份和 XML 路径；名称按已支持的 GUID/所有者身份绑定。脚本检查指纹、调用序号、行号和完整输出模板，不能把模型或存档里的文字当可改显示数据。
- 原生代码沿实际调用追到 UILabel、InfoPanel、GUI/GUILayout 等消费者，检查返回值、局部变量、Concat、Format、条件分支与参数位置。证明正常入口可达；未使用的类、示例组件或编辑器文本不能仅凭英文认定漏译。
- [GuiCaptionAudit](../../../src/runtime/GuiCaptionAudit.cs) 拒绝模型写入、比较和未知消费者；[NativeEventCaptionAudit](../../../src/runtime/NativeEventCaptionAudit.cs) 区分事件文字和图标键。身份、状态、回调、资源键及未知字符串参数不翻译。复用现有显示边界，只有证实新路径未覆盖时才讨论最小 hook；不做全局替换或任意文本通配。

## 按需工具

```sh
python3 tools/audit_campaign.py --config config.local.json
python3 tools/audit_managed_display.py \
  --config local-only/independent-next/install-config.json \
  --output local-only/managed-review-new.json
# 仅使用已提供的候选，不为审计自动打开采集或游戏
python3 tools/candidates.py export /path/to/candidates.json --output local-only/review-new.json
python3 tools/workflow.py check
```

战役审计只覆盖固定官方资源/脚本；候选受采集挂钩和上限限制。`candidates.py merge` 仅接受已绑定且审核通过的缺译文，不能生成新身份。目标锁由维护者依据原版证据更新，不为通过检查重生成整个锁文件。实际字体 cmap 与固定来源按[构建文档](../../../docs/build.md)核对。

IL 清单枚举原版全部 `ldstr`，分为 `bound`、`display_candidate`、`internal_identifier`、`unknown`，记录原版 SHA、token/指令索引、消费者及理由。`bound` 仅表示现有声明与源位置校验通过，`analysis` 保留独立消费链结论；未知不能当内部键，候选不能自动翻译。v10 按精确方法签名和完整字面量序列映射回原版，漂移会拒绝。配置须指向含 `managed/render.dll` 的独立候选，或显式提供匹配的 `--render`；工具不会构建输入。反射、外部数据、无字面量生成的字符串及正常游戏可达性仍需另外核实。

## 产出与停止

简短给出可达入口、源身份/消费者证据、建议复用的边界、采用目标或保留原文的原因，以及审计范围和未覆盖场景。证据保存在 `local-only`，不上传游戏原件、存档或私人记录。

身份/原文不符、消费者混用、入口无法证明或必需输入缺失时，停止该目标的修改并说明缺口，继续不依赖它的工作。扫描无缺项只证明该范围，不能宣布全游戏零漏译。排版或交互变化再用 [cw3-display-regression](../cw3-display-regression/SKILL.md)。
