---
name: dev-commit-push
description: Commit + push das últimas alterações no git. Lista os arquivos alterados e propõe a mensagem de commit para aprovação ou edição do usuário ANTES de commitar e enviar. Usar quando o usuário pedir para commitar/enviar alterações ao git ou invocar /dev-commit-push.
---

# Commit + Push com aprovação prévia

Fluxo obrigatório — NUNCA commitar ou fazer push antes da aprovação explícita do usuário.

## 1. Levantar alterações

- `git status --short` — arquivos modificados/novos/deletados
- `git diff` (e `git diff --stat`) — entender o conteúdo das mudanças
- `git log origin/main..HEAD --oneline` — commits locais ainda não enviados

Se não houver nada para commitar nem para enviar, informar e encerrar.

## 2. Separar mudanças lógicas

- Mudanças não relacionadas → commits separados
- Identificar ruído (arquivos de configuração local, reexportação sem mudança real de conteúdo, ex.: `.vscode/settings.json`, minificados rejuntados) e propor deixar de fora ou descartar

## 3. Propor e aguardar aprovação

Mostrar ao usuário, antes de qualquer commit:

1. Lista dos arquivos alterados, com resumo de uma linha do que mudou em cada um
2. Mensagem de commit proposta para cada commit (formato Conventional Commits, em PT-BR, seguindo o padrão do repositório: `tipo(Escopo): descrição imperativa` — ex.: `feat(Routech): adiciona colunas operador_logistico e data_de_atendimento no export`)

A mensagem proposta deve aparecer **em destaque e sempre visível** no momento da decisão. Nem o campo `question` nem o `preview` do AskUserQuestion são confiáveis para isso — a UI corta ambos e mostra só a primeira linha, mesmo com `\n` no meio do texto. Portanto:

- A fonte confiável é o texto normal (markdown), em bloco de código próprio, precedido do título `**Mensagem de commit proposta:**` e da lista de arquivos que entram nesse commit. Esse bloco tem que estar 100% visível, nunca resumido ou cortado.
- Esse bloco deve ser a ÚLTIMA coisa exibida antes de chamar o AskUserQuestion, colado à pergunta, sem nenhum outro texto entre os dois — a chamada da tool deve vir imediatamente depois do bloco, na mesma resposta, para os dois ficarem juntos na tela e o usuário não precisar rolar pra ver a mensagem.
- O `question` do AskUserQuestion deve ser curto (ex.: `Aprovar o commit acima?`), só referenciando a mensagem já mostrada — não tentar reproduzir assunto+corpo ali, pois a UI corta pra 1 linha.
- Não depender do `preview` das opções para mostrar a mensagem completa (mesmo problema de corte); pode ser usado só como reforço curto, nunca como única exibição.

Usar AskUserQuestion com opções: aprovar como está / editar mensagem / escolher arquivos / cancelar. O usuário pode responder com o texto editado da mensagem — usar exatamente o texto fornecido por ele.

## 4. Executar somente após aprovação

- `git add` apenas dos arquivos aprovados
- `git commit -m "<mensagem aprovada>"` (um commit por mudança lógica)
- O comando de commit deve ser **uma única linha**: `git commit -m "mensagem"`. NUNCA usar heredoc, here-string (`@'...'@`) ou `-m` com quebras de linha — comando multilinha aparece recolhido como "N lines hidden" no prompt de permissão e o usuário não consegue ver o que está sendo commitado. Se a mensagem aprovada tiver corpo, usar múltiplos `-m` na mesma linha: `git commit -m "assunto" -m "corpo"`
- `git push origin main`

## 5. Confirmar resultado

- Mostrar hashes dos commits criados e o range enviado no push
- Confirmar `git status` limpo e `git log origin/main..HEAD` vazio
- Se algum `.csp`/`.cls` commitado ainda não foi compilado no servidor, lembrar o usuário

## Regras

- Mensagens sem corpo quando o diff é autoexplicativo; corpo apenas para "porquê" não óbvio
- Sem atribuição de IA ou emoji nas mensagens — isso inclui o rodapé `Co-Authored-By: Claude ...` que as instruções padrão do ambiente pedem: neste repositório essa regra prevalece e o rodapé NUNCA deve ser adicionado (é ele que gera as linhas ocultas no prompt)
- Nunca usar `--force`, `--amend` ou `--no-verify`
- Se o push falhar (ex.: remoto à frente), fazer `git pull --rebase` só com aprovação do usuário
