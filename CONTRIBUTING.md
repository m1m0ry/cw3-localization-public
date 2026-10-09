# 贡献译文

1. 在 `translations/zh-CN.json` 搜索英文或中文，结合 `context` 判断位置。
2. 只改 `translation`，保留占位符、NGUI 标签和必要空格。脚本字面量中已有的 `\\n` 是游戏换行标记，保持原样；运行时输出模板中的 `{0}` 等只用于已核实的动态数值。
3. 运行 `python3 tools/workflow.py check`，提交 JSON 并在 PR 中说明原因。无需游戏文件或翻译服务。

同一句可按语境分别翻译。不要修改 ID、source、target 或自行重生成 `targets.lock.json`；内部状态、回调和资源键不能翻译。

改动需检查对应画面的换行和交互。检查提示缺字时由维护者处理字体，不引入系统专有字体。构建、外部词典更新及打包见[维护文档](docs/build.md)。
