# 可选调试接口

Windows 的独立调试模块用于开发时检查场景、字体、材质和显示文本，默认关闭，不随发行包提供。启用和停用时必须退出游戏，工具会核对程序集 SHA。原生 Mac 使用常驻但默认关闭的固定接口，见下节。

```sh
python3 tools/build_managed.py --debug
python3 tools/debug.py enable
# 启动游戏后查询
python3 tools/debug.py command snapshot
# 退出游戏后停用
python3 tools/debug.py disable
```

支持的命令：

| 命令 | 参数 | 用途 |
| --- | --- | --- |
| `discovery_probe` | 无 | 候选采集开关、计数、写盘及局部耗时 |
| `runtime_probe` / `font_probe` | 无 | 外部候选的绑定/词典计数、原文 fallback 与实际字体选择 |
| `load_auto` / `restart_mission` | 无 | Tempus 正常加载界面中的自动读取/重开；保留锁定与碰撞器前置检查 |
| `load_slot` | `0` | 从 Tempus 加载界面读取 0 槽 |
| `ui_probe` | 无 | 当前鼠标命中、首页锁定、弹窗矩形与 GUI 字号；附最近一次首页点击，只读 |
| `snapshot` | 无 | 场景、字体、材质所有权/淡入引用状态及原始/绘制文本 |
| `menu_open` / `menu_close` | 无 | 打开或关闭游戏菜单 |
| `archive_open` / `archive_next` / `archive_close` / `message_probe` | 无 | Gal 正常归档打开、翻页、关闭及运行时统一匹配状态 |
| `prelude_replay` / `prelude_return` | 无 / `awaken`、`skip` | 重播序章 / 正常唤醒或跳过，保留按钮前置检查 |
| `dialogue_replay` | 无 | 检查 Gal 当前通讯是否需要首次显示 |
| `select_planet` | `Tempus` 或 `Carcere` | 选择关卡 |
| `start_mission` | 无 | 开始所选关卡 |
| `planet_preview` | `Tempus` | 显示已解锁关卡预览 |
| `description` | `Collector`、`Relay` 或 `Mortar` | 查看原版单位说明函数的结果 |

选择和开始关卡遵守游戏原有锁定条件。接口只接受这些固定命令，没有网络端口或任意代码执行接口。请求/响应使用随机 ID；超时后先检查待处理请求再重试。

停用会恢复正式程序集并移除 `CW3Debug.dll`。

其他构建目录须使用对应的 `--config local-only/候选/install-config.json`。写存档前先备份并选择空槽位，遵守游戏正常确认流程。

`style_probe` 报告当前字体角色、加载与回退状态；`layout_probe "控件路径"` 查询已存在控件的字号、布局和图集。

## 原生 Mac 候选

桥接候选的固定诊断接口在外置 `CW3ExternalRuntime.dll` 中，默认关闭。启停只读写 Unity `persistentDataPath/CW3Localization/cw3-debug/enabled.txt`，其内容必须等于已安装外置运行时的 SHA-256。启停前须正常退出游戏；命令仅接受下列白名单，不载入额外 DLL，也不改动 app 签名。显式传入已存在的 State 路径。

```sh
python3 tools/debug.py --config local-only/候选/install-config.json \
  --state '/path/to/persistentDataPath/CW3Localization' enable
python3 tools/debug.py --config local-only/候选/install-config.json \
  --state '/path/to/persistentDataPath/CW3Localization' \
  command settings_native_open
# 游戏正常退出后，以相同选项运行 debug.py disable。
```

`runtime_probe` 包含桥接状态、实际运行版本及译文计数；`style_probe/font_probe` 返回字体状态。`settings_native_open` 返回原设置页核心打开调用耗时；`settings_open/probe/change/save/cancel/defaults` 操作字体设置，probe 也报告已绑定入口的可见性。`settings_change` 只接受四角色、sans/serif 和 75–150% 的 5% 步进；`screenshot` 写入调试 State 目录。停用会将未处理请求改名保留，避免重启后执行旧请求。请求和截图局限在本机固定 State 目录，调用外置运行时代码拥有与游戏相同的本机用户权限，须保护该目录的写权限。

补验命令均不接受参数：`display_probe` 读取当前场景最多 400 个活动文本控件及其实际字体/回退/材质状态；`fonts_probe` 请求所选字体的原生中文字形；`fallback_probe` 在不显示的 TextMesh 上测试固定的 `字体㐀`，用于区分真实缺字回退和正常页面显示。它不是自然剧情中的文本。

`prelude_preview` 从首页直接进入原生序章场景，保留原有时间线与文字显示；不调用首页会写设置的首次启动分支。它是脚本预览，不代表鼠标导航或完整剧情验收。`preview_return` 只从本接口拥有的序章预览返回首页；`quit` 只允许在首页正常退出。`audio_probe` 只读取已载入音频的原生状态和正在播放的来源，不触发声音或改变设置。所有产物保留在本机，不随包分发。

Tempus 的暂停地图曾在临时候选中显示，但任务启动会重新读取原生设置，覆盖内存中的临时数据路径；安全检查拒绝了解除暂停。该教程预览入口已移除，不提供自动启动任务命令。完整教程对话仍需另行验收。
