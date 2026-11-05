# 原生 macOS 自定义数据目录

原版已经提供 `UseCustomDataPath` / `CustomDataPath` 设置，但启动时先运行文稿目录大小写迁移，再读取设置。即使玩家选了别处，启动仍会枚举 Documents，可能等待 macOS 文稿权限。

原生 macOS 构建增加一个限定补丁：

- 先读取游戏设置，再运行旧目录迁移。
- 已启用自定义目录时，跳过 Documents 的旧目录迁移。
- 自定义目录创建失败时直接报告错误，不再静默退回 Documents。
- 未启用自定义目录时保留原版行为；Windows 构建不应用此补丁。

目录仍由原版 GameSettings.xml 配置。`CustomDataPath` 是父目录，游戏会在其下追加 `creeperworld3/`。可使用用户的 `~/Library/Application Support` 作为父目录。游戏设置本身仍保存在原版设置目录；这里不修改它的位置。

迁移应在游戏退出后进行：复制原数据目录，核对文件，将自定义目录设置指向新父目录，再启动确认日志中的 `Using base game data dir`。保留旧目录即可回退。构建、安装不会自动迁移玩家数据，也不会修改 Steam 云同步设置；Steam 原有 Auto Cloud 规则不随自定义路径更新。

验证包括补丁可逆和其余 IL 不变、启动顺序、自定义路径读写、目录失败不回退、默认分支保留。契约入口为 `tools/test.py --config CONFIG --suite CustomSavePathContracts`。实际验收仍需确认游戏加载目录；契约文件读写测试不等同于关卡存档加载测试。

“不访问 Documents”的保证以成功读取启用自定义路径的配置为前提。配置缺失或损坏时，原版设置恢复逻辑可能重新选择默认目录。暂不引入额外配置系统或全局路径替换；如果上游修正启动顺序和回退逻辑，应重新核验并移除此补丁。
