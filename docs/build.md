# 本地构建与安装

支持版本：

- Windows、原生 macOS 的 Steam 2.12 / build 22453699
- Unity 5.2.3f1

构建依赖：

- Python 3.12（已验证）及 `requirements-build.txt` 中的依赖包
- 配置文件中指定的 Mono 工具链和 Cecil
- 对应平台的原版游戏文件

## 构建

1. 将 `config.example.json` 复制为 `config.local.json`，填写目标平台、游戏目录、原版输入和工具链路径。原生 macOS 配置使用 `target_id: macos-steam-22453699`，`game` 指向 `CW3.app` 所在父目录，并提供 Mac 原版文件。
2. 按 [fonts/provenance.json](../fonts/provenance.json) 中的来源与 SHA 准备 Noto Sans SC 源字体。
3. 运行以下命令完成准备、构建与打包（`prepare` 会校验并复用已有原版输入，从匹配的游戏安装目录中补齐缺失文件）：

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

构建过程仅在本地生成文件，不会自动安装到游戏目录。生成的安装包包含安装脚本、默认译文和 OFL 字体（`--external-full` 生成完整静态字体，分发时须保留 OFL 许可证）。若新增显示目标，需重新审计绑定后再构建。

确定性复核需保持以下输入一致：

- 源码提交、版本参数、原版游戏文件及引用 DLL
- `mcs.exe`、Cecil、源字体和 `requirements-build.txt` 中的依赖版本

字体构建固定 OpenType `head.modified` 和输出 SHA256（不读取当前时间）；ZIP 打包固定文件排序、日期、Unix 权限和 DEFLATE 级别，并保留安装入口的可执行位。

不同 Python/zlib 或 Mono 环境的字节一致性须另行验证。

## 安装与更新

补丁安装、更新、恢复原版和自定义译文说明见 [README](../README.md)。

## 云构建

维护者可在 GitHub Actions 页面打开 `Build candidate`，点击 `Run workflow`：

1. 选择目标分支。
2. 填写版本号 `version`（如 `v12.14`），平台 `target` 选择 `windows` 或 `macos`。
3. 构建完成后，从该次运行的 Artifacts 下载产物。

也可在对应分支或标签的干净工作副本中，使用已登录的 `gh` 触发构建、下载并校验：

```sh
python3 tools/build_candidate.py --ref feature/example --version v12.14 --target windows
```

`--target` 可改为 `macos`，产物保存在 `local-only/candidate-运行ID/`。

## 开发检查

无需游戏文件的检查：

```sh
python3 tools/workflow.py check
python3 -m unittest discover -s tests -p 'test_*.py'
python3 tools/test.py --list
```

配置好本地构建输入后，可运行 C# 契约测试与原版 IL 审计：

```sh
python3 tools/test.py --config local-only/independent-next/install-config.json
python3 tools/test.py --config local-only/independent-next/install-config.json \
  --suite GuiCaptionContracts --suite MainMenuClickContracts
python3 tools/audit_managed_display.py \
  --config local-only/independent-next/install-config.json \
  --output local-only/managed-review-new.json
```

- `--suite` 可重复指定以运行所选 C# 测试套件；不指定时运行全套测试。
- IL 审计需配置 `target_id` 和对应平台的原版输入。工具会校验原版哈希及绑定，将字符串区分为已有绑定、显示候选、内部键和未知项，并写入指定的 `local-only` 路径，不会自动修改译文。
- 漏译采集默认关闭。在[字体配置目录](text-style.md)下创建 `discover.enabled` 并重启游戏即可启用，结果写入同目录的 `candidates.json` 供人工审核；移除该文件并重启游戏即可关闭。

校验安装包完整性：

```sh
python3 tools/verify_package.py --config local-only/候选/install-config.json \
  --package local-only/候选包.zip --inspect-only
```

该命令检查 ZIP 清单、文件大小与哈希、安装器及说明文档。未提供构建用 EXE 时仅核对目标指纹；安装器在实际安装时还会校验目标游戏文件（macOS 使用不受签名变化影响的代码指纹）。

[贡献译文](../CONTRIBUTING.md) · [可选调试](debug.md) · [许可](licensing.md)
