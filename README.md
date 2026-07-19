# Codex Traffic Light

一个 Windows 桌面红绿灯，用来聚合显示本机 Codex 任务状态，并在需要权限批准、任务完成或异常中止时播放不同声音。

## 状态

- 红灯：等待权限批准；任务异常时也会亮红灯，并显示“任务异常”。
- 黄灯：Codex 正在分析、使用工具、修改文件或整理结果。
- 绿灯：任务完成；一段时间没有新任务后显示“空闲”。

Codex 没有提供可信的百分比进度，因此程序显示当前阶段、已运行时间和活动任务数量，不虚构完成百分比。

## 安装

在 PowerShell 中运行：

```powershell
.\install.ps1
```

安装程序会：

1. 复制程序到 `%LOCALAPPDATA%\CodexTrafficLight`。
2. 在桌面创建 `Codex Traffic Light` 快捷方式。
3. 合并用户级 `%USERPROFILE%\.codex\hooks.json`，并在修改已有文件前创建时间戳备份。
4. 启动红绿灯。

首次安装后，在 Codex 中输入 `/hooks`，审核并信任状态为 `Codex Traffic Light status bridge` 的 hooks。新任务会立即使用 hooks；当前已经运行的任务仍可通过本地会话日志被监控。

需要开机启动时，可以右键红绿灯并勾选“开机启动”，也可以安装时运行：

```powershell
.\install.ps1 -StartWithWindows
```

## 使用

- 双击桌面的 `Codex Traffic Light`。
- 双击灯体或点击“收起”，切换迷你红绿灯。
- 右键打开菜单，可静音、置顶、测试声音、打开 Codex 或设置开机启动。
- 待审批会重复播放警示音；完成和异常使用不同音阶。

## 隐私

hook 桥接只保存会话 ID、工作目录、状态、阶段和时间。它不会保存提示词、回复、命令参数、工具输入或凭据。会话日志仅在本机只读解析，提取事件类型和任务标题。

## 开发与测试

项目只使用 Python 标准库。源码运行：

```powershell
python main.py
```

测试和打包：

```powershell
python -m unittest discover -v
.\build.ps1
```

## 卸载

```powershell
.\uninstall.ps1
```

卸载只删除本程序加入的 hook 处理器，保留其他 Codex hooks，并在修改前备份 `hooks.json`。

