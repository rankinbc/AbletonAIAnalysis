$Content = Get-Content 'C:\claude-workspace\AbletonAIAnalysis\.claude-container\config.yaml' -Raw
if ($Content -match 'cpus:\s*"([^"]+)"') {
    Write-Host "Quoted Match: [$($Matches[1])]"
}
elseif ($Content -match 'cpus:\s*([0-9.]+)') {
    Write-Host "Unquoted Match: [$($Matches[1])]"
}
