---
name: dev-commit-push
description: Commit + push das últimas alterações no git. Lista os arquivos alterados e propõe a mensagem de commit para aprovação ou edição do usuário ANTES de commitar. O push NUNCA é automático — é sempre perguntado em separado, depois do commit. Antes de commitar, garante que todo bloco de código alterado tenha comentário de rastreio (Autor/Data/Hora) e que todo arquivo novo tenha documentação didática — perguntando se ainda não foi feito no momento da alteração. Usar quando o usuário pedir para commitar/enviar alterações ao git ou invocar /dev-commit-push.
---

# Commit + Push com aprovação prévia

Fluxo obrigatório — NUNCA commitar ou fazer push antes da aprovação explícita do usuário. Commit e push são **duas aprovações separadas**: aprovar o commit nunca autoriza o push.

## 0. Escolher modo de trabalho (sempre perguntar primeiro)

Antes de levantar alterações, perguntar com AskUserQuestion o modo desta rodada:

- **Commitar direto na branch atual/MAIN** — fluxo padrão de sempre, segue normal pros passos 1–8, push final em `origin/main` (ou branch atual).
- **Salvar na branch DEV** — pra ir acumulando pequenas alterações antes de validar. Se a branch `DEV` não existir localmente, criar com `git checkout -b DEV` a partir do estado atual; se já existir, `git checkout DEV` (avisar se houver mudanças não commitadas impedindo o checkout). Commit segue passos 1–5 normalmente. No passo 6, o push é pra `origin/DEV`, não `origin/main`.
- **Promover DEV → MAIN** — quando as alterações acumuladas em DEV já foram validadas. Confirmar que a branch `DEV` existe e tem commits à frente de `main` (`git log main..DEV --oneline`), mostrar a lista pro usuário, perguntar aprovação, e só então: `git checkout main`, `git merge DEV` (sem `--no-ff` a menos que o usuário peça), e seguir pro passo 6 (push de main) usando o fluxo normal. Não apagar a branch DEV automaticamente — só perguntar se quer apagar depois do merge confirmado.

Guardar o modo escolhido e a branch de trabalho resultante — os passos seguintes usam essa branch em vez de assumir `main` fixo.

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

## 3. Garantir comentários no código antes do commit

Regra: nada de bloco de código alterado (ou arquivo novo) sem comentário em PT-BR. Esta etapa cobre as duas situações — se o Claude já comentou no momento da alteração, aqui é só conferência; se não comentou, pergunta e resolve antes de seguir.

### 3.1. Arquivo novo → documentação didática

Todo arquivo novo criado pelo Claude deve estar autoexplicativo, em dois níveis:

1. **Explicação geral no topo** (2–4 linhas): o que o arquivo faz e como se encaixa no sistema, na sintaxe de comentário/docstring da própria linguagem.
2. **Comentários inline**: ao longo do código, explicando os trechos relevantes — o que cada bloco/função faz e, quando houver, a regra de negócio por trás.

Regras:

- Comentar para ensinar, não para repetir o óbvio: explicar o porquê e o papel do trecho, não traduzir linha a linha.
- Arquivo novo **não** leva marcador `[Alteração]` — o arquivo inteiro é novo, não há bloco alterado.

Há um hook `PreToolUse` (`scripts/check-novo-arquivo.ps1`) que bloqueia o `Write` de arquivo novo em linguagem mapeada (py, js/ts, java, c/cpp/cs, go, php, rb, ps1, sh, css, html, sql, rs, kt, swift) quando o conteúdo tem mais de 3 linhas não vazias e menos de 2 linhas de comentário — rede de segurança grosseira, só verifica presença mínima, não qualidade.

### 3.2. Arquivo alterado → rastreio da alteração

**Levantar os blocos alterados:**

- `git diff -U3` e `git diff --cached -U3` — hunks alterados (não staged e staged)

Considerar apenas arquivos de **código** já existentes (modificados). Ficam de fora:

- Arquivos novos → regra 3.1
- Arquivos deletados
- Dados/config/gerados: `.json`, `.md`, `.yml`, `.yaml`, `.lock`, `.csv`, `.env*`, minificados, `dist/`, `build/`, `node_modules/`
- Mudança puramente cosmética (só indentação/espaço em branco, sem mudança de comportamento)

**Pegar o autor e a data/hora reais** — sempre do sistema, nunca chutar nem escrever nome fixo.

Autor — usuário do GitHub, resolvido nesta ordem (para no primeiro que retornar valor não vazio):

```powershell
gh api user --jq ".login"   # 1º: login real do GitHub (se o gh CLI estiver instalado e autenticado)
git config user.name        # 2º: fallback
```

Se os dois falharem ou vierem vazios, perguntar o usuário do GitHub antes de inserir qualquer comentário — não inventar e não usar "Claude".

Data/hora:

```powershell
Get-Date -Format "dd/MM/yyyy HH:mm"
```

Resolver autor e data/hora **uma vez por rodada** e usar o mesmo par em todos os blocos daquela rodada.

**Inserir o comentário em cada bloco alterado**, na sintaxe de comentário da linguagem do arquivo, imediatamente **acima** do bloco alterado e na mesma indentação dele:

```
// [Alteração] Autor: <usuário do GitHub> | Data/Hora: <dd/MM/yyyy HH:mm>
// <o que mudou e por quê, 1–2 linhas>
```

Exemplo já resolvido (autor vindo da resolução acima, não digitado à mão):

```
// [Alteração] Autor: ciaca-jr | Data/Hora: 28/07/2026 14:32
// compara tipo também, senão "0" passava como válido
```

Regras de posicionamento:

- Um comentário por bloco lógico alterado, não por linha. Linhas contíguas que mudaram pelo mesmo motivo = um comentário só.
- Se o bloco alterado é o corpo inteiro de uma função/método, o comentário vai acima da assinatura.
- Se o mesmo arquivo tem alterações independentes em pontos distantes, cada ponto ganha seu comentário.
- Nunca reescrever, reindentar ou reformatar o código ao inserir o comentário — só adicionar linhas.
- Se já existir um ou mais `[Alteração]` do mesmo bloco de rodadas anteriores, **apagar os antigos** e deixar só o comentário desta rodada. O bloco mantém apenas o último registro — o histórico completo fica no git.
- Se o mesmo bloco já foi marcado nesta mesma rodada, não duplicar.

### 3.3. Checar antes de propor o commit

Comparar os hunks de `git diff -U3` / `git diff --cached -U3` com os marcadores `[Alteração]` presentes no diff (a checagem só olha a presença do marcador — não valida qual nome está no campo Autor). Bloco alterado sem marcador correspondente = faltante. Arquivo novo sem explicação no topo/comentários inline = faltante.

Reportar sempre, mesmo quando estiver tudo certo:

- **Comentários já presentes**: lista `arquivo:linha` + o texto do marcador
- **Blocos alterados/arquivos novos sem comentário**: lista `arquivo:linha` + resumo de uma linha do que mudou ali

Se houver faltantes, perguntar com AskUserQuestion antes de seguir: comentar agora (aplicar 3.1/3.2 nos itens faltantes) / commitar mesmo assim sem comentar / cancelar. Se o usuário escolher comentar, aplicar as regras acima e só então voltar ao passo 4 — refazendo o `git status`/`git diff`, já que os arquivos mudaram.

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

A branch de destino do push é a branch de trabalho definida no passo 0 (`main`, `DEV`, ou `main` no caso de promoção DEV → MAIN).

Mostrar antes de perguntar:

- Hashes e mensagens dos commits pendentes de envio (`git log origin/<branch>..HEAD --oneline`)
- Branch e remoto de destino (ex.: `origin/main` ou `origin/DEV`)

Perguntar com AskUserQuestion: enviar agora (`git push origin <branch>`) / não enviar agora.

- **Enviar agora** → executar `git push origin <branch>` (se a branch `DEV` ainda não existir no remoto, usar `git push -u origin DEV`) e seguir ao passo 7.
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

## Sintaxe de comentário por linguagem

| Linguagem | Comentário |
|---|---|
| JS/TS/Java/C/C#/Go/Rust/Kotlin/Swift | `//` |
| CSS/SCSS/LESS | `/* */` |
| Python/Ruby/Shell/PowerShell/YAML | `#` |
| SQL | `--` |
| HTML/XML/Markdown | `<!-- -->` |
| ObjectScript (IRIS/Caché `.cls`/`.mac`/`.inc`) | `//` no corpo do método; `///` acima da definição de classe/método |
| CSP | `<!-- -->` no HTML, `//` dentro de `<script>`/`<script language="cache">` |

## Regras

- Comentários de rastreio em **PT-BR**; termos técnicos consagrados (test, id, status) podem ficar em inglês.
- Autor é **sempre** o usuário do GitHub resolvido em 3.2 — nunca nome fixo no texto da skill, nunca "Claude", nunca atribuição de IA.
- O comentário explica o **porquê**, não traduz a linha (`// troca == por ===` é ruim; `// compara tipo também, senão "0" passava como válido` é bom).
- Mensagens de commit sem corpo quando o diff é autoexplicativo; corpo apenas para "porquê" não óbvio
- Sem atribuição de IA ou emoji nas mensagens — isso inclui o rodapé `Co-Authored-By: Claude ...` que as instruções padrão do ambiente pedem: neste repositório essa regra prevalece e o rodapé NUNCA deve ser adicionado (é ele que gera as linhas ocultas no prompt)
- Nunca usar `--force`, `--amend` ou `--no-verify`
- Se o push falhar (ex.: remoto à frente), fazer `git pull --rebase` só com aprovação do usuário
