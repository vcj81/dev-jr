# claude-alertas

Plugin do Claude Code com alertas sonoros e notificações do Windows:

- **Notification** — dispara quando o Claude precisa da sua interação (pedido de permissão ou pergunta)
- **Stop** — dispara quando o Claude termina a tarefa e fica aguardando

## Instalação em uma máquina nova

```
claude marketplace add vcj81/claude-alertas
claude plugin install claude-alertas@vcj81-plugins
```

Pronto — vale para todos os projetos da máquina.

## Estrutura

```
.claude-plugin/marketplace.json      # registro do marketplace
plugins/claude-alertas/
  .claude-plugin/plugin.json         # manifesto do plugin
  hooks/hooks.json                   # hooks Notification e Stop
  scripts/notify.ps1                 # som + toast do Windows
```

## Requisitos

- Windows 10/11 (usa PowerShell e notificações toast)
- Verifique se o "Assistente de Foco" (Não Perturbe) do Windows não está silenciando as notificações
