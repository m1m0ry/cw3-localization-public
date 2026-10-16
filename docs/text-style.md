# 字体与字号

打开“设置 → 字体与字号”，分别选择四类文字的字体和字号。字号保存后生效，换字体须重启。自定义静态 TTF/OTF 放入配置目录的 `fonts/`：

- Windows/CrossOver：游戏目录下的 `CW3Localization`。
- 原生 macOS：`~/Library/Application Support/unity.Knuckle Cracker LLC.Creeper World 3/CW3Localization`。

也可退出游戏后编辑该目录中的 `text-style.json`：

```json
{"format":1,"roles":{
  "body":{"font":"正文.ttf","size_percent":100},
  "title":{"font":"serif","size_percent":100},
  "ui":{"font":"像素.ttf","size_percent":100,"pixel_size":12},
  "status":{"font":"sans","size_percent":100}
}}
```

四类文字对应 `body`（正文）、`title`（标题/角色名）、`ui`（界面）、`status`（状态/数值）。

- `font`：`sans`、`serif` 或本地字体文件名。随附字体为 Noto Sans SC、Noto Serif SC，默认全部为 Sans。
- `size_percent`：75–150 的整数百分比。
- `pixel_size`：像素字体的基准字号，范围1–64，按整数倍显示并使用点采样。省略或设0为平滑字形。

编辑器可写输入保留原生光标、选区和字号参数。

设置页显示当前字体的加载状态和待重启的改动。取消不写配置；“恢复默认”后仍须保存。字号立即生效，字体与像素基准改动重启后生效。文字会按原显示区域适配，实际字号可能小于所选值。

## 加载和回退

支持静态轮廓字体；字体集合、可变字体、网页字体及纯位图字体须先导出为静态 TTF/OTF。每个文件最多 50 MB，四种角色最多引用四份本地字体、总计 200 MB。字表按 BMP 验证，不接受目录外路径或链接文件。部分字体可能被旧引擎或内置读取器拒绝，以游戏实际检查结果为准。

字表来自字体自身。缺字、文件缺失或加载失败时，整控件回退 Sans；Sans 也不可用时回退原生字体。像素正文无法在不小于12px的整数倍字号下容纳文本时，当前控件回退 Sans 普通适配，保留所选设置。未知名称会回退，不能当作加载成功。无效配置恢复默认；删除 `text-style.json` 后重启也可重置。控件空间固定，较大字号仍可能换行或裁切。

字体缓存位于上述配置目录的 `font-bundles/`，损坏时自动重建，退出游戏后可删除。源文件变化下次启动生效，`font-status.json` 记录加载结果。字体和缓存不上传，不写地图或存档。
