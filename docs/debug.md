# 可选调试接口

调试模块用于开发时检查场景、字体、材质和显示文本，默认关闭，不随发行包提供。启用和停用时必须退出游戏，工具会核对程序集 SHA。

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
| `load_slot` | `0` | Tempus 正常界面读取 0 槽，仅用于存档往返验收 |
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

临时注入限于三个 `Awake` 的 Boot 调用，构建时反向去除后校验原有方法。停用会恢复正式程序集并移除 `CW3Debug.dll`，保留候选正式运行所需的辅助 DLL。调试返回值不能代替实际画面或鼠标交互测试。

外部候选需用对应 `--config local-only/候选/install-config.json` 构建调试模块；源码和运行时反向语义检查通过后才能 enable。存档写入使用游戏正常确认流程，先备份并选空槽位。
