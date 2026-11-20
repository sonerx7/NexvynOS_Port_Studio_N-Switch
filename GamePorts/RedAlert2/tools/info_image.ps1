param([string]$Path)
Add-Type -AssemblyName System.Drawing
$img = [System.Drawing.Image]::FromFile($Path)
Write-Output "File: $Path | Size: $($img.Width)x$($img.Height)"
$img.Dispose()

