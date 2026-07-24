# Hook PreToolUse (matcher: Write) - forca documentacao didatica em arquivo novo de codigo.
# Bloqueia (deny) a escrita se o arquivo e novo, e de uma linguagem mapeada,
# tem mais que poucas linhas, e nao tem pelo menos 2 linhas de comentario
# (proxy para "explicacao no topo" + "comentario inline" exigidos pela skill dev-novo-arquivo).
# Heuristica grosseira de proposito: nao avalia qualidade do texto, so presenca minima.

$ErrorActionPreference = 'Stop'

try {
    $stdin = [Console]::In.ReadToEnd()
    $payload = $stdin | ConvertFrom-Json
} catch {
    exit 0
}

$filePath = $payload.tool_input.file_path
$content = $payload.tool_input.content
if (-not $content) { $content = $payload.tool_input.file_text }

if (-not $filePath -or -not $content) { exit 0 }

# so entra em arquivo novo - Write sobre arquivo existente nao aciona
if (Test-Path -LiteralPath $filePath) { exit 0 }

$ext = [System.IO.Path]::GetExtension($filePath).TrimStart('.').ToLower()

$skipExt = @('json','yml','yaml','lock','txt','csv','xml','svg','png','jpg','jpeg','gif','ico','env','toml','md','gitignore','ttf','woff','woff2')
if ($skipExt -contains $ext) { exit 0 }

$hashExt  = @('py','rb','ps1','sh','pl')
$slashExt = @('js','jsx','ts','tsx','java','c','cpp','h','hpp','cs','go','php','css','scss','less','kt','swift','rs')
$sqlExt   = @('sql')
$htmlExt  = @('html','htm')

if ($hashExt -contains $ext) { $pattern = '^\s*#' }
elseif ($slashExt -contains $ext) { $pattern = '^\s*(//|/\*|\*)' }
elseif ($sqlExt -contains $ext) { $pattern = '^\s*--' }
elseif ($htmlExt -contains $ext) { $pattern = '<!--' }
else { exit 0 }  # linguagem nao mapeada - nao forca

$lines = $content -split "`n"
$nonBlank = $lines | Where-Object { $_.Trim() -ne '' }
if ($nonBlank.Count -le 3) { exit 0 }  # arquivo trivial - nao forca

$commentLines = ($lines | Where-Object { $_ -match $pattern }).Count

if ($commentLines -lt 2) {
    $reason = "Skill dev-novo-arquivo: arquivo novo de codigo sem documentacao didatica minima. Antes de escrever, adicione (1) explicacao geral no topo (2-4 linhas, sintaxe de comentario da linguagem) e (2) comentarios inline nos trechos relevantes, em PT-BR. Reescreva o Write com os comentarios incluidos."
    $output = @{
        hookSpecificOutput = @{
            hookEventName = "PreToolUse"
            permissionDecision = "deny"
            permissionDecisionReason = $reason
        }
    } | ConvertTo-Json -Depth 5 -Compress
    Write-Output $output
    exit 0
}

exit 0
