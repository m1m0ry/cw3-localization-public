# 本地构建与安装

本仓库包含源码、译文和构建脚本。

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

确定性复核须保持源码提交、版本参数、游戏及引用 DLL、mcs.exe、Cecil、字体和依赖版本相同。完整 Python 依赖版本固定在 `requirements-build.txt`；字体配方保留受控产物的 OpenType `head.modified` 和输出 SHA256，生成时不读取当前时间。ZIP 固定排序、日期、Unix 权限和 DEFLATE 级别；安装入口保留可执行位。不同 Python/zlib 或 Mono 环境间的字节一致性须另行验证。

## 安装与更新

安装和恢复步骤见 [README](../README.md)。基础补丁安装后，只改 `CW3Localization/zh-CN.json` 的 `translation`，保留其他字段、标签和占位符。退出后替换，重启生效。新增显示目标须重新审计和构建；新增字形须更新字体。

升级使用新版完整包的安装入口；兼容备份可直接更新，跨类型补丁按安装器提示先恢复。包内不含用户字号配置和自定义字体，覆盖或升级会保留它们。词典可在退出游戏后直接替换，重启生效；构建校验留在开发端。

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

`--suite` 可重复、去重，只运行所选 C# 套件；不指定时运行全套。IL 审计区分已有绑定、显示候选、内部键及未知，不自动改译文。配置须指向对应 `managed/render.dll`，输出使用新的 `local-only` 路径。

漏译候选采集默认关闭。创建游戏目录下的 `CW3Localization/discover.enabled` 并重启可启用，删除后重启关闭；结果写入同目录 `candidates.json`，需人工审核，不自动翻译或上传。


`tools/verify_package.py --config local-only/候选/install-config.json --package local-only/候选包.zip --inspect-only` 检查 ZIP 清单、文件大小与哈希、安装器和说明，不创建游戏副本。没有构建用 EXE 时只核对目标指纹；安装器始终检查实际 EXE。

[贡献译文](../CONTRIBUTING.md) · [可选调试](debug.md) · [许可](licensing.md)
