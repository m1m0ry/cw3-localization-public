# Creeper World 3 简体中文补丁

面向 **Windows 与原生 macOS 的 Steam 2.12 / build 22453699**，主要菜单、剧情和教程纯离线汉化。社区内容和地图编辑器可能保留英文。

## 下载与安装

从 [Release](https://github.com/m1m0ry/cw3-localization-public/releases/latest) 下载与你的游戏平台匹配的完整补丁包。须自备上述版本的正版游戏；源码 ZIP 不是安装包。

### Windows（含 CrossOver 中的 Windows 版）

1. 完全退出游戏，下载并解压 `CW3-Windows-v12.14.zip`。
2. 在 Steam 中右键游戏 → 管理 → 浏览本地文件，找到包含 `CW3.exe` 的目录。
3. 把解压包里的 `CW3_Data` 和 `CW3Localization` 两个文件夹复制到该目录，与 `CW3.exe` 同级；合并文件夹并覆盖同名文件。

**手动安装无需 Python。** 更新时保留原有 `CW3Localization` 中的 `fonts/`、`text-style.json` 和 `zh-CN.user.json`，只合并包内文件。

自定义译文若仍在 `zh-CN.json`，先将自定义条目合并到 `zh-CN.user.json`，保留已有内容。

也可安装 Python 3.10+ 后双击包内 `安装汉化.cmd`，按提示选择上述游戏目录，再选 `1 安装/重装汉化`。CrossOver 使用同一 Windows 包，脚本入口为 `安装汉化.command`，选择瓶内包含 `CW3.exe` 的目录。

### 原生 macOS

1. 完全退出游戏，下载并解压 `CW3-Mac-v12.14.zip`，准备 Python 3.10+。
2. 在 Steam 中右键游戏 → 管理 → 浏览本地文件，找到包含 `CW3.app` 的目录。
3. 双击包内 `安装汉化.command`，按提示选择该目录，再选 `1 安装/重装汉化`。

安装器负责将资源写入 `CW3.app` 并做必要的 ad-hoc 重签，保留用户词典、字体设置、自定义字体和存档。如系统阻止启动，确认来源后按系统提示手动允许。

### 恢复原版

运行对应的安装脚本，选择 `2 清理汉化程序`，再通过 Steam「验证游戏文件完整性」。Steam 不会自动删除额外注入的 DLL。

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
