#requires -RunAsAdministrator
param(
    [Parameter(Mandatory=$true)][string]$PayloadDirectory,
    [Parameter(Mandatory=$true)][ValidatePattern('^[a-fA-F0-9]{64}$')][string]$ManifestSha256,
    [Parameter(Mandatory=$true)][string]$PythonPath
)
$ErrorActionPreference = 'Stop'
function Set-RLinkAcl([string]$Path, [bool]$Directory, [bool]$Public) {
    if ($Directory) { $taskAcl = New-Object Security.AccessControl.DirectorySecurity }
    else { $taskAcl = New-Object Security.AccessControl.FileSecurity }
    $taskAcl.SetAccessRuleProtection($true, $false)
    $taskAcl.SetOwner((New-Object Security.Principal.SecurityIdentifier('S-1-5-32-544')))
    $taskInherit = [Security.AccessControl.InheritanceFlags]::None
    if ($Directory) { $taskInherit = [Security.AccessControl.InheritanceFlags]'ContainerInherit,ObjectInherit' }
    foreach ($taskAccess in @(@('S-1-5-18','FullControl'), @('S-1-5-32-544','FullControl'))) {
        $taskRule = New-Object Security.AccessControl.FileSystemAccessRule((New-Object Security.Principal.SecurityIdentifier($taskAccess[0])), [Security.AccessControl.FileSystemRights]$taskAccess[1], $taskInherit, [Security.AccessControl.PropagationFlags]::None, [Security.AccessControl.AccessControlType]::Allow)
        $taskAcl.AddAccessRule($taskRule)
    }
    if ($Public) {
        $taskRule = New-Object Security.AccessControl.FileSystemAccessRule((New-Object Security.Principal.SecurityIdentifier('S-1-5-32-545')), [Security.AccessControl.FileSystemRights]::ReadAndExecute, $taskInherit, [Security.AccessControl.PropagationFlags]::None, [Security.AccessControl.AccessControlType]::Allow)
        $taskAcl.AddAccessRule($taskRule)
    }
    Set-Acl -LiteralPath $Path -AclObject $taskAcl
}
$taskLock = New-Object Threading.Mutex($false, 'Global\RLinkFabricInstall')
if (-not $taskLock.WaitOne(0)) { throw 'Another R-Link network installation is running.' }
try {
    $taskPayload = (Resolve-Path -LiteralPath $PayloadDirectory).Path
    $taskManifestPath = Join-Path $taskPayload 'manifest.json'
    if ((Get-FileHash -LiteralPath $taskManifestPath -Algorithm SHA256).Hash -ine $ManifestSha256) { throw 'Package manifest verification failed.' }
    $taskManifest = Get-Content -LiteralPath $taskManifestPath -Raw | ConvertFrom-Json
    if ($taskManifest.schema_version -ne 1 -or $taskManifest.platform -ne 'windows-amd64') { throw 'Package is for another platform.' }
    foreach ($taskName in @('rlink-agent.exe', 'wintun.dll', 'decrypt-enrollment.py')) {
        $taskHash = $taskManifest.files.$taskName
        if (-not $taskHash -or (Get-FileHash -LiteralPath (Join-Path $taskPayload $taskName) -Algorithm SHA256).Hash -ine $taskHash) { throw ('Package checksum mismatch: ' + $taskName) }
    }
    $taskSignature = Get-AuthenticodeSignature -LiteralPath (Join-Path $taskPayload 'wintun.dll')
    if ($taskSignature.Status -ne 'Valid' -or $taskSignature.SignerCertificate.Subject -notmatch 'O=WireGuard LLC') { throw 'Wintun publisher validation failed.' }
    $taskProgramFiles = (Get-ItemProperty -LiteralPath 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion' -Name ProgramFilesDir).ProgramFilesDir
    $taskBinaryDirectory = Join-Path $taskProgramFiles 'R-Link\Agent'
    $taskStateDirectory = Join-Path ([Environment]::GetFolderPath('CommonApplicationData')) 'R-Link\Agent'
    $taskExe = Join-Path $taskBinaryDirectory 'rlink-agent.exe'
    $taskConfig = Join-Path $taskStateDirectory 'config.json'
    $taskServiceCommand = '"' + $taskExe + '" run --config "' + $taskConfig + '" --udp-port 51822'
    $taskExistingService = Get-CimInstance Win32_Service -Filter "Name='RLinkFabric'"
    if ($taskExistingService -and $taskExistingService.PathName.Trim() -ine $taskServiceCommand) { throw 'An unrelated service or network configuration was preserved.' }
    if (Test-Path -LiteralPath $taskConfig) {
        $taskIdentity = Get-Content -LiteralPath $taskConfig -Raw | ConvertFrom-Json
        if ($taskIdentity.control_url -ne 'https://175.178.16.90/r-link') { throw 'Existing network identity was preserved.' }
        $taskIdentity = $null
    }
    foreach ($taskDirectory in @($taskBinaryDirectory, $taskStateDirectory)) {
        if ((Test-Path -LiteralPath $taskDirectory) -and ((Get-Item -LiteralPath $taskDirectory).Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Installation path is a reparse point.' }
        New-Item -ItemType Directory -Path $taskDirectory -Force | Out-Null
        Set-RLinkAcl $taskDirectory $true $true
    }
    if ($taskExistingService -and $taskExistingService.State -eq 'Running') {
        Stop-Service -Name 'RLinkFabric'
        (Get-Service -Name 'RLinkFabric').WaitForStatus('Stopped', [TimeSpan]::FromSeconds(20))
    }
    Copy-Item -LiteralPath (Join-Path $taskPayload 'rlink-agent.exe') -Destination $taskExe -Force
    Copy-Item -LiteralPath (Join-Path $taskPayload 'wintun.dll') -Destination (Join-Path $taskBinaryDirectory 'wintun.dll') -Force
    Set-RLinkAcl $taskExe $false $true
    Set-RLinkAcl (Join-Path $taskBinaryDirectory 'wintun.dll') $false $true
    if (Test-Path -LiteralPath (Join-Path $taskStateDirectory 'status.json')) { Set-RLinkAcl (Join-Path $taskStateDirectory 'status.json') $false $true }
    if (-not (Test-Path -LiteralPath $taskConfig)) {
        Write-Output 'Enrolling this device; the private key stays on this computer.'
        $taskPlain = & $PythonPath (Join-Path $taskPayload 'decrypt-enrollment.py')
        if ($LASTEXITCODE -ne 0) { throw 'Enrollment package validation failed.' }
        $taskEnrollment = $taskPlain | ConvertFrom-Json
        $taskPlain = $null
        if ($taskEnrollment.device -ine $env:COMPUTERNAME -or $taskEnrollment.control_url -ne 'https://175.178.16.90/r-link') { throw 'Enrollment belongs to another device or service.' }
        try {
            $taskEnrollment.enrollment_token | & $taskExe enroll --server $taskEnrollment.control_url --name $taskEnrollment.device --token-stdin --config $taskConfig
            if ($LASTEXITCODE -ne 0) { throw 'Device enrollment failed.' }
        } finally { $taskEnrollment = $null }
    }
    Set-RLinkAcl $taskConfig $false $false
    $taskSc = Join-Path $env:SystemRoot 'System32\sc.exe'
    if (-not $taskExistingService) {
        New-Service -Name 'RLinkFabric' -DisplayName 'R-Link private network' -BinaryPathName $taskServiceCommand -StartupType Automatic | Out-Null
    } else {
        $taskServiceUpdate = Invoke-CimMethod -InputObject $taskExistingService -MethodName Change -Arguments @{ PathName = $taskServiceCommand; StartMode = 'Automatic' }
        if ($taskServiceUpdate.ReturnValue -ne 0) { throw 'Agent service configuration failed.' }
    }
    & $taskSc failure RLinkFabric reset= 86400 actions= 'restart/5000/restart/10000/restart/30000' | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Agent service recovery configuration failed.' }
    $taskRule = Get-NetFirewallRule -Name 'RLinkFabric-UDP' -ErrorAction SilentlyContinue
    if ($taskRule) { Remove-NetFirewallRule -Name 'RLinkFabric-UDP' }
    New-NetFirewallRule -Name 'RLinkFabric-UDP' -DisplayName 'R-Link encrypted peer traffic' -Direction Inbound -Action Allow -Program $taskExe -Protocol UDP -LocalPort 51822 | Out-Null
    Start-Service -Name 'RLinkFabric'
    $taskReady = $false
    for ($taskAttempt = 0; $taskAttempt -lt 180; $taskAttempt++) {
        if ((Get-Service -Name 'RLinkFabric').Status -ne 'Running') { throw 'The agent service stopped before the tunnel was ready.' }
        $taskPreviousPreference = $ErrorActionPreference
        try {
            $ErrorActionPreference = 'Continue'
            $taskRaw = & $taskExe status --json 2>$null
            $taskStatusExit = $LASTEXITCODE
        } finally { $ErrorActionPreference = $taskPreviousPreference }
        if ($taskStatusExit -eq 0 -and $taskRaw) {
            $taskStatus = $taskRaw | ConvertFrom-Json
            if ($taskStatus.mode -eq 'vpn' -and $taskStatus.control.connected -and $taskStatus.tun.ready) { $taskReady = $true; break }
        }
        Start-Sleep -Seconds 1
    }
    if (-not $taskReady) { throw 'The agent is installed; the real tunnel is not ready yet. Check the public status.' }
    Write-Output ('R-Link network interface is ready: ' + $taskStatus.tun.ip)
    Write-Output 'Peer handshakes and service connectivity are verified separately.'
} finally { $taskLock.ReleaseMutex(); $taskLock.Dispose() }
