# Uso: autoarranque.ps1 instalar | quitar
param([string]$accion = "instalar")

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$startup = [Environment]::GetFolderPath("Startup")
$lnk = Join-Path $startup "Jarvis.lnk"

if ($accion -eq "quitar") {
    if (Test-Path $lnk) { Remove-Item $lnk; Write-Host "Jarvis ya no arranca con Windows." }
    else { Write-Host "No estaba instalado el autoarranque." }
    exit
}

$pythonw = Join-Path $root ".venv\Scripts\pythonw.exe"   # pythonw = sin ventana de consola
if (-not (Test-Path $pythonw)) { Write-Host "Falta el entorno .venv. Corre instalar.bat primero."; exit 1 }

$ws = New-Object -ComObject WScript.Shell
$s = $ws.CreateShortcut($lnk)
$s.TargetPath = $pythonw
$s.Arguments = "-m jarvis"
$s.WorkingDirectory = $root
$s.Save()
Write-Host "Listo: Jarvis arrancara al iniciar Windows ($lnk)."
