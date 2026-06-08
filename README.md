# PyGiffer

本地 GIF 转换与合并工具（Python + PyQt6 GUI + 无 Qt 依赖的 CLI）。

## 架构

| 组件 | 入口 | 依赖 |
|------|------|------|
| GUI | `main.py` / `pygiffer.exe` | PyQt6 |
| CLI | `python -m pygiffer.cli` / `pygiffer-cli.exe` | Pillow、OpenCV（无 PyQt） |

GUI 通过子进程调用 CLI 完成转换与合并；资源管理器右键菜单也调用同一 CLI。

## 功能

- **格式转换**：WebP / 图片 / 视频 → GIF
- **横向合并**：多 GIF 拼接，支持去透明背景
- **素材文件夹**：网格预览、合并队列
- **右键菜单**：注册表绑定到 `pygiffer-cli`
- **自动更新**：GUI 右下角显示版本号与更新状态，发现新版本时一键更新

## 版本与自动更新

- 版本号唯一来源：`pygiffer/version.py` 的 `__version__`。
- 推送 `vX.Y.Z` 形式的 git tag 会触发 GitHub Action（`.github/workflows/release.yml`）：在 Windows 上打包并发布 Release，附带 `pygiffer-X.Y.Z-windows.zip`。CI 会用 tag 覆写 `__version__`，保证产物版本与 tag 一致。
- GUI 启动时异步查询最新 Release，右下角状态：`检测更新中… / 已是最新 / 发现新版本 vX / 更新检测失败（网络故障）`。
- 发现新版本时出现「更新」按钮：下载 zip → 解压 → 关闭 GUI → 覆盖安装目录 → 运行 `install_registry.bat` → 重启。仅打包版（frozen）支持。

发布新版本：

```powershell
git tag v0.1.1
git push origin v0.1.1
```

## 安装

```powershell
cd pygiffer
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 启动 GUI

```powershell
python main.py
```

## CLI 用法

```powershell
python -m pygiffer.cli convert input.webp
python -m pygiffer.cli convert input.webp -o out.gif
python -m pygiffer.cli merge a.gif b.gif
python -m pygiffer.cli merge a.gif b.gif -o out.gif --flat
python -m pygiffer.cli --notify convert file.webp   # 右键菜单模式（弹窗提示）
```

## 打包

```powershell
scripts\build_release.bat          # 增量（较快）
scripts\build_release.bat clean    # 全量
```

输出：

```
dist/pygiffer/
  pygiffer.exe              GUI（仅 PyQt）
  install_registry.bat      安装右键菜单（双击）
  uninstall_registry.bat    卸载右键菜单（双击）
  _internal/
    pygiffer-cli.exe        CLI（convert / merge，无 PyQt）
    install_registry.ps1    实际写注册表的脚本（由 .bat 调用）
    assets/app.ico          菜单与窗口图标
    (OpenCV / Pillow / …)
```

根目录只保留 GUI 和两个 `.bat` 入口，其余实现细节都收纳在 `_internal\`。

GUI 与 CLI 分开 Analysis，打包更快、体积更小。

### 打包环境

推荐使用 [python.org](https://www.python.org/downloads/) Python 3.12 的 venv。Conda venv 可能导致 GUI EXE 启动失败（Qt DLL 问题）。

## 右键菜单

发布包：双击 `install_registry.bat`（会自动请求管理员权限）。菜单直接调用 `_internal\pygiffer-cli.exe`，图标使用 `assets\app.ico`。卸载用 `uninstall_registry.bat`。

资源管理器对该菜单按「每个文件启动一次」（Document 模型，仅 `%1` 能传文件）。因此合并命令用 `--batch "%1"`：每个实例把文件写入临时批次文件，等待约 1.5 秒收齐后，由其中一个实例统一执行合并。命令形如：

```
"...\pygiffer-cli.exe" --notify merge --batch "%1"
"...\pygiffer-cli.exe" --notify merge --flat --batch "%1"
```

GUI 仍直接传入所有路径（不走 `--batch`）。

Windows 11 需在右键菜单中选择 **「显示更多选项」** 才能看到自定义项与图标（系统限制，现代精简菜单不支持）。

右键操作失败时会弹出置顶错误提示；成功时无弹窗。输出文件保存在**源文件所在目录**：
- 转换：`{原名}-{时间戳}.gif`
- 合并：`{时间戳}.gif`

修改脚本或重新打包后，请先 `uninstall_registry.bat` 再 `install_registry.bat`。

开发环境：

```powershell
python scripts\install_registry.py install
```

| 操作 | CLI 等价命令 |
|------|----------------|
| 右键 `.webp` | `pygiffer-cli --notify convert "%1"` |
| 多选 `.gif` 合并 | `pygiffer-cli --notify merge %*` |
| 多选合并去透明 | `pygiffer-cli --notify merge --flat %*` |

## 项目结构

```
pygiffer/
├── main.py              # GUI 入口
├── cli_main.py          # CLI 打包入口
├── pygiffer/
│   ├── cli.py           # 统一 CLI
│   ├── convert.py / merge.py
│   ├── ui/
│   │   ├── main_window.py
│   │   └── cli_runner.py
│   └── paths.py
└── scripts/
    ├── build_release.bat
    └── install_registry.bat
```
