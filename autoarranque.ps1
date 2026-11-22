# Hace que Jarvis arranque (o deje de arrancar) junto con Windows.
# Uso: powershell -ExecutionPolicy Bypass -File autoarranque.ps1 instalar | quitar | estado
param([string]$accion = "instalar")

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$startup = [Environment]::GetFolderPath("Startup")
$lnk = Join-Path $startup "Jarvis.lnk"

if ($accion -eq "quitar") {
    if (Test-Path $lnk) { Remove-Item $lnk; Write-Host "Jarvis ya no arranca con Windows." }
    else { Write-Host "No estaba instalado el autoarranque." }
    exit
}

if ($accion -eq "estado") {
    if (Test-Path $lnk) {
        $s = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)
        Write-Host "Jarvis arranca con Windows desde: $($s.WorkingDirectory)"
    } else { Write-Host "Jarvis NO arranca con Windows." }
    exit
}

$pythonw = Join-Path $root ".venv\Scripts\pythonw.exe"   # pythonw = sin ventana de consola
if (-not (Test-Path $pythonw)) { Write-Host "Falta el entorno .venv. Corre instalar.bat primero."; exit 1 }

# El acceso directo siempre apunta a ESTA carpeta, asi que si moviste el proyecto,
# volver a correr instalar.bat lo deja apuntando bien.
$ws = New-Object -ComObject WScript.Shell
$s = $ws.CreateShortcut($lnk)
$s.TargetPath = $pythonw
$s.Arguments = "-m jarvis"
$s.WorkingDirectory = $root
$s.Description = "Asistente de voz Jarvis"
$s.Save()
Write-Host "Listo: Jarvis arrancara al iniciar Windows."
Write-Host "   Carpeta: $root"

if ($root -match "OneDrive") {
    Write-Host ""
    Write-Host "AVISO: el proyecto esta dentro de OneDrive." -ForegroundColor Yellow
    Write-Host "OneDrive puede mover o liberar estos archivos y romper el arranque."
    Write-Host "Conviene moverlo a C:\Jarvis y volver a correr instalar.bat."
}
