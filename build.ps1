# Construit l'application autonome dans dist\CTgraph\ (CTgraph.exe + dépendances).
# Usage : powershell -ExecutionPolicy Bypass -File build.ps1 [-Dist dossier]
# -Dist : dossier de sortie (défaut : dist). Utile quand CTgraph.exe est en cours d'utilisation :
#         compilez ailleurs (-Dist dist_nouveau) puis remplacez dist\CTgraph une fois le logiciel fermé.
param([string]$Dist = "dist")
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if ($Dist -eq "dist") {
    $running = Get-Process CTgraph -ErrorAction SilentlyContinue | Where-Object { $_.Path -like (Join-Path $PSScriptRoot "dist\*") }
    if ($running) {
        Write-Host "CTgraph.exe est en cours d'exécution depuis dist\ : fermez-le, ou compilez ailleurs avec -Dist dist_nouveau."
        exit 1
    }
}

$py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Host "Création de l'environnement virtuel..."
    py -3.12 -m venv .venv
    & $py -m pip install --upgrade pip
    & $py -m pip install -r requirements.txt
}

& $py tools\make_icon.py
& $py tools\make_sample.py exemples

# Horodatage de cette compilation, affiché dans Aide > À propos. Le fichier est remis à vide à la fin
# pour que le dépôt Git reste propre (depuis les sources, le logiciel affiche « exécuté depuis les sources »).
function Ecrire-BuildInfo([string]$valeur) {
    @(
        '"""Horodatage de compilation. Fichier reecrit par build.ps1 a chaque compilation (ASCII volontaire)."""',
        '',
        "BUILD_TIME = `"$valeur`"   # AAAA-MM-JJ HH:MM:SS ; vide = non compile (execution depuis les sources)"
    ) | Set-Content -Path (Join-Path $PSScriptRoot "ctgraph\build_info.py") -Encoding Ascii
}
$stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Ecrire-BuildInfo $stamp
Write-Host "Compilation horodatée : $stamp"

# Compilation dans un dossier de travail, puis remplacement de $Dist\CTgraph d'un seul coup.
$stage = Join-Path $PSScriptRoot "build\stage"
if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
& $py -m PyInstaller --noconfirm --clean --windowed --name CTgraph `
    --distpath $stage --icon assets\ctgraph.ico `
    --exclude-module PySide6.QtQml --exclude-module PySide6.QtQuick `
    --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.QtWebEngineWidgets `
    --exclude-module PySide6.QtMultimedia --exclude-module PySide6.QtSql --exclude-module PySide6.QtTest `
    --exclude-module PySide6.QtSvg --exclude-module PySide6.QtPdf --exclude-module PySide6.QtPdfWidgets `
    --exclude-module PySide6.QtXml --exclude-module PySide6.QtDBus --exclude-module PySide6.QtConcurrent `
    --exclude-module PySide6.QtHelp --exclude-module PySide6.QtDesigner --exclude-module PySide6.QtUiTools `
    --exclude-module PySide6.Qt3DCore --exclude-module PySide6.QtCharts --exclude-module PySide6.QtDataVisualization `
    --exclude-module PySide6.QtBluetooth --exclude-module PySide6.QtPositioning --exclude-module PySide6.QtSensors `
    --exclude-module PySide6.QtRemoteObjects --exclude-module PySide6.QtScxml --exclude-module PySide6.QtStateMachine `
    --exclude-module PySide6.QtTextToSpeech --exclude-module PySide6.QtWebChannel --exclude-module PySide6.QtWebSockets `
    --exclude-module PySide6.QtNfc --exclude-module PySide6.QtLocation --exclude-module PySide6.QtHttpServer `
    --exclude-module PySide6.QtGraphs --exclude-module PySide6.QtSpatialAudio --exclude-module PySide6.QtQuick3D `
    --exclude-module PySide6.QtQuickWidgets --exclude-module PySide6.QtQuickControls2 --exclude-module PySide6.QtQuickTest `
    --exclude-module PySide6.QtAsyncio --exclude-module tkinter --exclude-module pydoc `
    --exclude-module matplotlib --exclude-module PyQt5 --exclude-module psutil --exclude-module yaml `
    --exclude-module pytest `
    run.py
# QtOpenGL et QtOpenGLWidgets restent inclus : la vue 3D en aura besoin.
# QtSerialPort n'est pas utilisé : la liaison RS232 passera par pyserial.
$code = $LASTEXITCODE
Ecrire-BuildInfo ""
if ($code -ne 0 -or -not (Test-Path "$stage\CTgraph\CTgraph.exe")) {
    Write-Host "Compilation PyInstaller échouée : $Dist\CTgraph est laissé tel quel."
    exit 1
}
if (-not (Get-ChildItem "$stage\CTgraph\_internal" -Filter "python3*.dll")) {
    Write-Host "python3xx.dll absent de _internal : compilation incomplète, $Dist\CTgraph est laissé tel quel."
    exit 1
}

if (Test-Path README.md) { Copy-Item README.md "$stage\CTgraph\LISEZMOI.md" -Force }
if (Test-Path exemples) {
    New-Item -ItemType Directory -Force "$stage\CTgraph\exemples" | Out-Null
    Copy-Item exemples\*.ctg "$stage\CTgraph\exemples\" -Force -ErrorAction SilentlyContinue
}

New-Item -ItemType Directory -Force $Dist | Out-Null
$target = Join-Path $Dist "CTgraph"
$old = Join-Path $Dist "CTgraph.ancien"
if (Test-Path $old) { Remove-Item $old -Recurse -Force }
if (Test-Path $target) { Move-Item $target $old }
Move-Item "$stage\CTgraph" $target
if (Test-Path $old) { Remove-Item $old -Recurse -Force }
Write-Host ""
Write-Host "Terminé : $Dist\CTgraph\CTgraph.exe"
