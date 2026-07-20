# Codex Desktop Pet

一个 Windows 火柴人桌宠，用来聚合显示本机多个 Agent 的任务状态。它会通过动作和表情展示当前状态，并在需要权限批准、任务完成或异常中止时播放不同声音。

桌宠可以同时监控 Codex、Claude Code、OpenCode、Antigravity CLI、Gemini CLI、Aider、Cursor Agent、Qwen Code、Goose 和 Kimi CLI。每个任务在菜单中保留自己的 Agent 来源，任务数量和状态按所有 Agent 合并计算。

## 桌宠状态

- 空闲待命：在鱼缸前俯身，把手伸入水中追着游鱼打发时间；鱼、水草、气泡和水面波纹持续运动。
- 正在工作：坐在电脑桌前使用笔记本；双手持续敲击键盘，屏幕光标和代码行闪烁，杯中蒸汽缓慢摆动。
- 等你批准：举手并显示感叹号，同时重复播放提醒音。
- 任务完成，待检查：弯腰扶膝、满头大汗；身体随喘息起伏，汗滴下落，呼吸气团向外扩散。完成任务会从运行数量中移除并单独计入“待检查”。
- 任务已终止：主动中止会单独标记为“已终止”，不会误报为异常。
- 遇到异常：低头沮丧，并播放异常提示音。

所有桌宠场景均由 C# GDI+ 矢量图元实时绘制，不依赖位图素材；粗轮廓带有浅色描边，可适应明暗不同的桌面背景。

状态气泡会显示当前阶段、任务名称、已运行时间和活动任务数量。Codex 没有提供可信的百分比进度，因此桌宠不会虚构完成百分比。
完整版气泡会逐行显示当前任务的名称、状态和独立计时；最多直接预览 4 行，右键菜单中的“任务”子菜单会列出全部任务。点击任意任务可直接打开对应的 Codex 任务。

已完成数量与 Codex 的未读完成提示保持一致。没有打开过的完成任务会持续显示为“任务完成，待检查”；点击桌宠中的任务打开成果后会立即标记为已检查并移除。在 Codex 中点掉对应提示也会在下一次轮询中同步移除。Claude Code 和 OpenCode 的已检查状态保存在本机，同一会话后续再次完成时会重新提示。

## 安装

在 PowerShell 中运行：

```powershell
.\install.ps1
```

安装程序会：

1. 复制程序到 `%LOCALAPPDATA%\CodexDesktopPet`。
2. 在桌面创建 `Codex Desktop Pet` 快捷方式。
3. 合并用户级 `%USERPROFILE%\.codex\hooks.json`，并在修改已有文件前创建时间戳备份。
4. 启动桌宠。

首次安装后，在 Codex 中输入 `/hooks`，审核并信任状态为 `Codex Desktop Pet status bridge` 的 hooks。新任务会立即使用 hooks；当前已经运行的任务仍可通过本地会话日志被监控。

右键桌宠的“连接 Agent”菜单可以按需安装 Claude Code Hooks 或 OpenCode 插件，安装前会为已有配置创建时间戳备份。Claude Code 和 OpenCode 的 Hook/插件会提供精确的会话阶段；其他 CLI 会通过 Windows 进程命令行自动监控活动 TUI，显示真实进程启动时间和“TUI 运行中”。TUI 进程退出后对应的临时任务会自动移除，不会把用户主动关闭误报为异常。超过 7 天且已读的 Hook 历史状态会自动清理，未检查的完成任务不会被清理。

需要开机启动时，可以右键桌宠并勾选“开机启动”，也可以安装时运行：

```powershell
.\install.ps1 -StartWithWindows
```

## 使用

- 在桌宠任意非按钮区域按住鼠标左键拖动。
- 双击火柴人或点击“收起”，切换迷你模式；切换前后人物在桌面上的位置保持不变。
- 重复打开快捷方式只会唤醒已有桌宠，不会产生重叠窗口。
- 点击状态气泡中的任务可直接跳转到对应 Codex 任务；Claude Code 和 OpenCode 会恢复对应会话，其他 Agent 任务会启动对应 CLI 命令。也可打开 Codex、开关声音或连接 Hooks。
- 点击气泡右上角关闭按钮会隐藏到 Windows 系统托盘，任务监控和声音提醒继续运行。
- 单击或双击托盘里的火柴人图标可以恢复桌宠；托盘右键菜单可显示桌宠、打开 Codex 或彻底退出。
- 再次打开桌面快捷方式也可恢复托盘中的现有实例，不会重复启动。
- 右键桌宠打开完整菜单，可查看全部任务、隐藏到系统托盘、设置声音、置顶、开机启动、测试声音和明确退出。
- 待审批会重复播放警示音；完成和异常使用不同音阶。

## 隐私

Hook 桥接只保存会话 ID、工作目录、状态、阶段和时间。它不会保存提示词、回复、命令参数、工具输入或凭据。会话日志仅在本机只读解析，提取事件类型和任务标题。

## 开发与测试

项目使用 C#、WinForms 和 .NET Framework 4.8。主程序和 Hook 桥接均为独立 Windows EXE，不依赖 Python、PyInstaller 或额外运行时包；进程监控使用 Windows Management Instrumentation 读取活动 CLI 的进程名和命令行，不读取提示词、回复或凭据。

源码位于 `src/CodexDesktopPet` 和 `src/CodexDesktopPetHook`。构建和测试：

```powershell
.\test.ps1
.\build.ps1
```

构建脚本使用 Windows 自带的 .NET Framework C# 编译器。程序图标的可编辑矢量原稿位于 `assets/CodexDesktopPet.svg`，发布图标为多尺寸 Windows ICO。

## 卸载

```powershell
.\uninstall.ps1
```

卸载只删除本程序加入的 Hook 处理器，保留其他 Codex Hooks，并在修改前备份 `hooks.json`。
