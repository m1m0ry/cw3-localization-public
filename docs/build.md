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

PR 与 `main` 提交自动运行译文检查和不需游戏输入的 Python 测试。

在 `Build candidate` 的 Branch 菜单选择开发分支，可在合并前构建 Windows 或原生 Mac 候选。API/CLI 也支持仓库标签。构建使用所选分支或标签当时的提交；固定输入引用见 [ci-inputs.json](../resources/ci-inputs.json)。

首次启用[原生手动入口](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow)需要默认分支已有 workflow 定义；之后可选择开发分支独立运行。

首次配置：

1. 在 Settings → Environments 创建 `build-inputs`。
2. Deployment branches and tags 允许需要构建的分支/标签，或选择 No restriction。
3. 在该 Environment 添加 `CW3_INPUTS_READ_TOKEN`，不要设为仓库级 Secret。

令牌使用仅选择私有输入仓库的 fine-grained PAT，权限为 `Contents: read`。它可读取所选仓库的全部内容，不能限制为单个 Release。

Required reviewers 可选：启用后须审批，否则由维护者手动触发。

工作副本须保持干净，并检出所选分支/标签的同一提交。使用已登录的 `gh` 下载并校验候选：

```sh
python3 tools/build_candidate.py --ref feature/example --version v12.14 --target windows
python3 tools/build_candidate.py --ref feature/example --version v12.14 --target macos
```

候选校验使用命令启动时冻结的提交快照。运行 SHA 不符时，下载前停止并打印实际提交。

构建上传补丁 ZIP、`SHA256SUMS.txt` 和 `build-info.json`，保留 14 天。候选命令按确切运行 ID 下载，校验来源、平台和文件哈希，保存到 `local-only/candidate-运行ID/`。构建不创建 Release 或安装补丁。

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
