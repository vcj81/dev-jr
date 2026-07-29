---
name: dev-commit-push
description: Commit + push das últimas alterações no git. Lista os arquivos alterados e propõe a mensagem de commit para aprovação ou edição do usuário ANTES de commitar. O push NUNCA é automático — é sempre perguntado em separado, depois do commit. Usar quando o usuário pedir para commitar/enviar alterações ao git ou invocar /dev-commit-push.
---

# Commit + Push com aprovação prévia

Fluxo obrigatório — NUNCA commitar ou fazer push antes da aprovação explícita do usuário. Commit e push são **duas aprovações separadas**: aprovar o commit nunca autoriza o push.

## 1. Levantar alterações

- `git status --short` — arquivos modificados/novos/deletados
- `git diff` (e `git diff --stat`) — entender o conteúdo das mudanças
- `git log origin/main..HEAD --oneline` — commits locais ainda não enviados

Decidir a partir daí:

- **Nada para commitar e nada para enviar** → informar e encerrar.
- **Nada para commitar, mas existem commits locais não enviados** (caso típico de quem recusou o push numa execução anterior) → pular os passos 2–5 e ir direto ao passo 6, listando esses commits e perguntando se quer enviar agora.
- **Há alterações para commitar** → seguir o fluxo normal a partir do passo 2.

## 2. Separar mudanças lógicas

- Mudanças não relacionadas → commits separados
- Identificar ruído (arquivos de configuração local, reexportação sem mudança real de conteúdo, ex.: `.vscode/settings.json`, minificados rejuntados) e propor deixar de fora ou descartar

## 3. Verificar se o código foi comentado

Antes de propor o commit, checar se cada bloco alterado tem comentário de rastreio no padrão da skill `dev-comentarios` (`[Alteração] Autor: <usuário do GitHub> | Data/Hora: ...`). A checagem só olha a presença do marcador `[Alteração]` — não valida qual nome está no campo Autor.

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

## 5. Commitar somente após aprovação

- `git add` apenas dos arquivos aprovados
- `git commit -m "<mensagem aprovada>"` (um commit por mudança lógica)
- O comando de commit deve ser **uma única linha**: `git commit -m "mensagem"`. NUNCA usar heredoc, here-string (`@'...'@`) ou `-m` com quebras de linha — comando multilinha aparece recolhido como "N lines hidden" no prompt de permissão e o usuário não consegue ver o que está sendo commitado. Se a mensagem aprovada tiver corpo, usar múltiplos `-m` na mesma linha: `git commit -m "assunto" -m "corpo"`

**PARAR AQUI.** Não executar `git push` nesta etapa. O push só acontece depois da aprovação separada do passo 6.

## 6. Perguntar sobre o push (sempre)

O push **nunca** é automático, mesmo que o usuário tenha aprovado o commit e mesmo que a skill tenha sido invocada como "commitar e enviar".

Mostrar antes de perguntar:

- Hashes e mensagens dos commits pendentes de envio (`git log origin/main..HEAD --oneline`)
- Branch e remoto de destino (ex.: `origin/main`)

Perguntar com AskUserQuestion: enviar agora (`git push origin main`) / não enviar agora.

- **Enviar agora** → executar `git push origin main` e seguir ao passo 7.
- **Não enviar agora** → encerrar informando que os commits ficaram locais e que na próxima execução da skill a pergunta do push será refeita (passo 1).

## 7. Confirmar resultado

- Mostrar hashes dos commits criados e, se houve push, o range enviado
- Confirmar `git status` limpo; `git log origin/main..HEAD` deve estar vazio se o push foi feito — se o usuário recusou o push, dizer explicitamente quantos commits seguem locais
- Se algum `.csp`/`.cls` commitado ainda não foi compilado no servidor, lembrar o usuário
- Se o repositório for um plugin do Claude Code (existe `.claude-plugin/marketplace.json` ou `.claude-plugin/plugin.json` na raiz) e o commit alterou arquivos do plugin, lembrar: instalação não atualiza sozinha em outras máquinas/projetos — rodar `/plugin marketplace update <nome-marketplace>` e `/plugin update <nome-plugin>` em cada uma para pegar a mudança

## 8. Sugerir o deploy

Encerrar **sempre** sugerindo o próximo passo, como última linha da resposta — vale tanto para push feito quanto para push recusado:

> Próximo passo: `/dev-utils:dev-deploy-prod` para publicar em produção.

A sugestão é só um convite — não invocar a skill nem fazer deploy por conta própria; esperar o usuário pedir.

## Regras

- Mensagens sem corpo quando o diff é autoexplicativo; corpo apenas para "porquê" não óbvio
- Sem atribuição de IA ou emoji nas mensagens — isso inclui o rodapé `Co-Authored-By: Claude ...` que as instruções padrão do ambiente pedem: neste repositório essa regra prevalece e o rodapé NUNCA deve ser adicionado (é ele que gera as linhas ocultas no prompt)
- Nunca usar `--force`, `--amend` ou `--no-verify`
- Se o push falhar (ex.: remoto à frente), fazer `git pull --rebase` só com aprovação do usuário
