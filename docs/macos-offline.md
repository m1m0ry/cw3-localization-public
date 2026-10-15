# 原生 Mac 离线候选

目标为 Steam build 22453699、Unity 5.2.3f1、序列化平台 2 的 `CW3.app`。
`v12.16.3-macos-bridge` 已从 Steam 正常启动，外置运行时实际载入，固定诊断报告桥接 `ready`、2232 条译文及 sans/serif 均可用。四角色保存、取消、即时字号、重启切换字体和恢复默认已通过脚本状态与截图验证；置前窗口的 Escape 返回已验证。后续包外补验确认原生序章中文及淡入淡出、现有 Zpix 的原生加载和实际菜单画面；真实鼠标命中、完整教程对话仍未确认。
Windows 发行路径保持平台 5。宿主是 macOS 并不代表目标是原生版，CrossOver 仍选择 Windows。

## 构建

沿用现有 `config.local.json` 的 Mono/Cecil 配置，另存一份配置并明确设置：

```json
{
  "target_id": "macos-steam-22453699",
  "game": "/path/to/steamapps/common/Creeper World 3",
  "original": "/path/to/style-inputs/macos-original"
}
```

`game` 是 `CW3.app` 的父目录。`workflow.py prepare` 只读游戏，按目标指纹封存规范化输入；输入仍使用逻辑 `CW3_Data/...` 路径。原版与编译引用必须全部来自同一目标，不能混用 Windows 文件。字体与固定 Python 依赖沿用 [build.md](build.md)。

```sh
python3 tools/workflow.py prepare --config local-only/macos-config.json
python3 tools/independent.py --config local-only/macos-config.json \
  --version v12.16.3-macos-bridge --output local-only/macos-native-candidate
python3 tools/package_player.py \
  --config local-only/macos-native-candidate/install-config.json \
  --output local-only/CW3-Mac-bridge
python3 tools/verify_package.py \
  --config local-only/macos-native-candidate/install-config.json \
  --package local-only/CW3-Mac-bridge.zip --inspect-only
```

这些命令不安装、不启动游戏。失败候选保留在 `.building-*` 目录，完成全部验证才发布候选目录和清单。不要用 `python -O` 关闭守卫。

`resources/macos-target.json` 锁定可执行文件、输入与允许的资源修复；`resources/macos-bindings.json` 将现有译文 ID 映射到 Mac 原版物理位置。共用词典和原始目标锁不迁移。历史 Windows v10 坐标须先由其 rendering 阶段解释；Mac 绑定一律使用 pristine 坐标、方法签名和邻近 IL 指纹。

## 字体、性能与路径

Mac 默认使用 sans、100%、非像素策略，复用四角色字体设置、字号即时刷新、本地字体及像素字体加载与缺字回退。平台 2 字体模板通过离线生成和独立反解析。实机四角色改为 serif 并分别设置 105/110/115/120%，保存后仅字号即时生效，重启后字体及字号均按配置生效；恢复默认并重启后回到 sans/100%。补验使用用户已有的 Zpix，未下载或加入包：原生动态字体名称、中文字形、独立像素图集及实际菜单画面均通过。Zpix 覆盖当前全部译文字符；固定离屏 TextMesh 的 `字体㐀` 实际报告 `zpix.ttf_missing_glyph`，回退 sans 后字形请求成功。该探针不等于自然页面发生过缺字。

资源保留原生 Shader、外部引用、ResourceManager 原字段及脚本索引。新版把与 Windows 原版对象字节、ID、关键字段完全一致的 166 个非菜单音效改为后台加载；菜单 ID 81/104/229 保持同步。`UIPanel.Fill/LateUpdate` 的材质查询缓存对 Mac 程序集通过了仅两方法变化的独立 IL 校验。原设置页的读配置、激活和输入初始化调用在三次正常启动后测得 107/110/130 ms；这是核心调用耗时，不包含鼠标导航、启动总耗时或帧呈现延迟，未作原版性能对比。

Mac 运行时从固定的包外 DLL 位置推导 Data 和 Content。Content 位于 `.app` 兄弟目录 `CW3Localization`，State 位于 Unity `persistentDataPath/CW3Localization`。Unity 5.2 的 `dataPath` 指向 `.app/Contents`，不能直接用作实际 Data。配置、状态和缓存只允许写 State；不可用时不回写 bundle。Windows 保持原来的 sidecar 行为。

包内仍需保留 Unity 序列化资源、固定显示调用已补丁的 `Assembly-CSharp.dll`、小型渲染辅助 `CW3Rendering.dll` 和固定桥接入口 `CW3Runtime.dll`。完整汉化运行时、词典及字体输入位于包外；本方案不把 Unity 的资源加载改成通用外部补丁框架。

桥接层只从同级 `CW3Localization/Runtime/CW3ExternalRuntime.dll` 加载，不枚举 DLL、不下载代码。该文件及两个固定父目录必须为游戏用户所有、类型正确、非链接且不可被其他用户写入；外置代码拥有游戏用户权限，这个本机目录是信任边界。加载时核对完整固定接口，缺失或不匹配时回退原文及原版 GUI，并显示持续的失败提示，不能把回退报告为汉化成功。Intel libc 的普通 `lstat` 是旧 ABI，须显式请求 `lstat$INODE64`；ARM 无此符号时使用默认 ABI。这个差异已在游戏自带的 Intel Mono 中做独立加载验证。

固定诊断命令常驻于外置运行时，默认关闭；启用标记只在 State，详见 [debug.md](debug.md)。未启用时不创建诊断更新对象。

## 安装、重签与回滚边界

包内 `CW3_Data` 是逻辑路径，不能手工拖入 `.app` 合并。通用安装器按目标清单转换路径、检查原生 `Contents/MacOS/CW3` 及旧 `Menu Helper` 进程、锁定原版与未覆盖依赖，先备份再写 journal；对带封印签名的 Mac bundle 仍在写入前拒绝。已安装、有效 ad-hoc 签名的旧候选可用源码工具 `tools/macos_adhoc_update.py` 经严格核验后更新，必须等游戏完全退出。默认只预检，`--apply` 才更新；只有包内变化才重签。外置运行时、登记表或词典单独更新会跳过签名命令，并校验现有签名。改动前保留旧补丁文件、可执行文件、封印和安装状态的可恢复快照。此前受限执行环境对两个 Mono 库误报签名无效；宿主环境对同一应用的 `codesign --verify --deep --strict` 通过，因此更新工具不设置签名例外，必须在宿主环境执行。它不会恢复原 Developer ID 签名，也不会清除 quarantine、添加系统例外或关闭安全保护。新的 ad-hoc 签名可能要求用户再次在系统设置中允许启动。

```sh
python3 tools/macos_adhoc_update.py --game /path/to/Creeper\ World\ 3 \
  --old-package local-only/CW3-Mac-font-performance \
  --new-package local-only/CW3-Mac-bridge
# 游戏退出后，确认预检内容再追加 --apply
```

Mac 备份和 staging 位于 `.app` 外，备份绑定目标、安装根和可执行文件指纹。原文件字节与权限必须保存并验证；不执行签名修复、清除 quarantine 或权限提权。恢复仅处理本包清单，保留用户 State 和存档；未知文件变化拒绝覆盖。
首次实机尝试发现，macOS 在对已有程序集原位写入时自动改变了 `com.apple.provenance` 的值，普通复制和原位恢复均不能复原旧值。安装器保存原值与安装后观测值，只容许**这一属性的值**变化；属性存在性、权限、quarantine 及所有其他扩展属性仍严格校验。恢复后如值不同，会明确报告原字节与可恢复元数据已恢复、系统管理值未复原。备份和 journal 先于写入，中断时只允许 journal 标记的当前文件按已验证备份恢复。
`8cd52f5` 离线包触发过 provenance 问题，禁止再次用于实际安装。后续真实恢复结清了中断 journal，`fc68bc1` 版本安装和恢复均通过 14 文件校验，但两次启动没有生成窗口或新日志。`codesign --verify --deep --strict` 明确报告新增两个 Managed DLL 和修改的程序集、资源使原 Developer ID 封印失效；恢复后同一 bundle 验证通过。之后的 `53e5523` 试验由受控入口安装并 ad-hoc 重签，用户通过系统入口成功打开；原版备份保留。通用安装器继续拒绝所有签名 bundle，已签名候选的后续更新只走单独的签名快照工具。

桥接候选相对字体性能版只变更 `CW3.app/Contents/Resources/Data/Managed/CW3Runtime.dll` 与外部 `CW3Localization/fonts.json`，并新增外部 `CW3Localization/Runtime/CW3ExternalRuntime.dll`。`Assembly-CSharp.dll` 不变。更新工具为 14→15 文件迁移保留独立 `adhoc-bridge-previous` 快照；默认 `--recover` 恢复该迁移前版本，并将新增 DLL 可恢复地移入快照。后续更新按版本保留 `adhoc-版本` 或 `external-版本` 快照，以 `--recover --new-package 对应包目录` 恢复。

实机 `v12.16.2`→`v12.16.3` 只更新外置运行时和登记表，无签名命令；独立比对确认 `.app` 全部 81 个文件的字节和元数据不变，字体配置哈希不变，重启后新版本及配置实际生效。四角色配置写入也通过相同比对。结束时恢复原默认配置状态、关闭诊断并正常退出，六个存档数据文件哈希与安装前一致。

补验在 `v12.16.4/5` 仅更新包外 Runtime 和字体登记表，没有执行重签。原生序章通过直接场景预览自然播放，截图中的中文、材质状态和淡入淡出正常。Tempus 暂停地图及中文界面有实际画面，但任务启动会重新读取设置，覆盖内存中的临时数据路径；安全检查拒绝解除暂停。此教程预览入口已从最终运行时移除，不把暂停地图报告为教程对话通过。音频只读探针观察到 186 个音频处于 `Loaded`、音乐 `Desperation` 正在播放；没有旧版耗时基线，不能量化音频或 PanelFill 提速。测试后正常退出、关闭诊断并恢复用户原有无字号配置/无自定义字体状态；`.app` 全部 81 文件和真实存档树 65 文件的字节、mode 与扩展属性均不变。

仍需人工验收：字体入口的真实鼠标命中、原设置页关闭及焦点、完整长剧情/教程对话、实际正文和数值控件的遮挡与裁切。离线通过或调试状态不能代替实际显示或点击结果。
