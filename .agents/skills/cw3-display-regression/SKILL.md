---
name: cw3-display-regression
description: 对 CW3 译文、字体、材质、布局或点击修复选择定向验证，区分源码契约、运行时结构、实际画面与真实输入证据；CUA 仅作必要补充，不用于发布安装。
---

# CW3 显示变更回归

输入变更位置/提交、对应候选配置和已有问题证据。从仓库根目录读取 [AGENTS](../../../AGENTS.md)，核对原版、候选与已安装版本，避免用旧调试 DLL 或旧截图验证新源码。仅执行本次范围内的验证；skill 不新增权限或自动启动游戏、安装候选、启用调试、写存档、推送或发布。

## 先选需要证明的行为

优先源码、原版资源身份、IL 消费链和已有定向契约。按实际影响选择 [GuiCaptionContracts](../../../tests/GuiCaptionContracts.cs)、[NativeNoticeContracts](../../../tests/NativeNoticeContracts.cs)、[CaptionLayoutContracts](../../../tests/CaptionLayoutContracts.cs)、[RenderingOrderContracts](../../../tests/RenderingOrderContracts.cs) 或 [MainMenuClickContracts](../../../tests/MainMenuClickContracts.cs)；不要为文档/skill 修改重跑游戏套件。

检查中文宽度、换行、原生锚点与相邻状态行；材质要核对面板所有权、深度、裁切材质及动画引用，不能统一改绘制队列。点击修复要保留锁定、碰撞器和真实接收者，不能仅检查按钮文字。相关实现见 [CaptionLayout](../../../src/runtime/CaptionLayout.cs)、[CW3Rendering](../../../src/rendering/CW3Rendering.cs) 和 [MainMenuClickPatch](../../../src/runtime/MainMenuClickPatch.cs)。

| 证据 | 可以说明 | 不能代替 |
| --- | --- | --- |
| 源码/资源/契约 | 身份、消费链、尺寸规则及反向语义约束 | 当前画面和点击结果 |
| 运行时结构化状态 | 匹配/回退、字体选择、材质与控件状态、hook 执行 | 可见文字、遮挡和真实鼠标入口 |
| 当前画面 | 可见文字、换行、裁切和遮挡 | 真实点击后的行为 |
| 真实输入后的状态/画面 | 本次点击触发了预期行为 | 未操作的界面/关卡 |

## 结构检查与必要补充

已有匹配版本的调试模块且运行检查在授权范围内时，按 [debug.md](../../../docs/debug.md) 选只读查询：

```sh
python3 tools/debug.py command runtime_probe
python3 tools/debug.py command font_probe
python3 tools/debug.py command snapshot
python3 tools/debug.py command ui_probe
```

只运行与假设相关的查询。重放、菜单操作、加载等命令会改变游戏状态，不能当只读探测，也不能用它们成功冒充鼠标点击成功。请求超时先检查已有请求，不盲发重试。

CUA 不是默认强制门禁。只有画面或真实输入会改变结论且操作在范围内时才使用；从已观察到的现有正确窗口开始，绑定失败即停止该轮自动输入。仅在获得新的明确窗口信息后考虑重试，不换启动器、另开实例、循环绑定或改用未授权 OS 输入脚本。用户愿意自行验证时给一个最小动作及成功标准，不反复索要截图；已有截图注明对应版本和可证明范围。Library/CUA 的访问或上传仍服从各自权限与本次授权，不能通过 skill 绕过。

```sh
python3 tools/test.py --list
python3 tools/test.py --config local-only/independent-next/install-config.json \
  --suite GuiCaptionContracts --suite NativeNoticeContracts
```

`--suite` 可重复，名称去重，只运行所选 C# 套件及必要夹具，跳过 Python；消息候选套件仍包含其跨语言验证。省略 `--suite` 保留完整 Python/C# 运行。依赖按需准备，测试不会构建游戏候选；`ManagedDisplayContracts` 需要对应 `managed/render.dll`。定向执行范围更小，不代表同覆盖加速。已有检查通过后，只有新变更或未解风险才扩大验证。

## 结果与停止

报告已证实行为、证据层级、未验证项及下一项最小必要检查。结构成功但没有画面/真实输入时，保留“视觉/交互未验证”，不宣布修复已实测。静态检查请求可以止于静态结论；CUA 不可用也可完成其他证据，不能强迫用户操作。

原版身份、候选/调试哈希不符时停止相关执行；缺乏运行授权时止于静态分析。游戏运行时不换文件，存档和恢复点保持不动。构建、推送、发布、安装分别核对本次授权，不从验证自动进入交付。
