# CW3 工程规则

- 本仓库是唯一源码、译文和构建逻辑主线。日常修改与 PR 在此完成；私有 `m1m0ry/cw3-localization` 只维护固定原版输入、源码 revision 门禁及手动构建 workflow，不同步维护另一份源码。云端构建入口见 `docs/build.md`。

- 目标为 Windows Steam 2.12 / build 22453699（Unity 5.2.3f1）。不修改原生 Mac 版或其他游戏。
- 使用 `config.local.json` 定位安装和构建输入，不在源码中硬编码个人路径。原版、备份、缓存、日志、密钥和存档不提交 Git。
- 采用译文唯一来源是 `translations/zh-CN.json`。使用 `tools/workflow.py check` 校验、`tools/independent.py` 构建，不手改生成的 TSV、C# 映射或游戏二进制作为译文来源。
- 内部 ID、状态值、回调和资源键不翻译，只处理显示边界。保留 Unity 脚本索引、对象引用和未声明字段；不要绕过版本及哈希保护。
- 显示变更按影响选择源码契约、结构状态及必要画面/真实输入验证，分别报告证据和未验证项。CUA 不是默认门禁，静态或调试结果不能冒充实际显示/点击成功。游戏运行时不替换资源，保留安装版本对应的恢复文件。
- 调试模块默认关闭；接口与启停方法见 `docs/debug.md`。发行包不包含调试模块、运行日志或本机验收记录。
- 完整文件包由 `tools/package_player.py` 生成，构建目录保持 Git 忽略。公开安装包只包含补丁必要文件，不包含原版构建依赖、备份、存档或日志；游戏产物不提交源码树。
- 自写代码采用 MIT，字体保留 OFL 版权声明和许可证；来源见 `fonts/provenance.json`，许可范围见 `NOTICE.md` 和 `docs/licensing.md`。

本机验收、操作和旧版本记录存放于 `local-only/docs/`，不属于构建输入或协作必需文件。

按需使用：[显示目标审计](.agents/skills/cw3-display-audit/SKILL.md)（漏译/新增绑定）与[显示变更回归](.agents/skills/cw3-display-regression/SKILL.md)（字体/布局/交互）。Skill 不扩展授权；构建、推送、发布和安装分别按本次任务范围执行。
