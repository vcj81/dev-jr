# claude-ferramentas

Plugin do Claude Code com alertas e skills de fluxo de trabalho.

## Hooks (alertas)

- **Notification** — som + toast do Windows quando o Claude precisa da sua interação (pedido de permissão ou pergunta)
- **Stop** — som + toast quando o Claude termina a tarefa e fica aguardando

## Skills

- **dev-commit-push** — commit + push com aprovação prévia obrigatória da mensagem e dos arquivos
- **dev-novo-arquivo** — documentação didática em todo arquivo novo: breve explicação no topo + comentários inline, em PT-BR (o usuário está aprendendo a linguagem)
- **dev-padroes-projeto** — padrões de arquitetura para todo projeto: toda interface web deve nascer preparada para instalação como PWA (manifest, service worker, HTTPS)
- **dev-deploy-prod** — deploy de classes/páginas num servidor IRIS/Caché de produção via API Atelier, com aprovação prévia da lista de itens, backup XML automático (rollback) e retenção dos 3 mais recentes. Config/segredos/backups ficam sempre no repositório alvo (`.claude/dev-deploy-prod/`), nunca no plugin — espera repo com estrutura `src/cls`, `src/mac`, `src/inc`, `src/oth`

## Instalação em uma máquina nova

```
claude plugin marketplace add vcj81/claude-ferramentas
claude plugin install claude-ferramentas@vcj81-plugins
```

Ou, dentro de uma sessão interativa do Claude Code:

```
/plugin marketplace add vcj81/claude-ferramentas
/plugin install claude-ferramentas@vcj81-plugins
```

Pronto — vale para todos os projetos da máquina.

## Estrutura

```
.claude-plugin/marketplace.json      # registro do marketplace (vcj81-plugins)
plugins/claude-ferramentas/
  .claude-plugin/plugin.json         # manifesto do plugin
  hooks/hooks.json                   # hooks Notification e Stop
  scripts/notify.ps1                 # som + toast do Windows
  skills/dev-commit-push/SKILL.md    # commit com aprovação prévia
  skills/dev-novo-arquivo/SKILL.md   # padrões de criação de arquivos
  skills/dev-padroes-projeto/SKILL.md # padrões de projeto (PWA obrigatório)
  skills/dev-deploy-prod/SKILL.md    # deploy em produção IRIS/Caché (API Atelier)
  skills/dev-deploy-prod/deploy.py   # script do deploy (config/backups ficam no repo alvo)
  skills/dev-deploy-prod/.env.example
```

## Requisitos

- Windows 10/11 (usa PowerShell e notificações toast)
- Verifique se o "Assistente de Foco" (Não Perturbe) do Windows não está silenciando as notificações
