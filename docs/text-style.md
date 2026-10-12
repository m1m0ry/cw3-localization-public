# 字体与字号

将自己的静态 `.ttf` 或 `.otf` 放入游戏的 `CW3Localization/fonts` 文件夹，打开游戏“设置”下方的“字体与字号”，分别选择字体和字号，字号保存后即时生效；更换字体后退出并重启游戏。也可编辑 `CW3Localization/text-style.json`。支持中文文件名和空格。无需安装 Python、运行命令、安装系统字体或为每种字体重建补丁。

```json
{"format":1,"roles":{
  "body":{"font":"文楷.ttf","size_percent":100},
  "title":{"font":"serif","size_percent":100},
  "ui":{"font":"zpix.ttf","size_percent":100,"pixel_size":12},
  "status":{"font":"sans","size_percent":100}
}}
```

正文 `body`、标题/角色名 `title`、界面 `ui`、状态/数值 `status` 都可选择本地字体。`sans`、`serif` 是随附的 Noto Sans SC、Noto Serif SC；默认全部为 Sans。字号是 75–150 的整数百分比。Zpix 自动使用 12px 基准；其他像素字体可加 `pixel_size`（1–64），按基准字号的整数倍显示并使用点采样；省略或设 0 为平滑字形。编辑器可写输入保留原生光标、选区和字号参数。

设置页显示本次启动的选择、加载与已检查控件的缺字回退状态，以及已保存但待重启的字体改动。取消不写配置；“恢复默认”先恢复草稿，点击保存才生效。底部显示实际加载补丁的构建版本。保存后一次性更新现有文本和布局，新控件采用当前字号；混合修改先将字号应用到当前字体，新字体和像素基准重启生效。固定对话框与主菜单会按原显示区域适配，实际字号可能小于请求值；加入新字体后重启检查。

## 加载和回退

目标为 Windows Steam 2.12、Unity 5.2.3f1。游戏用 C# 将字体源字节封装进受控原生 Font 容器并加载，字形与图集由 Unity 生成。启动时核对源字表、实际字体身份和两个字号的字宽；随附 Sans/Serif 继续使用受控原生资源。运行中不改 `sharedassets0.assets`、`mainData` 或字体文件。

支持静态轮廓字体；字体集合、可变字体、网页字体及纯位图字体须先导出为静态 TTF/OTF。每个文件最多 50 MB，四种角色最多引用四份本地字体、总计 200 MB。字表按 BMP 验证，不接受目录外路径或链接文件。部分字体可能被旧引擎或内置读取器拒绝，以游戏实际检查结果为准。

字表来自字体自身。缺字、文件缺失或加载失败时，整控件回退 Sans；Sans 也不可用时回退原生字体。未知名称会回退，不能当作加载成功。无效配置恢复默认；删除 `text-style.json` 后重启也可重置。控件空间固定，较大字号仍可能换行或裁切。

原生字体容器缓存在 `CW3Localization/font-bundles`，按源内容和封装版本区分；损坏缓存自动重建。退出游戏后可删除缓存目录。源文件变化下次启动生效；`font-status.json` 记录检查结果。字体和缓存不上传，不写地图或存档。旧 `font-cache` 字图不再使用，可退出游戏后自行删除。


用户须遵守字体作者许可，自备字体及其缓存不能进入发行包。Zpix 使用相同文件流程，许可见 [Zpix 作者说明](https://github.com/SolidZORO/zpix-pixel-font)。正式发行只随附 OFL 的 Sans/Serif，保留原嵌入回退字体、对象引用与脚本索引。

## 旧版导入恢复

本节仅适用于曾使用 Python 资源导入工具的安装。普通旧版补丁使用原安装包的恢复入口。新安装器不再自动处理 `.cw3-font-imports`，不要删除其中的恢复备份。

1. 完全退出游戏，另存 `.cw3-font-imports`、`.cw3-zh-backup`、`CW3Localization/fonts` 和 `text-style.json`。
2. 使用该次导入所用的完整旧安装包。若 `.cw3-font-imports/journal.json` 存在，先恢复中断写入，再恢复导入前资源：

   ```sh
   python3 "旧包目录/font_import.py" --game "游戏目录" recover
   python3 "旧包目录/font_import.py" --game "游戏目录" restore
   ```

   没有 `journal.json` 时只执行 `restore`。若工具位于旧源码的 `tools` 目录，相应使用 `旧源码目录/tools/font_import.py`，保留同版相邻模块。
3. 确认旧工具恢复成功后，用旧安装包的安装器恢复原版；将旧安装备份另存到游戏目录外，再安装新版。旧工具保留的用户字体位于 `.cw3-font-imports/saved-fonts`，可另存回新版 `CW3Localization/fonts`。

旧工具缺失时应先取得与原安装匹配的完整工具包；不要拼接不同版本工具。若旧工具报哈希、未知字体文件或备份错误，停止升级并保留所有备份，不能用新包强行覆盖。恢复只依赖旧包的恢复入口，新版 C# 字体加载无需这些构建工具。
