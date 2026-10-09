#!/bin/zsh
set -u
bundle_dir="${0:A:h}"
cw3_exit_code=1
if command -v python3 >/dev/null 2>&1; then
  python3 "$bundle_dir/install.py"
  cw3_exit_code=$?
else
  echo '需要 Python 3.10 或更新版本。无需 UnityPy、Mono 或其他开发依赖。'
  echo '安装 Python 后再次双击此文件；不要修改系统安全设置。'
fi
if [[ -t 0 ]]; then read -r '?按回车关闭。'; fi
exit "$cw3_exit_code"
