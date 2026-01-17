# R-Link 插件编译脚本 (Windows)
# 用于将子模块编译为二进制插件

$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $PSScriptRoot
$SubmodulesDir = Join-Path $RootDir "submodules"
$PluginsDir = Join-Path $RootDir "R-Link-Server\plugins"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "R-Link 插件编译脚本" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 定义要编译的插件
$Plugins = @(
    @{
        Name = "frp"
        SourceDir = "frp"
        BinaryName = "frpc.exe"
        BuildScript = {
            param($SourcePath)
            # FRP 使用预编译的二进制，直接复制
            $BinaryPath = Get-ChildItem -Path $SourcePath -Recurse -Filter "frpc.exe" | Select-Object -First 1
            return $BinaryPath.FullName
        }
    },
    @{
        Name = "rustdesk"
        SourceDir = "rustdesk"
        BinaryName = "rustdesk.exe"
        BuildScript = {
            param($SourcePath)
            # RustDesk 需要编译
            Set-Location $SourcePath
            cargo build --release --binary "rustdesk"
            return Join-Path $SourcePath "target\release\rustdesk.exe"
        }
    },
    @{
        Name = "sunshine"
        SourceDir = "sunshine"
        BinaryName = "sunshine.exe"
        BuildScript = {
            param($SourcePath)
            # Sunshine 需要使用 CMake 编译
            # 这里假设已经编译好，直接复制
            $BinaryPath = Get-ChildItem -Path $SourcePath -Recurse -Filter "sunshine.exe" | Select-Object -First 1
            return $BinaryPath.FullName
        }
    },
    @{
        Name = "rclone"
        SourceDir = "rclone"
        BinaryName = "rclone.exe"
        BuildScript = {
            param($SourcePath)
            # RClone 使用 Go 编译
            Set-Location $SourcePath
            go build -o rclone.exe .
            return Join-Path $SourcePath "rclone.exe"
        }
    },
    @{
        Name = "netbird"
        SourceDir = "netbird"
        BinaryName = "netbird.exe"
        BuildScript = {
            param($SourcePath)
            # NetBird 使用 Go 编译
            Set-Location (Join-Path $SourcePath "client")
            go build -o netbird.exe .
            return Join-Path $SourcePath "client\netbird.exe"
        }
    }
)

# 创建插件目录
if (-not (Test-Path $PluginsDir)) {
    New-Item -ItemType Directory -Path $PluginsDir -Force | Out-Null
}

# 编译每个插件
foreach ($Plugin in $Plugins) {
    Write-Host "处理插件: $($Plugin.Name)" -ForegroundColor Yellow

    $PluginDir = Join-Path $PluginsDir $Plugin.Name
    $SourcePath = Join-Path $SubmodulesDir $Plugin.SourceDir

    # 检查源码目录
    if (-not (Test-Path $SourcePath)) {
        Write-Host "  跳过: 源码目录不存在 ($SourcePath)" -ForegroundColor Gray
        continue
    }

    # 创建插件目录
    if (-not (Test-Path $PluginDir)) {
        New-Item -ItemType Directory -Path $PluginDir -Force | Out-Null
    }

    # 执行构建脚本
    try {
        $BinaryPath = & $Plugin.BuildScript $SourcePath

        if ($BinaryPath -and (Test-Path $BinaryPath)) {
            # 复制二进制文件
            $DestPath = Join-Path $PluginDir $Plugin.BinaryName
            Copy-Item -Path $BinaryPath -Destination $DestPath -Force
            Write-Host "  已复制: $DestPath" -ForegroundColor Green
        } else {
            Write-Host "  警告: 二进制文件未找到" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "  错误: $_" -ForegroundColor Red
    }

    Write-Host ""
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "编译完成!" -ForegroundColor Green
Write-Host "请为每个插件创建 manifest.yaml 文件" -ForegroundColor Yellow
Write-Host "参考: R-Link-Server\docs\plugin-manifest-example.yaml" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan
