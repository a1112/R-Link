$ErrorActionPreference = 'Stop'
# Load only port helper definitions through the AST. Never execute installer
# main, require elevation, enroll, touch SCM, or modify firewall/route state.
$taskTokens=$null
$taskErrors=$null
$taskInstaller=Join-Path $PSScriptRoot 'install-windows.ps1'
$taskAst=[Management.Automation.Language.Parser]::ParseFile($taskInstaller,[ref]$taskTokens,[ref]$taskErrors)
if($taskErrors.Count){throw 'Installer syntax validation failed.'}
foreach($taskFunction in $taskAst.FindAll({param($taskNode) $taskNode -is [Management.Automation.Language.FunctionDefinitionAst]},$true)) {
    if($taskFunction.Name -in @('ConvertTo-RLinkUdpExcludedRanges','Test-RLinkUdpPortAvailable','Select-RLinkUdpPort','Get-RLinkServiceUdpPort')){Invoke-Expression $taskFunction.Extent.Text}
}
$taskRanges=@(ConvertTo-RLinkUdpExcludedRanges @('Protocol udp Port Exclusion Ranges','Start Port End Port','     51732       51831','     52000       52099     *'))
if($taskRanges.Count -ne 2 -or $taskRanges[0].Start -ne 51732 -or $taskRanges[0].End -ne 51831){throw 'Exclusion fixture failed.'}
$taskPrefix='"C:\Program Files\R-Link\Agent\rlink-agent.exe" run --config "C:\ProgramData\R-Link\Agent\config.json" --udp-port '
if((Get-RLinkServiceUdpPort ($taskPrefix+'51922') $taskPrefix) -ne 51922){throw 'Existing alternate-port service fixture failed.'}
$taskReject=$false
try{Get-RLinkServiceUdpPort ($taskPrefix+'51922 --no-tun') $taskPrefix|Out-Null}catch{$taskReject=$true}
if(-not $taskReject){throw 'Unrelated service command was accepted.'}
# Verify the real exclusive UDP bind rejects an already owned endpoint.
$taskSocket=New-Object Net.Sockets.Socket([Net.Sockets.AddressFamily]::InterNetwork,[Net.Sockets.SocketType]::Dgram,[Net.Sockets.ProtocolType]::Udp)
try {
    $taskSocket.ExclusiveAddressUse=$true
    $taskSocket.Bind((New-Object Net.IPEndPoint([Net.IPAddress]::Loopback,0)))
    $taskBoundPort=$taskSocket.LocalEndPoint.Port
    if(Test-RLinkUdpPortAvailable $taskBoundPort){throw 'An already owned UDP endpoint was accepted.'}
} finally {$taskSocket.Dispose()}
if(-not (Test-RLinkUdpPortAvailable $taskBoundPort)){throw 'An available UDP endpoint was rejected after its owner closed.'}
# Deterministic candidate fixtures do not depend on this machine's exclusions.
function Test-RLinkUdpPortAvailable([int]$Port){return $Port -in @(41822,41823)}
if((Select-RLinkUdpPort $taskRanges 51822) -ne 41822){throw 'Excluded default did not fall back to a low verified port.'}
if((Select-RLinkUdpPort @() 41823) -ne 41823){throw 'Existing usable alternate port was not preserved.'}
if((Select-RLinkUdpPort @([pscustomobject]@{Start=41822;End=41822}) 51822) -ne 41823){throw 'Excluded first low port did not fall back to the next verified port.'}
$taskReject=$false
try{Select-RLinkUdpPort @([pscustomobject]@{Start=1;End=65535}) 51822|Out-Null}catch{$taskReject=$true}
if(-not $taskReject){throw 'All-excluded fixture did not fail safely.'}
Write-Output 'Installer syntax, exclusion, occupied-port and fallback fixtures passed.'
