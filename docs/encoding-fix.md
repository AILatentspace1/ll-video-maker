# Windows 乱码修复说明

## 背景

本项目在 Windows 下如果使用 **Windows PowerShell 5.1**，容易出现 UTF-8 中文乱码问题，常见表现包括：

- `Get-Content` 读取中文文件时乱码
- 终端里中文 prompt、注释、日志显示异常
- 通过 shell 管道把中文内容写入文件后，文件内容本身被写坏

这不是项目业务逻辑的问题，核心是 **PowerShell 5.1 的编码行为过旧**。

## 当前项目约定

本项目默认应使用：

- **PowerShell 7 (`pwsh`)**

不要使用：

- **Windows PowerShell 5.1**

工作区已在 `.vscode/settings.json` 中预设：

- `PowerShell 7` 终端 profile
- 默认终端为 `PowerShell 7`

## 为什么要切到 PowerShell 7

根据 PowerShell 官方文档和相关排查经验：

- PowerShell 7 对 UTF-8 的支持更现代
- 与 Python / Node / Git 的编码行为更一致
- 对中文文件读取、终端输出、管道传输更稳定

## 如何确认当前终端版本

在终端中运行：

```powershell
$PSVersionTable.PSVersion
```

如果结果类似：

```text
Major Minor
----- -----
5     1
```

说明你当前还在用 Windows PowerShell 5.1。

如果是 `7.x`，说明已切换成功。

## 安装 PowerShell 7

官方文档：

- Microsoft Learn: https://learn.microsoft.com/en-us/powershell/scripting/install/install-powershell-on-windows?view=powershell-7.5

如果你的系统有 `winget`，官方推荐安装方式是：

```powershell
winget install --id Microsoft.PowerShell --source winget
```

安装后重新打开终端，再运行：

```powershell
pwsh -v
```

## 如果 `winget` 不存在

说明当前系统环境较旧，可以改用以下方式之一：

1. 从 Microsoft Learn 指向的官方 MSI 安装包手动安装
2. 从 Microsoft Store 安装 PowerShell
3. 如果有 .NET SDK，也可以按官方文档使用 `.NET Global tool` 安装

## VS Code 中检查默认终端

打开 VS Code 设置，确认：

- 默认终端为 `PowerShell 7`

或检查 `.vscode/settings.json` 中是否存在：

```json
"terminal.integrated.defaultProfile.windows": "PowerShell 7"
```

## 对本项目的实际影响

如果继续使用 PowerShell 5.1，最容易受影响的是：

- prompt markdown 文件写入
- 含中文注释或内容的文件编辑
- 终端中 `Get-Content` / 管道 / here-string 的中文传递

因此：

- **代码逻辑可以是对的**
- **但文件内容可能在终端写入链路里先被转码损坏**

## 建议

1. Windows 下优先使用 `pwsh`
2. 尽量避免通过 PowerShell 5.1 的 here-string / 管道直接写大段中文
3. 对 prompt 文件保持 UTF-8，并通过测试持续检查乱码字符

## 参考

- 博客园文章（用户提供）：https://www.cnblogs.com/pridelzh/articles/19540703
- Microsoft Learn：Install PowerShell 7 on Windows  
  https://learn.microsoft.com/en-us/powershell/scripting/install/install-powershell-on-windows?view=powershell-7.5
