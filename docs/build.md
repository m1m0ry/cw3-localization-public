# 本地构建与安装

源码、译文和构建脚本只在本公开仓库维护。私有 `m1m0ry/cw3-localization` 是固定输入与手动云端构建后台，不维护另一条源码主线。

目标为 Windows Steam 2.12 / build 22453699 / Unity 5.2.3f1。构建已验证于 macOS + CrossOver（wine-mono 10.4.1），需要 Python 3.10+、`requirements-build.txt` 中的依赖及自备的匹配原版游戏文件。原版输入与构建产物保存在 `local-only/`，不提交 Git。

## 构建

复制 `config.example.json` 为 `config.local.json`，填写游戏和 CrossOver 路径。游戏须为匹配的干净原版，原版文件按固定 SHA 校验。按 [fonts/provenance.json](../fonts/provenance.json) 的来源与 SHA 准备 Noto Sans SC 源字体。

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

构建只写本地产物，不自动安装。完整文件包含安装、恢复入口、外部词典和 OFL 字体。`--external-full` 生成完整静态字体；分发字体须保留 OFL。

## 安装与更新

安装和恢复步骤见 [README](../README.md)。基础补丁安装后，只改 `CW3Localization/zh-CN.json` 的 `translation`，保留其他字段、标签和占位符。退出后替换，重启生效。新增显示目标须重新审计和构建；新增字形须更新字体。

```sh
python3 tools/update_runtime.py --config local-only/independent-next/install-config.json
```

更新器检查固定目标、格式及实际字体，并同步恢复文件；该工具使用 CrossOver 进程检查。Windows 可在退出游戏后手动替换词典，恢复使用包内安装器。

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

`--suite` 可重复、去重，只运行选定 C# 套件及必要夹具；不指定时运行全套。IL 审计只读枚举原版 `ldstr`，区分已有绑定、显示候选、明确内部键及未知；候选不等于确认漏译，不自动改译文。配置须指向对应 `managed/render.dll`，输出使用新的 `local-only` 路径。静态检查不证明实际画面或点击正常。

漏译候选采集默认关闭。创建游戏目录下的 `CW3Localization/discover.enabled` 并重启可启用，删除后重启关闭；结果写入同目录 `candidates.json`，需人工审核，不自动翻译或上传。

[贡献译文](../CONTRIBUTING.md) · [可选调试](debug.md) · [许可](licensing.md)

## 维护者云端构建与发布

先将修改合并到本仓库 `main`，选定完整的 40 位 commit SHA。在私有后台手动触发：

```sh
gh workflow run release.yml --repo m1m0ry/cw3-localization --ref main \
  -f source_commit=<公开完整SHA> -f tag=v12.6
```

后台仅接受本仓库 `main` 已包含的提交，不接受分支名、短 SHA 或未合并 PR。原版输入按私有锁校验；仅构建，不启动游戏、不安装、不创建 Release。成功后从对应 run 下载唯一的 `cw3-package-<SHA>` artifact：

```sh
gh run download <run-id> --repo m1m0ry/cw3-localization \
  -n cw3-package-<公开完整SHA> -D local-only/release-v12.6
```

核对 `build-info.json` 的版本与公开 SHA，用 `SHA256SUMS.txt` 校验 ZIP；检查 ZIP 内 manifest 的 `source_repo`、`source_commit` 和逐文件 `after` 哈希。画面/交互验证按本次改动范围完成。准备简短发行说明到 `local-only/release-v12.6/RELEASE.md`，经本次发布授权后用已有本机认证发布：

```sh
gh release create v12.6 --repo m1m0ry/cw3-localization-public \
  --target <同一公开完整SHA> --title 'CW3 简体中文 v12.6' \
  --notes-file local-only/release-v12.6/RELEASE.md \
  local-only/release-v12.6/CW3-Windows-v12.6.zip \
  local-only/release-v12.6/SHA256SUMS.txt
```

已有版本不覆盖。当前自动化到候选包为止；公开发布仍是维护者手动操作，不需要新增 token 或跨仓 secret。
