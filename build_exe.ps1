# Construit PlanEtudes.exe (PyInstaller --onefile --windowed).
# Usage :  .\.venv\Scripts\Activate.ps1 ; .\build_exe.ps1
# ou      .\.venv\Scripts\pyinstaller ... (la commande ci-dessous, telle quelle).

& "$PSScriptRoot\.venv\Scripts\pyinstaller.exe" `
    --noconfirm --onefile --windowed `
    --name PlanEtudes `
    --add-data "docs\schema\cours.schema.json;docs\schema" `
    --add-data "docs\PROMPT_EXTRACTION.md;docs" `
    --add-data "src\planner\ui\style.qss;planner\ui" `
    "$PSScriptRoot\src\planner\app.py"

Write-Host "Exe : $PSScriptRoot\dist\PlanEtudes.exe"
