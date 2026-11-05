# 维护入口

日常开发使用 `tools/dev.py`，复用已有构建、安装和调试工具。源码检查可以在本地或云环境运行；固定输入的 Windows/macOS 完整包使用现有 GitHub Actions。原生 Mac 安装和实机诊断在 Mac 上执行。

## 一次配置环境

把本机配置放在被 Git 忽略的 `local-only/dev.json`：

```json
{
  "python": "/path/to/existing/environment/bin/python",
  "game": "/path/to/Steam/steamapps/common/Creeper World 3",
  "state": "/path/to/Unity/persistentDataPath/CW3Localization",
  "mono_runtime": "/path/to/mono",
  "mono_compiler": "/path/to/lib/mono/4.5/mcs.exe",
  "steam": "/Applications/Steam.app/Contents/MacOS/steam_osx"
}
```

`state` 是已生成 `font-status.json` 的[字体配置目录](text-style.md)，不是 Steam 游戏目录。路径不写入公开源码。纯源码测试不需要 `game`、`state` 或 Steam。

```sh
python3 tools/dev.py doctor
python3 tools/dev.py test
```

入口依次验证配置的 Python、当前虚拟环境、项目 `.venv`、当前解释器与 PATH；可用 `python_candidates` 添加已有环境。最后尝试 uv 的离线缓存，不自动下载或全局安装依赖。`doctor` 显示实际解释器和依赖版本。若维护者明确复用额外的纯 Python 依赖目录，可配置 `pythonpath` 数组，作用仅限所选解释器的子进程，不改变系统环境。固定版本发行构建仍由锁定依赖的 CI 完成。

默认 `test` 执行译文检查、完整 Python 测试和不需要游戏文件的 C# 契约。仅修改 Python 时可用 `test --python-only`，结果明确记录 C# 未运行。Mono 可在 PATH 上，或使用上述已有工具链配置；不需要复制 CW3 原版输入。

## 按改动运行

```sh
python3 tools/dev.py plan --base HEAD
python3 tools/dev.py run --kind source --python-only
python3 tools/dev.py run --kind rendering --ref feature/example --version v12.15
python3 tools/dev.py run --kind package --ref feature/example --version v12.14 --target macos
```

- `source`：构建脚本、测试和文档只执行源码检查，不启动游戏。
- `rendering`：测试后构建精确远程 ref 的完整候选，再按文件哈希差分安装。Mac 的实际渲染实现位于包外 `CW3Localization/Runtime/CW3ExternalRuntime.dll`，`fonts.json` 必须携带配套运行时哈希。包内 `CW3Rendering.dll` 是稳定薄桥，不再单独编译完整 renderer 覆盖它。当前复用完整云构建，不声称是增量编译。
- `package`：复用 `build_candidate.py` 触发精确远程 ref，下载并验证对应产物，再安装和验收。入口不提交或推送源码；远程 ref 必须事先存在且匹配干净 HEAD。Windows 目标只生成已验证候选，不在 Mac 上安装 Windows 包。
- `auto`（默认）：根据相对 `--base` 的改动选择以上范围。已经提交的改动要给出比较基线，或明确指定 `--kind`。原版 IL、字体、运行时、薄桥或译文改动归入 `package`；`rendering` 和 `package` 都要求 `--ref` / `--version`，不会自动推送源码。

已有候选可跳过构建：

```sh
python3 tools/dev.py apply --package local-only/unpacked-player-package
```

完整包使用原安装器的白名单、哈希、差分写入与条件重签。首次迁移到外置渲染需要更新包内薄桥并重签；迁移后若仅外置实现和配套 `fonts.json` 变化，且现有签名有效，安装不会写入 app 包或重签。旧的单 DLL `rendering_component` 候选及其中断会话已停用，应换成完整包，避免把薄桥覆盖回旧实现。

开始前校验完整候选和外置运行时哈希配对；不允许只替换 DLL 而漏更新配套清单。整个操作不更改系统权限或 Steam 配置。默认只请求正常退出，退出超时则保留当前阶段，不自动强杀。

## 中断后继续

```sh
python3 tools/dev.py status
python3 tools/dev.py resume
```

状态保存在 `local-only/evidence/dev-session.json`，包含候选清单指纹、实际安装哈希、升级前的外置运行时哈希、启动时间和 PID、诊断请求 ID 及证据。也可用全局 `--session` 指定本次记录。

安装中断后重跑同一候选；安装完成后等待权限或连接恢复不会重装或回退。若原诊断开关匹配会话记录的旧运行时，且没有排队中的请求，入口在游戏退出后自动刷新为新哈希；不覆盖来源不明的开关或未完成的请求。启动结果不明时先观察进程，不重复发起启动。诊断超时保留原请求，`resume` 等待相同 ID，忽略旧响应。若请求投递被中断且确实需要重试，只读探针可用 `resume --retry-probe` 更换请求；它不会重做安装或启动。

限时内没有回应时，入口说明当前阶段和待确认状态。应检查系统弹窗及本次启动日志；超时本身不证明权限问题，也不能把看不到窗口当成候选损坏。只有确认候选回归、安装损坏或明确需要恢复时才另行回退。

运行期间临时保持显示和系统唤醒，命令结束即释放，不改长期电源设置。

## 验收边界

原生 Mac 使用现有游戏内固定接口，检查同一次进程的 `MainMenu`、外置渲染 ABI v1 与实际委托绑定、文字控件及游戏内截图。仅到达菜单不算外置渲染验收通过。截图必须完整落盘，不能把 `queued` 当成完成。自动烟雾检查与实际画面审阅、真实鼠标焦点和卡顿收益测量分别记录；自动通过不代表所有画面或性能已经验证。

入口回归测试使用隔离的小型完整包和模拟进程；它们可以验证差分安装及重签边界，不能代替真实游戏中的验收。

完整云候选构建与源码 CI 共用 `dev.py test`，候选打包前先过 Python 和 standalone C# 契约。依赖真实游戏输入的全部 IL/字体检查仍由对应构建验包及专项测试覆盖，不能仅凭源码检查替代。
