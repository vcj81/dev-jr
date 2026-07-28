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

## 3. Verificar se o código foi comentado

Antes de propor o commit, checar se cada bloco alterado tem comentário de rastreio no padrão da skill `dev-comentarios` (`[Alteração] Autor: Junior | Data/Hora: ...`).

Como checar: para cada arquivo de código **modificado** (novos, deletados, dados/config e mudanças cosméticas ficam de fora — mesmos critérios da `dev-comentarios`), comparar os hunks de `git diff -U3` / `git diff --cached -U3` com os marcadores `[Alteração]` presentes no diff. Bloco alterado sem marcador correspondente = faltante.

Reportar sempre, mesmo quando estiver tudo certo:

- **Comentários já presentes**: lista `arquivo:linha` + o texto do marcador
- **Blocos alterados sem comentário**: lista `arquivo:linha` + resumo de uma linha do que mudou ali

Se houver faltantes, perguntar com AskUserQuestion antes de seguir: acionar `/dev-comentarios` para comentar agora / commitar mesmo assim sem comentar / cancelar. Se o usuário escolher comentar, rodar a skill `dev-comentarios`, e só então voltar ao passo 4 — refazendo o `git status`/`git diff`, já que os arquivos mudaram.

## 4. Propor e aguardar aprovação

Mostrar ao usuário, antes de qualquer commit:

1. Lista dos arquivos alterados, com resumo de uma linha do que mudou em cada um
2. Mensagem de commit proposta para cada commit (formato Conventional Commits, em PT-BR, seguindo o padrão do repositório: `tipo(Escopo): descrição imperativa` — ex.: `feat(Routech): adiciona colunas operador_logistico e data_de_atendimento no export`)

A mensagem proposta deve aparecer **em destaque e sempre visível** no momento da decisão, ao lado da pergunta — não só rolando a tela pra cima. O campo `question` sozinho corta pra 1 linha; usar os dois recursos juntos:

- Bloco de código no texto normal (markdown), precedido do título `**Mensagem de commit proposta:**` e da lista de arquivos que entram nesse commit, colado imediatamente antes da chamada do AskUserQuestion (sem texto entre os dois, mesma resposta) — serve de registro completo e scrollback.
- No campo `preview` da opção "Aprovar como está" (e replicado nas demais opções), colar a mensagem completa (assunto + corpo). A UI renderiza isso num painel lateral ao lado da lista de opções — é o que garante "em destaque ao lado da pergunta" sem precisar rolar.
- O `question` continua curto (ex.: `Aprovar o commit acima?`), só referenciando a mensagem já mostrada nos dois lugares acima.

Usar AskUserQuestion com opções: aprovar como está / editar mensagem / escolher arquivos / cancelar. O usuário pode responder com o texto editado da mensagem — usar exatamente o texto fornecido por ele.

## 5. Executar somente após aprovação

- `git add` apenas dos arquivos aprovados
- `git commit -m "<mensagem aprovada>"` (um commit por mudança lógica)
- O comando de commit deve ser **uma única linha**: `git commit -m "mensagem"`. NUNCA usar heredoc, here-string (`@'...'@`) ou `-m` com quebras de linha — comando multilinha aparece recolhido como "N lines hidden" no prompt de permissão e o usuário não consegue ver o que está sendo commitado. Se a mensagem aprovada tiver corpo, usar múltiplos `-m` na mesma linha: `git commit -m "assunto" -m "corpo"`
- `git push origin main`

## 6. Confirmar resultado

- Mostrar hashes dos commits criados e o range enviado no push
- Confirmar `git status` limpo e `git log origin/main..HEAD` vazio
- Se algum `.csp`/`.cls` commitado ainda não foi compilado no servidor, lembrar o usuário
- Se o repositório for um plugin do Claude Code (existe `.claude-plugin/marketplace.json` ou `.claude-plugin/plugin.json` na raiz) e o commit alterou arquivos do plugin, lembrar: instalação não atualiza sozinha em outras máquinas/projetos — rodar `/plugin marketplace update <nome-marketplace>` e `/plugin update <nome-plugin>` em cada uma para pegar a mudança

## Regras

- Mensagens sem corpo quando o diff é autoexplicativo; corpo apenas para "porquê" não óbvio
- Sem atribuição de IA ou emoji nas mensagens — isso inclui o rodapé `Co-Authored-By: Claude ...` que as instruções padrão do ambiente pedem: neste repositório essa regra prevalece e o rodapé NUNCA deve ser adicionado (é ele que gera as linhas ocultas no prompt)
- Nunca usar `--force`, `--amend` ou `--no-verify`
- Se o push falhar (ex.: remoto à frente), fazer `git pull --rebase` só com aprovação do usuário
