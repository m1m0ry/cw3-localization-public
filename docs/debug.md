# 可选调试接口

用于开发时检查场景、字体、材质和显示文本，默认关闭。启停前退出游戏，工具会核对程序集 SHA。

## Windows / CrossOver

调试 DLL 需单独构建，不随发行包提供。

```sh
python3 tools/build_managed.py --debug
python3 tools/debug.py enable
# 启动游戏后查询
python3 tools/debug.py command snapshot
# 退出游戏后停用
python3 tools/debug.py disable
```

常用命令：

| 命令 | 参数 | 用途 |
| --- | --- | --- |
| `discovery_probe` | 无 | 候选采集开关、计数、写盘及局部耗时 |
| `runtime_probe` / `font_probe` | 无 | 译文绑定、词典计数、原文回退与字体选择 |
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

选择和开始关卡遵守游戏原有锁定条件。接口仅接受固定命令，没有网络端口或任意代码执行接口。超时后先检查待处理请求再重试。

停用会恢复正式程序集并移除 `CW3Debug.dll`。

其他构建目录须使用对应的 `--config local-only/候选/install-config.json`。写存档前先备份并选择空槽位，遵守游戏正常确认流程。

`style_probe` 报告当前字体角色、加载与回退状态；`layout_probe "控件路径"` 查询已存在控件的字号、布局和图集。

## 原生 macOS

Mac 使用外置运行时中的固定接口，无需构建调试 DLL。

先正常启动并退出游戏，确认[字体配置目录](text-style.md)中已有 `font-status.json`。将该目录作为 `STATE`，启停前退出游戏。

```sh
python3 tools/debug.py --config CONFIG --state STATE enable
# 启动后改为 command runtime_probe；退出后改为 disable。
```

查询命令：`runtime_probe`、`style_probe`、`display_probe`、`screenshot`。
