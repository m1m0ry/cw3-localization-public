# 本地构建与安装

支持版本：

- Windows、原生 macOS 的 Steam 2.12 / build 22453699。
- Unity 5.2.3f1。

构建依赖：

- Python 3.12（已验证）。
- `requirements-build.txt` 中的 Python 包。
- 配置中的 Mono 工具链和 Cecil。
- 对应平台的原版游戏文件。

## 构建

复制 `config.example.json` 为 `config.local.json`，填写目标、游戏、原版输入和工具链路径。

`prepare` 校验并复用已有原版输入，从匹配的游戏安装中补齐缺失文件。按 [fonts/provenance.json](../fonts/provenance.json) 的来源与 SHA 准备 Noto Sans SC 源字体。

原生 Mac 配置使用 `target_id: macos-steam-22453699`，`game` 指向 `CW3.app` 父目录；原版输入须来自 Mac。

```sh
python3 -m pip install -r requirements-build.txt
python3 tools/workflow.py prepare
python3 tools/build_font.py /path/to/NotoSansSC-variable.ttf \
  local-only/independent-font/font.ttf --external-full
python3 tools/independent.py --version local --output local-only/independent-next
python3 tools/package_player.py \
  --config local-only/independent-next/install-config.json \
  --output local-only/CW3-local
```

构建只生成本地文件，不自动安装。安装包包含安装脚本、默认译文和 OFL 字体。`--external-full` 生成完整静态字体；分发字体须保留 OFL。

`workflow.py` 提供 `check` 和 `prepare`；候选由 `independent.py` 构建。译文在运行时按固定目标绑定，资源构建只保留字体和布局修复。

确定性复核须保持以下输入一致：

- 源码提交、版本参数、游戏文件及引用 DLL。
- mcs.exe、Cecil、字体和 `requirements-build.txt` 中的依赖版本。

字体配方固定 OpenType `head.modified` 和输出 SHA256，生成时不读取当前时间。ZIP 固定排序、日期、Unix 权限和 DEFLATE 级别，安装入口保留可执行位。不同 Python/zlib 或 Mono 环境的字节一致性须另行验证。

## 安装与更新

安装、更新、恢复和自定义译文见 [README](../README.md)。新增显示目标须重新审计和构建，新增字形须更新字体。

## 云构建

维护者在 GitHub Actions 打开 `Build candidate`，点击 `Run workflow`：

1. 选择分支。
2. 填写版本号 `version`（如 `v12.14`），平台 `target` 选择 `windows` 或 `macos`。
3. 完成后，从该次运行的 Artifacts 下载产物。

也可在对应分支/标签提交的干净工作副本中，使用已登录的 `gh` 触发、下载并校验：

```sh
python3 tools/build_candidate.py --ref feature/example --version v12.14 --target windows
```

`--target` 可改为 `macos`。产物保存在 `local-only/candidate-运行ID/`。

## 开发检查

不需游戏文件的检查：

```sh
python3 tools/workflow.py check
python3 -m unittest discover -s tests -p 'test_*.py'
python3 tools/test.py --list
```

有本地构建输入时可运行 C# 契约与原版 IL 审计：

```sh
python3 tools/test.py --config local-only/independent-next/install-config.json
python3 tools/test.py --config local-only/independent-next/install-config.json \
  --suite GuiCaptionContracts --suite MainMenuClickContracts
python3 tools/audit_managed_display.py \
  --config local-only/independent-next/install-config.json \
  --output local-only/managed-review-new.json
```

`--suite` 可重复，只运行所选 C# 套件；不指定时运行全套。

IL 审计区分已有绑定、显示候选、内部键及未知，不自动改译文。配置须提供 `target_id` 和匹配平台的原版输入。审计校验原版哈希及绑定，输出使用新的 `local-only` 路径。

漏译采集默认关闭。在[字体配置目录](text-style.md)创建 `discover.enabled`，重启游戏后启用；移除后重启关闭。结果写入同目录的 `candidates.json`，需人工审核。

检查安装包：

```sh
python3 tools/verify_package.py --config local-only/候选/install-config.json \
  --package local-only/候选包.zip --inspect-only
```

该命令检查 ZIP 清单、文件大小与哈希、安装器和说明。未提供构建用 EXE 时只核对目标指纹；安装器还会校验实际游戏，Mac 使用不受签名变化影响的代码指纹。

[贡献译文](../CONTRIBUTING.md) · [可选调试](debug.md) · [许可](licensing.md)
