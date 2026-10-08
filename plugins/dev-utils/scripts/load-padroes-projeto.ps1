# SessionStart: injeta os Padroes de Projeto (instrucoes/padroes-projeto.md) como contexto
# da sessao, para que o Claude siga esses padroes em todo projeto que usa o plugin dev-utils
# sem precisar de comando/skill. Substitui a antiga skill /dev-padroes-projeto.
# Se o arquivo nao existir ou der erro, sai em silencio para nao travar o inicio da sessao.
$ErrorActionPreference = "SilentlyContinue"

# CLAUDE_PLUGIN_ROOT vem do Claude Code; fallback pela pasta do script (scripts/..) para testes manuais
$pluginRoot = $env:CLAUDE_PLUGIN_ROOT
if (-not $pluginRoot) { $pluginRoot = Split-Path -Parent $PSScriptRoot }

$arquivo = Join-Path $pluginRoot "instrucoes\padroes-projeto.md"
if (-not (Test-Path -LiteralPath $arquivo)) { exit 0 }

# le como UTF-8 explicito: o PowerShell 5.1 usa ANSI por padrao e estragaria os acentos.
# ReadAllText (e nao Get-Content) porque o Get-Content anexa propriedades (PSPath etc.) a string
# e o ConvertTo-Json do PS 5.1 serializaria isso como objeto, nao como texto.
$texto = [System.IO.File]::ReadAllText($arquivo, [System.Text.Encoding]::UTF8)
if (-not $texto) { exit 0 }

# formato que o Claude Code espera de um hook SessionStart para adicionar contexto
$obj = @{
    hookSpecificOutput = @{
        hookEventName     = "SessionStart"
        additionalContext = $texto
    }
}

# saida em UTF-8 pelo mesmo motivo da leitura (o console do Windows nao e UTF-8 por padrao)
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$obj | ConvertTo-Json -Compress
exit 0
