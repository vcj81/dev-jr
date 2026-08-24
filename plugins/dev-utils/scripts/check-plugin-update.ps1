# SessionStart: verifica se o cache local da marketplace "dev-jr" esta atrasado
# em relacao ao origin/main e sugere ao Claude perguntar sobre atualizar o plugin.
$ErrorActionPreference = "SilentlyContinue"

$mktDir = Join-Path $env:USERPROFILE ".claude\plugins\marketplaces\dev-jr"
if (-not (Test-Path $mktDir)) { exit 0 }

git -C $mktDir fetch origin main --quiet 2>$null
$behind = git -C $mktDir rev-list "HEAD..origin/main" --count 2>$null

if ($behind -and [int]$behind -gt 0) {
    $msg = "Ha $behind commit(s) novo(s) na marketplace dev-jr (podem trazer atualizacao do plugin dev-utils). Pergunte ao usuario se deseja rodar /plugin marketplace update dev-jr e /plugin update dev-utils."
    $obj = @{
        hookSpecificOutput = @{
            hookEventName    = "SessionStart"
            additionalContext = $msg
        }
    }
    $obj | ConvertTo-Json -Compress
}
exit 0
