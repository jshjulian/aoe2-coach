# Narrow, opt-in Windows bridge for the offline research collector.
# Caller supplies $RequestJson. No memory access, private interfaces, installers,
# global desktop capture, entitlement changes or process-name-based termination.
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=New-Object System.Text.UTF8Encoding($false)
$r=$RequestJson | ConvertFrom-Json
$allowed=@('CaptureAge','AoE2DE','AoE2DE_s','BattleServer','gamelaunchhelper')
function Fingerprint($p) {
 [PSCustomObject]@{pid=$p.Id;name=$p.ProcessName;started_utc_ticks=$p.StartTime.ToUniversalTime().Ticks.ToString()}
}
function Matching($f) {
 if ($allowed -notcontains $f.name) {throw 'Process outside application allowlist'}
 $p=Get-Process -Id ([int]$f.pid) -ErrorAction SilentlyContinue
 if (!$p) {return $null}
 if ($p.ProcessName -ne $f.name -or $p.StartTime.ToUniversalTime().Ticks.ToString() -ne $f.started_utc_ticks) {return $null}
 return $p
}
function Save-Receipt($f) {
 # Persist immediately, before responding, so interrupted callers can recover.
 [System.IO.File]::WriteAllText($r.receipt_path,($f | ConvertTo-Json -Depth 5),(New-Object System.Text.UTF8Encoding($false)))
}
function Find-SteamLaunch($intent) {
 $client=Get-Process -Id ([int]$intent.steam_client.pid) -ErrorAction SilentlyContinue
 if (!$client -or $client.ProcessName -ne 'steam' -or $client.StartTime.ToUniversalTime().Ticks.ToString() -ne $intent.steam_client.started_utc_ticks) {throw 'Steam client identity changed; no game ownership guessed'}
 $found=@(Get-Process -Name AoE2DE_s -ErrorAction SilentlyContinue | Where-Object {
  $_.Path -eq $intent.exe_path -and $_.StartTime.ToUniversalTime().Ticks -ge [long]$intent.started_utc_ticks -and $_.StartTime.ToUniversalTime().Ticks -le ([long]$intent.started_utc_ticks+600000000)
 } | ForEach-Object {
  $p=$_; $meta=Get-CimInstance Win32_Process -Filter ("ProcessId="+$p.Id)
  if ($meta.ParentProcessId -eq $client.Id) {
   $f=Fingerprint $p
   $f | Add-Member -NotePropertyName exe_path -NotePropertyValue $p.Path
   $f | Add-Member -NotePropertyName ownership_basis -NotePropertyValue 'explicit_exclusive_steam_launch_unique_path_parent_time'
   $f
  }
 })
 if ($found.Count -gt 1) {throw 'Ambiguous Steam game processes; none adopted'}
 if ($found.Count -eq 1) {return $found[0]}
 return $null
}
switch ($r.action) {
 'inventory' {
  $parents=@{}
  Get-CimInstance Win32_Process -Filter "Name='CaptureAge.exe' OR Name='AoE2DE.exe' OR Name='AoE2DE_s.exe' OR Name='BattleServer.exe' OR Name='gamelaunchhelper.exe'" | ForEach-Object {$parents[[int]$_.ProcessId]=[int]$_.ParentProcessId}
  $rows=@(Get-Process -ErrorAction SilentlyContinue | Where-Object {$allowed -contains $_.ProcessName} | ForEach-Object {
   try {$f=Fingerprint $_; $f | Add-Member -NotePropertyName parent_pid -NotePropertyValue $parents[[int]$_.Id]; $f} catch {if (!$_.Exception.Message.Contains('exited')) {throw}}
  })
  ConvertTo-Json -InputObject $rows -Depth 5
 }
 'launch_ca' {
  if (@(Get-Process -Name CaptureAge -ErrorAction SilentlyContinue).Count) {throw 'CaptureAge is already running; refusing to take ownership'}
  $exe=Join-Path $env:LOCALAPPDATA 'Programs\CaptureAge\CaptureAge.exe'
  if (!(Test-Path -LiteralPath $exe)) {throw 'Installed CaptureAge not found; no installation attempted'}
  $p=Start-Process -FilePath $exe -PassThru
  $f=Fingerprint $p
  Save-Receipt $f
  $f | ConvertTo-Json
 }
 'launch_game' {
  if ($r.launcher -ne 'steam') {throw 'Explicit supported launcher steam is required; no Xbox fallback'}
  if (@(Get-Process -Name AoE2DE,AoE2DE_s,BattleServer,gamelaunchhelper -ErrorAction SilentlyContinue).Count) {throw 'Game is already running; refusing to take ownership'}
  $exe=Get-Item -LiteralPath $r.game_exe
  if ($exe.Name -ne 'AoE2DE_s.exe') {throw 'Select the explicit installed Steam game executable'}
  $clients=@(Get-Process -Name steam -ErrorAction SilentlyContinue)
  if ($clients.Count -ne 1) {throw 'One existing Steam client required; it will never be owned or closed by this collector'}
  $client=$clients[0]
  $intent=[PSCustomObject]@{exe_path=$exe.FullName;started_utc_ticks=[DateTime]::UtcNow.Ticks.ToString();steam_client=(Fingerprint $client);steam_app_id=813780;scope='explicit_exclusive_offline_game_launch_and_cleanup'}
  [System.IO.File]::WriteAllText($r.intent_path,($intent | ConvertTo-Json -Depth 5),(New-Object System.Text.UTF8Encoding($false)))
  # Public Steam launch command: do NOT invoke the game EXE outside Steam.
  Start-Process -FilePath $client.Path -ArgumentList @('-applaunch','813780') -WorkingDirectory (Split-Path $client.Path)
  $deadline=[DateTime]::UtcNow.AddSeconds(30)
  do {
   $f=Find-SteamLaunch $intent
   if ($f) {Save-Receipt $f; $f | ConvertTo-Json -Depth 5; break}
   Start-Sleep -Milliseconds 400
  } while ([DateTime]::UtcNow -lt $deadline)
  if (!$f) {throw 'Steam launch not yet verified; intent retained for recovery; no process guessed'}
 }
 'recover_steam_launch' {
  $f=Find-SteamLaunch $r.intent
  if ($f) {Save-Receipt $f; $f | ConvertTo-Json -Depth 5} else {'null'}
 }
 'adopt_steam_relaunch' {
  # Steam may relaunch its game under the pre-existing Steam client. Require
  # an explicit operator assertion plus path, parent, time and empty-baseline checks.
  $p=Get-Process -Id ([int]$r.pid)
  $original=$r.original_game
  if ($p.ProcessName -ne 'AoE2DE_s' -or $p.Path -ne $original.exe_path -or $p.StartTime.ToUniversalTime().Ticks -lt [long]$original.started_utc_ticks) {throw 'Not the expected new Steam game process'}
  $meta=Get-CimInstance Win32_Process -Filter ("ProcessId="+$p.Id)
  $parent=Get-Process -Id $meta.ParentProcessId
  if ($parent.ProcessName -ne 'steam' -or $parent.StartTime.ToUniversalTime().Ticks -ge [long]$original.started_utc_ticks) {throw 'Expected pre-existing Steam client parent not verified'}
  $f=Fingerprint $p
  $f | Add-Member -NotePropertyName exe_path -NotePropertyValue $p.Path
  $f | Add-Member -NotePropertyName ownership_basis -NotePropertyValue 'operator_confirmed_new_steam_relaunch_exact_path_parent_and_time'
  Save-Receipt $f
  $f | ConvertTo-Json
 }
 'capture' {
  $p=Matching $r.target
  if (!$p -or $p.ProcessName -ne 'CaptureAge' -or !$p.MainWindowHandle -or $p.MainWindowTitle -ne 'CaptureAge') {throw 'Owned CaptureAge main window unavailable'}
  Add-Type -AssemblyName System.Drawing
  Add-Type @'
using System;
using System.Runtime.InteropServices;
public class OwnedWindowCapture {
 [StructLayout(LayoutKind.Sequential)] public struct Rect {public int Left,Top,Right,Bottom;}
 [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
 [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr hwnd);
 [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hwnd);
 [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hwnd,out Rect rect);
 [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hwnd,IntPtr hdc,uint flags);
}
'@
  $null=[OwnedWindowCapture]::SetProcessDPIAware()
  if ([OwnedWindowCapture]::IsIconic($p.MainWindowHandle) -or ![OwnedWindowCapture]::IsWindowVisible($p.MainWindowHandle)) {throw 'Target minimized/hidden; no desktop fallback'}
  $rect=New-Object OwnedWindowCapture+Rect
  if (![OwnedWindowCapture]::GetWindowRect($p.MainWindowHandle,[ref]$rect)) {throw 'Cannot obtain app window bounds'}
  $width=$rect.Right-$rect.Left; $height=$rect.Bottom-$rect.Top
  if ($width -ne 3440 -or $height -ne 1440) {throw 'Unsupported app window resolution; refusing guessed coordinates'}
  if (Test-Path -LiteralPath $r.output_path) {throw 'Snapshot already exists'}
  $bitmap=New-Object System.Drawing.Bitmap $width,$height,([System.Drawing.Imaging.PixelFormat]::Format24bppRgb)
  $graphics=[System.Drawing.Graphics]::FromImage($bitmap)
  try {
   $hdc=$graphics.GetHdc()
   try {$ok=[OwnedWindowCapture]::PrintWindow($p.MainWindowHandle,$hdc,2)} finally {$graphics.ReleaseHdc($hdc)}
   if (!$ok) {throw 'PrintWindow failed; no desktop fallback'}
   $bitmap.Save($r.output_path,[System.Drawing.Imaging.ImageFormat]::Png)
  } finally {$graphics.Dispose();$bitmap.Dispose()}
  [PSCustomObject]@{target=(Fingerprint $p);width=$width;height=$height;captured_at=[DateTime]::UtcNow.ToString('o')} | ConvertTo-Json -Depth 5
 }
 'close' {
  $p=Matching $r.target
  if (!$p) {[PSCustomObject]@{status='absent_or_reused_pid_not_touched'} | ConvertTo-Json; break}
  if ($r.force -eq $true) {
   Stop-Process -Id $p.Id -Force
   [PSCustomObject]@{status='forced_exact_owned_fingerprint'} | ConvertTo-Json
  } else {
   $requested=$false
   if ($p.MainWindowHandle) {$requested=$p.CloseMainWindow()}
   [PSCustomObject]@{status='graceful_requested';requested=$requested} | ConvertTo-Json
  }
 }
 default {throw 'Unknown bridge action'}
}
