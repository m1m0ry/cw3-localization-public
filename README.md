# Creeper World 3 简体中文补丁

面向 **Windows 与原生 macOS 的 Steam 2.12 / build 22453699**，主要菜单、剧情和教程纯离线汉化。社区内容和地图编辑器可能保留英文。

## 下载与安装

从 [Release](https://github.com/m1m0ry/cw3-localization-public/releases/latest) 下载完整补丁包；源码 ZIP 不是安装包。须自备匹配的正版游戏与 Python 3.10+。

完全退出游戏，解压后运行 `安装汉化.cmd`（Windows）或 `安装汉化.command`（macOS、CrossOver）。安装、更新、降级和中断后重试均使用完整包。也可使用源码安装器：

```sh
python3 tools/player_install.py --package PACKAGE --game GAME --action install
```

`GAME` 是 Steam「管理 → 浏览本地文件」打开的目录，包含 `CW3.exe` 或 `CW3.app`。原生 Mac 包内程序变化时会做必要的 ad-hoc 重签；如系统阻止启动，确认来源后按系统提示手动允许。

`CW3Localization/zh-CN.default.json` 随完整包更新；自定义译文放在独立的 `zh-CN.user.json`，字体设置、自定义字体、存档与旧备份保留。未知旧 `zh-CN.json` 会使本次安装停止，按提示迁移后重试。

恢复原版：先在安装入口选择清理汉化程序，再通过 Steam「验证游戏文件完整性」。Steam 不会自动删除额外注入的 DLL。若提示未覆盖的资源版本不符，也先执行这两步，再安装目标版本。

## 译文与构建

译文统一维护在 `translations/zh-CN.json`。仅修改 `translation`，保留原文、目标、标签和占位符；检查无需游戏文件或翻译服务：

```sh
python3 tools/workflow.py check
```

自定义译文沿用默认文件的 `format`、`language`、`entries` 格式，将要改的条目复制到 `CW3Localization/zh-CN.user.json`，只保留自定义项。仅修改 `translation`，保留 ID、原文、标签和占位符；退出后修改，重启生效。新增显示位置或字形须重新构建。源码构建需自备匹配游戏文件及构建依赖，见[构建文档](docs/build.md)。

## 游戏截图

中文主菜单。

![中文主菜单](docs/images/main-menu.jpg)

序幕文字。

![中文序幕](docs/images/prologue.jpg)

莉娅对话与按键设置。

![莉娅对话与中文按键设置](docs/images/dialogue-settings.jpg)

自写代码采用 [MIT](LICENSE)，字体采用 [OFL 1.1](fonts/OFL.txt)。游戏原文、画面及资源不属于本项目的 MIT 授权范围，见 [NOTICE](NOTICE.md)。

[贡献译文](CONTRIBUTING.md) · [构建与安装](docs/build.md) · [字体与字号](docs/text-style.md) · [字体与第三方许可](docs/licensing.md)
