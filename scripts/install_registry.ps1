#Requires -RunAsAdministrator
param(
    [ValidateSet("install", "uninstall")]
    [string]$Action = "install",
    [string]$Root
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# This script lives in <release>\_internal\. The release root is its parent,
# unless explicitly provided by the launcher .bat via -Root.
if (-not $Root) {
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $Root = Split-Path -Parent $scriptDir
}
$Cli = Join-Path $Root "_internal\pygiffer-cli.exe"
$Hive = [Microsoft.Win32.Registry]::ClassesRoot

function Get-MenuIcon {
    param([string]$CliPath)

    foreach ($candidate in @(
        (Join-Path $Root "_internal\assets\app.ico"),
        (Join-Path $Root "assets\app.ico")
    )) {
        if (Test-Path $candidate) {
            return (Resolve-Path $candidate).Path
        }
    }
    return "$CliPath,0"
}

function Get-ShellEntries {
    param([string]$CliPath)

    # Invoke CLI directly. wscript cannot receive Explorer's %* file list.
    return @(
        @{
            SubKey = "SystemFileAssociations\.webp\shell\PyGifferWebpToGif"
            Label = "转换为 gif 格式"
            Command = "`"$CliPath`" --notify convert `"%1`""
            Multi = $false
            AppliesTo = ""
        },
        @{
            # Explorer invokes once per file (%1); --batch aggregates them.
            SubKey = "SystemFileAssociations\.gif\shell\PyGifferMergeGifs"
            Label = "合并为 gif"
            Command = "`"$CliPath`" --notify merge --batch `"%1`""
            Multi = $true
            AppliesTo = ""
        },
        @{
            SubKey = "SystemFileAssociations\.gif\shell\PyGifferMergeGifsFlat"
            Label = "合并为 gif （去除透明背景）"
            Command = "`"$CliPath`" --notify merge --flat --batch `"%1`""
            Multi = $true
            AppliesTo = ""
        }
    )
}

function Write-ShellKey {
    param(
        [string]$SubKey,
        [string]$Label,
        [string]$Command,
        [string]$IconPath,
        [bool]$Multi,
        [string]$AppliesTo = ""
    )

    $key = $Hive.CreateSubKey($SubKey)
    if ($null -eq $key) {
        throw "Failed to open registry key: $SubKey"
    }
    try {
        $key.SetValue("", $Label, [Microsoft.Win32.RegistryValueKind]::String)
        $key.SetValue("Icon", $IconPath, [Microsoft.Win32.RegistryValueKind]::String)
        if ($AppliesTo) {
            $key.SetValue("AppliesTo", $AppliesTo, [Microsoft.Win32.RegistryValueKind]::String)
        }
        if ($Multi) {
            $key.SetValue("MultiSelectModel", "Player", [Microsoft.Win32.RegistryValueKind]::String)
        }
    }
    finally {
        $key.Close()
    }

    $cmdKey = $Hive.CreateSubKey("$SubKey\command")
    if ($null -eq $cmdKey) {
        throw "Failed to open registry key: $SubKey\command"
    }
    try {
        $cmdKey.SetValue("", $Command, [Microsoft.Win32.RegistryValueKind]::String)
    }
    finally {
        $cmdKey.Close()
    }
}

function Remove-ShellKey {
    param([string]$SubKey)

    foreach ($path in @("$SubKey\command", $SubKey)) {
        try {
            $Hive.DeleteSubKeyTree($path, $false)
        }
        catch {
            # Ignore missing keys during uninstall.
        }
    }
}

function Wait-ForExit {
    param([int]$ExitCode)

    if ($ExitCode -ne 0) {
        Write-Host ""
        Write-Host "安装失败，退出码：$ExitCode。" -ForegroundColor Red
    }
    else {
        Write-Host ""
        Write-Host "完成。" -ForegroundColor Green
    }
    Read-Host "按 Enter 键关闭窗口"
    exit $ExitCode
}

$LegacyKeys = @(
    "*\shell\PyGifferMergeGifs",
    "*\shell\PyGifferMergeGifsFlat",
    "*\shell\PyGifferWebpToGif",
    ".webp\shell\PyGifferWebpToGif"
)

try {
    switch ($Action) {
        "install" {
            if (-not (Test-Path $Cli)) {
                throw "找不到 CLI：$Cli`n请在 dist\pygiffer\ 目录下运行 install_registry.bat，或先执行 build_release.bat。"
            }

            $cliPath = (Resolve-Path $Cli).Path
            $icon = Get-MenuIcon $cliPath
            $entries = Get-ShellEntries $cliPath

            Write-Host "正在安装 PyGiffer 右键菜单..."
            Write-Host "Root: $Root"
            Write-Host "CLI:  $cliPath"
            Write-Host "Icon: $icon"
            foreach ($entry in $entries) {
                Write-ShellKey @entry -IconPath $icon
            }
            Write-Host "PyGiffer 右键菜单已安装。"
            Wait-ForExit 0
        }
        "uninstall" {
            Write-Host "正在移除 PyGiffer 右键菜单..."
            foreach ($entry in Get-ShellEntries $Cli) {
                Remove-ShellKey $entry.SubKey
            }
            foreach ($legacy in $LegacyKeys) {
                Remove-ShellKey $legacy
            }
            Write-Host "PyGiffer 右键菜单已移除。"
            Wait-ForExit 0
        }
    }
}
catch {
    Write-Host ""
    Write-Host "错误：$($_.Exception.Message)" -ForegroundColor Red
    if ($_.ScriptStackTrace) {
        Write-Host $_.ScriptStackTrace -ForegroundColor DarkGray
    }
    Wait-ForExit 1
}
