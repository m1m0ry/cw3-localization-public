# 本地构建与安装

本仓库包含源码、译文和构建脚本。

目标为 Windows 与原生 macOS 的 Steam 2.12 / build 22453699 / Unity 5.2.3f1。需要 Python 3.10+、配置中的 Mono 工具链与 Cecil、`requirements-build.txt` 中的依赖及匹配的原版游戏文件。原版输入与构建产物不提交 Git。

## 构建

复制 `config.example.json` 为 `config.local.json`，填写目标、游戏、原版输入和工具链路径。`prepare` 按固定 SHA 复用已有原版输入，仅从匹配安装补齐缺失项。按 [fonts/provenance.json](../fonts/provenance.json) 的来源与 SHA 准备 Noto Sans SC 源字体。

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

构建只写本地产物，不自动安装。完整文件包含安装、清理入口、外部词典和 OFL 字体。`--external-full` 生成完整静态字体；分发字体须保留 OFL。

`workflow.py` 仅提供 `check` 和 `prepare`；候选统一由 `independent.py` 构建。译文在运行时按固定目标绑定，资源构建只保留字体和布局修复。旧差分生成工具已退役。

确定性复核须保持源码提交、版本参数、游戏及引用 DLL、mcs.exe、Cecil、字体和依赖版本相同。完整 Python 依赖版本固定在 `requirements-build.txt`；字体配方保留受控产物的 OpenType `head.modified` 和输出 SHA256，生成时不读取当前时间。ZIP 固定排序、日期、Unix 权限和 DEFLATE 级别；安装入口保留可执行位。不同 Python/zlib 或 Mono 环境间的字节一致性须另行验证。

## 安装与更新

安装、重装、降级及原版清理步骤见 [README](../README.md)。默认译文 `CW3Localization/zh-CN.default.json` 随包更新；独立的 `zh-CN.user.json` 只保存自定义条目，不随包覆盖。新增显示目标须重新审计和构建，新增字形须更新字体。

## 云构建

PR 与 `main` 提交自动运行译文检查和不需游戏输入的 Python 测试。维护者可在 `Build candidate` 的原生 Branch 菜单选择本仓库开发分支，合并前构建 Windows 或原生 Mac 候选。运行固定到所选分支当时的 `github.sha`；API/CLI 也可选择本仓库标签来指定提交。固定输入引用见 [ci-inputs.json](../resources/ci-inputs.json)。

首次启用[原生手动入口](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow)需要默认分支已有 workflow 定义；之后可选择开发分支独立运行。

在仓库 Settings → Environments 创建 `build-inputs`，Deployment branches and tags 允许需要构建的分支/标签或选择 No restriction；在该 Environment 添加 `CW3_INPUTS_READ_TOKEN`。Required reviewers 为可选设置；启用后须审批，未启用时由维护者手动触发即可。使用仅选择私有输入仓库的 fine-grained PAT，仓库权限仅需 `Contents: read`。该权限可读取所选仓库全部内容，不能限制为单个 Release。不要将它配置为仓库级 Secret。

在所选分支的工作副本中，使用已登录的 `gh` 下载并校验候选：

```sh
python3 tools/build_candidate.py --ref feature/example --version v12.14 --target windows
python3 tools/build_candidate.py --ref feature/example --version v12.14 --target macos
```

每次构建固定源码提交及对应平台输入，只上传补丁 ZIP、`SHA256SUMS.txt` 和 `build-info.json`，保留 14 天。候选命令等待返回的确切运行 ID，校验来源、平台和文件哈希；产物保存到 `local-only/candidate-运行ID/`。构建不创建 Release 或安装补丁。

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

`--suite` 可重复、去重，只运行所选 C# 套件；不指定时运行全套。IL 审计区分已有绑定、显示候选、内部键及未知，不自动改译文。配置须提供已校验的原版输入，输出使用新的 `local-only` 路径。

漏译候选采集默认关闭。创建游戏目录下的 `CW3Localization/discover.enabled` 并重启可启用，删除后重启关闭；结果写入同目录 `candidates.json`，需人工审核，不自动翻译或上传。


`tools/verify_package.py --config local-only/候选/install-config.json --package local-only/候选包.zip --inspect-only` 检查 ZIP 清单、文件大小与哈希、安装器和说明，不创建游戏副本。没有构建用 EXE 时只核对目标指纹；安装器核验固定游戏版本及 Mac 签名无关代码指纹。

[贡献译文](../CONTRIBUTING.md) · [可选调试](debug.md) · [许可](licensing.md)
