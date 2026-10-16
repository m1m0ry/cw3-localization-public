# 字体与字号

可将自定义字体放入以下配置目录的 `fonts/` 文件夹中：

- Windows / CrossOver：游戏安装目录下的 `CW3Localization`
- 原生 macOS：`~/Library/Application Support/unity.Knuckle Cracker LLC.Creeper World 3/CW3Localization`

支持静态 TTF/OTF 字体，单个文件不超过 50 MB；最多同时使用 4 份，总计不超过 200 MB。

在游戏内打开“设置 → 字体与字号”，选择各类文字的字体和字号后点击保存（点击“恢复默认”后也需保存）。字号保存后立即生效；更换字体或修改像素基准需重启游戏后生效。

遇到缺字或字体加载失败时会自动回退到默认字体。实际字号受界面空间限制，文本过长时可能缩小、换行或裁切。若字体加载异常，可退出游戏后删除配置目录中的 `font-bundles/`，再重新启动游戏。

## 手动配置（可选）

退出游戏后，也可直接编辑上述配置目录中的 `text-style.json`：

```json
{"format":1,"roles":{
  "body":{"font":"正文.ttf","size_percent":100},
  "title":{"font":"serif","size_percent":100},
  "ui":{"font":"像素.ttf","size_percent":100,"pixel_size":12},
  "status":{"font":"sans","size_percent":100}
}}
```

四类文字角色分别为 `body`（正文）、`title`（标题/角色名）、`ui`（界面）、`status`（状态/数值）。字段说明：

- `font`：`sans`（默认）、`serif` 或 `fonts/` 下的本地字体文件名。
- `size_percent`：75–150 的整数百分比。
- `pixel_size`：可选的像素基准字号，取值范围 1–64。
