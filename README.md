# Creeper World 3 汉化补丁

适用于 **Windows 与原生 macOS 的 Steam 2.12 / build 22453699**，覆盖主菜单、剧情、教程和地图编辑器界面。社区地图的作者文本可能保留原文。

## 下载与安装

从 [Release](https://github.com/m1m0ry/cw3-localization-public/releases/latest) 下载对应平台的补丁包并解压。

### Windows

1. 完全退出游戏。
2. 在 Steam 中右键游戏 → 管理 → 浏览本地文件。
3. 将解压出的 `CW3_Data` 和 `CW3Localization` 复制到游戏安装文件夹（`CW3.exe` 所在位置），提示时选择覆盖。

**手动安装无需 Python。** 更新补丁时，保留原有 `CW3Localization` 目录下的 `fonts/`、`text-style.json` 和 `zh-CN.user.json`。

也可在安装 Python 3.10+ 后双击包内的 `安装汉化.cmd`，按提示选择游戏安装文件夹，再选 `1 安装/重装汉化`。

CrossOver 用户使用同一 Windows 补丁包，运行 `安装汉化.command`，选择包含 `CW3.exe` 的游戏安装文件夹。

### 原生 macOS

1. 完全退出游戏，并确认已安装 Python 3.10+。
2. 在 Steam 中右键游戏 → 管理 → 浏览本地文件，找到包含 `CW3.app` 的目录。
3. 双击包内 `安装汉化.command`，按提示选择该目录，再选 `1 安装/重装汉化`。

如系统阻止启动，确认来源后按系统提示手动允许。

### 恢复原版

运行对应平台的安装脚本，选择 `2 清理汉化程序`，再通过 Steam「验证游戏文件完整性」。

## 自定义译文

词典文件位于游戏目录的 `CW3Localization` 下：

- `zh-CN.default.json`：随补丁更新的默认译文。
- `zh-CN.user.json`：可选的自定义译文，有效条目优先于默认译文，更新补丁时保留。

可在 `zh-CN.user.json` 中添加需要覆盖的条目，例如：

```json
{
  "format": 1,
  "language": "zh-CN",
  "entries": [
    {
      "id": "text.edceac6532890c27",
      "source": "Exit",
      "translation": "退出游戏"
    }
  ]
}
```

可从 `zh-CN.default.json` 复制条目，仅修改 `translation` 字段（保留原文中的标签和占位符），保存后重启游戏生效。

## 译文与构建

仓库译文统一维护在 `translations/zh-CN.json`。修改 `translation` 时请保留原文、目标、标签和占位符。校验译文无需游戏文件或翻译服务：

```sh
python3 tools/workflow.py check
```

从源码构建补丁需自备匹配版本的游戏文件及构建依赖，详见[构建文档](docs/build.md)。

## 游戏截图

中文主菜单

![中文主菜单](docs/images/main-menu.jpg)

序幕文字

![中文序幕](docs/images/prologue.jpg)

莉娅对话与按键设置

![莉娅对话与中文按键设置](docs/images/dialogue-settings.jpg)

自写代码采用 [MIT](LICENSE) 许可，字体采用 [OFL 1.1](fonts/OFL.txt) 许可。游戏原文、画面及资源不属于本项目的 MIT 授权范围，详见 [NOTICE](NOTICE.md)。

[贡献译文](CONTRIBUTING.md) · [构建与安装](docs/build.md) · [字体与字号](docs/text-style.md) · [字体与第三方许可](docs/licensing.md)
