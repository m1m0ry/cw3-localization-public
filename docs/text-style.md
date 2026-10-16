# 字体与字号

自定义字体放入以下配置目录的 `fonts/`：

- Windows/CrossOver：游戏目录下的 `CW3Localization`。
- 原生 macOS：`~/Library/Application Support/unity.Knuckle Cracker LLC.Creeper World 3/CW3Localization`。

支持静态 TTF/OTF，每份最多 50 MB，最多四份、总计 200 MB。

打开“设置 → 字体与字号”。选择各类文字的字体和字号后保存。字号立即生效；字体与像素基准改动须重启。“恢复默认”后也须保存。

缺字或加载失败时使用默认字体。字号可能受界面空间限制而缩小、换行或裁切。

字体加载异常时，可退出游戏后删除配置目录中的 `font-bundles/`，再重启。

## 手动配置（可选）

退出游戏后，可编辑同一配置目录中的 `text-style.json`：

```json
{"format":1,"roles":{
  "body":{"font":"正文.ttf","size_percent":100},
  "title":{"font":"serif","size_percent":100},
  "ui":{"font":"像素.ttf","size_percent":100,"pixel_size":12},
  "status":{"font":"sans","size_percent":100}
}}
```

四类文字对应 `body`（正文）、`title`（标题/角色名）、`ui`（界面）、`status`（状态/数值）。

- `font`：`sans`（默认）、`serif` 或本地字体文件名。
- `size_percent`：75–150 的整数百分比。
- `pixel_size`：可选的像素基准字号，范围1–64。
