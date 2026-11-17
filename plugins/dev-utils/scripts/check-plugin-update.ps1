# SessionStart: verifica se a marketplace "dev-jr" tem versao nova do plugin dev-utils
# em relacao ao origin/main e, se tiver, atualiza o plugin sozinho via CLI do Claude Code.
$ErrorActionPreference = "SilentlyContinue"

# [Alteração] Autor: vcj81 | Data/Hora: 17/11/2026 15:04
# saida do hook: contexto pro Claude + aviso visivel pro usuario, em UTF-8 por causa do log do claude
function Write-HookOutput([string]$contexto, [string]$aviso) {
    $obj = @{
        hookSpecificOutput = @{
            hookEventName     = "SessionStart"
            additionalContext = $contexto
        }
    }
    if ($aviso) { $obj.systemMessage = $aviso }
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $obj | ConvertTo-Json -Compress
}

# [Alteração] Autor: vcj81 | Data/Hora: 17/11/2026 15:04
# le o "version" por regex: o PS 5.1 decodifica a saida do git em ANSI e os acentos da description quebrariam o JSON
function Get-VersaoManifesto([string]$texto) {
    if ($texto -match '"version"\s*:\s*"([^"]+)"') { return $Matches[1] }
    return $null
}

$mktDir = Join-Path $env:USERPROFILE ".claude\plugins\marketplaces\dev-jr"
if (-not (Test-Path $mktDir)) { exit 0 }

git -C $mktDir fetch origin main --quiet 2>$null
$behind = git -C $mktDir rev-list "HEAD..origin/main" --count 2>$null

# [Alteração] Autor: vcj81 | Data/Hora: 17/11/2026 15:04
# compara a versao carregada neste projeto (pode ser instalacao antiga de escopo projeto) com a do origin/main,
# porque a marketplace pode estar em dia (atualizada por outro projeto) e este projeto continuar na versao velha
$atual = Get-VersaoManifesto ([System.IO.File]::ReadAllText((Join-Path (Split-Path -Parent $PSScriptRoot) ".claude-plugin\plugin.json")))
$nova = Get-VersaoManifesto ((git -C $mktDir show "origin/main:plugins/dev-utils/.claude-plugin/plugin.json" 2>$null) -join "`n")
$atrasada = $behind -and [int]$behind -gt 0
$temVersaoNova = $false
if ($atual -and $nova) {
    try { $temVersaoNova = [version]$nova -gt [version]$atual } catch { $temVersaoNova = $nova -ne $atual }
}
if (-not $atrasada -and -not $temVersaoNova) { exit 0 }

# [Alteração] Autor: vcj81 | Data/Hora: 17/11/2026 15:04
# atualiza sozinho (equivale a /plugin marketplace update dev-jr + /plugin update dev-utils) em cada escopo que vale
# para este projeto. --scope explicito: sem ele o claude escolhe o escopo user mesmo com instalacao de escopo projeto
# mais antiga na pasta. O resultado vem do --json (o exit code e 0 tambem quando nada foi atualizado)
$manual = "/plugin marketplace update dev-jr e /plugin update dev-utils"
if (-not (Get-Command claude)) {
    if ($temVersaoNova) {
        Write-HookOutput "Ha versao nova do plugin dev-utils (${atual} -> ${nova}), mas o comando claude nao esta no PATH para atualizar sozinho. Avise o usuario e sugira rodar $manual."
    }
    exit 0
}
if ($env:CLAUDE_PROJECT_DIR) { Set-Location -LiteralPath $env:CLAUDE_PROJECT_DIR }

if ($atrasada) { $null = claude plugin marketplace update dev-jr 2>&1 }
if (-not $temVersaoNova) { exit 0 }

$atualizados = @()
$falhas = @()
foreach ($escopo in "user", "project", "local") {
    $r = (claude plugin update dev-utils@dev-jr --scope $escopo --json 2>$null | Select-Object -Last 1) | ConvertFrom-Json
    if (-not $r) { $falhas += "${escopo}: sem resposta do claude"; continue }
    if ($r.updateOutcome -eq "updated") { $atualizados += "$escopo ($($r.oldVersion) -> $($r.newVersion))" }
    elseif ($r.outcome -eq "failed" -and $r.failureCode -ne "not_installed_at_scope") { $falhas += "${escopo}: $($r.message)" }
}

if ($atualizados.Count -gt 0) {
    Write-HookOutput "O plugin dev-utils foi atualizado automaticamente: $($atualizados -join ', '). Esta sessao ainda roda a versao ${atual}; avise o usuario que a versao nova entra com /reload-plugins ou na proxima sessao." "dev-utils atualizado para ${nova} - rode /reload-plugins para aplicar"
} elseif ($falhas.Count -gt 0) {
    Write-HookOutput "Ha versao nova do plugin dev-utils (${atual} -> ${nova}), mas a atualizacao automatica falhou ($($falhas -join '; ')). Avise o usuario e sugira rodar $manual."
} else {
    Write-HookOutput "A versao ${nova} do plugin dev-utils ja esta instalada, mas esta sessao carregou a ${atual}. Avise o usuario para rodar /reload-plugins." "dev-utils ${nova} ja instalado - rode /reload-plugins para aplicar"
}
exit 0
