# dev-utils

Plugin do Claude Code com alertas e skills de fluxo de trabalho.

## Hooks (alertas)

- **Notification** — som + toast do Windows quando o Claude precisa da sua interação (pedido de permissão ou pergunta)
- **Stop** — som + toast quando o Claude termina a tarefa e fica aguardando
- **SessionStart** — avisa se há atualização pendente do plugin e carrega os **Padrões de Projeto** (`instrucoes/padroes-projeto.md`) como instruções obrigatórias da sessão

## Padrões de Projeto (instruções automáticas)

Não é mais uma skill/comando: o conteúdo de `instrucoes/padroes-projeto.md` é injetado em toda sessão de todo projeto que usa o plugin e deve ser seguido sempre — toda interface web deve nascer preparada para instalação como PWA (manifest, service worker, HTTPS), e todo arquivo deve estar em UTF-8 com charset explícito nas páginas (acentuação igual em homologação e produção), com revisão de projetos existentes e sugestões contínuas de ajuste. Para mudar os padrões, edite esse arquivo.

## Skills

- **dev-commit-push** — commit + push com aprovação prévia obrigatória da mensagem e dos arquivos; antes de propor o commit, confere o comentário de cada linha/bloco alterado — `[Alteração]` com `Autor: <usuário do GitHub>` (resolvido via `gh api user`, com fallback `git config user.name`), Data/Hora e o que mudou, substituindo comentários de alterações anteriores daquele trecho; nada de cabeçalho ou texto explicativo no começo de páginas, classes e arquivos, nem em arquivo novo — e checa a acentuação/encoding dos arquivos do commit
- **dev-deploy-prod** — deploy de classes/páginas num servidor IRIS/Caché de produção via API Atelier, com aprovação prévia da lista de itens, backup XML automático (rollback) e retenção dos 3 mais recentes. **Verificação de acentuação** em todo deploy (`acentuacao.py`): bloqueia arquivo fora de UTF-8 ou com acento corrompido, compara com a versão atual de produção, testa a gravação no servidor com uma sonda temporária antes de enviar, confere cada item depois de gravado (divergência cancela a compilação) e confere as páginas CSP compiladas; `--verificar` roda só a parte que não grava nada. Config/segredos/backups ficam sempre no repositório alvo (`.claude/dev-deploy-prod/`), nunca no plugin — espera repo com estrutura `src/cls`, `src/mac`, `src/inc`, `src/oth`

## Instalação em uma máquina nova

```
claude plugin marketplace add vcj81/dev-jr
claude plugin install dev-utils@dev-jr
```

Ou, dentro de uma sessão interativa do Claude Code:

```
/plugin marketplace add vcj81/dev-jr
/plugin install dev-utils@dev-jr
```

Pronto — vale para todos os projetos da máquina.

## Estrutura

```
.claude-plugin/marketplace.json      # registro do marketplace (dev-jr)
plugins/dev-utils/
  .claude-plugin/plugin.json         # manifesto do plugin
  hooks/hooks.json                   # hooks SessionStart, Notification e Stop
  instrucoes/padroes-projeto.md      # padrões de projeto (PWA obrigatório), injetados via SessionStart
  scripts/notify.ps1                 # som + toast do Windows
  scripts/load-padroes-projeto.ps1   # injeta instrucoes/padroes-projeto.md no contexto da sessão
  skills/dev-commit-push/SKILL.md    # commit com aprovação prévia + comentário só nas linhas/blocos alterados
  skills/dev-deploy-prod/SKILL.md    # deploy em produção IRIS/Caché (API Atelier)
  skills/dev-deploy-prod/deploy.py   # script do deploy (config/backups ficam no repo alvo)
  skills/dev-deploy-prod/acentuacao.py # verificação/correção de acentuação e encoding (usado no deploy e no commit)
  skills/dev-deploy-prod/.env.example
```

## Requisitos

- Windows 10/11 (usa PowerShell e notificações toast)
- Verifique se o "Assistente de Foco" (Não Perturbe) do Windows não está silenciando as notificações
