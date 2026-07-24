---
name: dev-deploy-prod
description: Deploy de classes (.cls) e páginas (.csp) num servidor IRIS/Caché de PRODUÇÃO via API Atelier, com aprovação prévia da lista de itens. Usar quando o usuário pedir para fazer deploy, publicar, subir ou enviar alterações para produção, ou invocar /dev-deploy-prod. Espera um repo com estrutura `src/cls`, `src/mac`, `src/inc`, `src/oth` (padrão de export ObjectScript via VS Code).
---

# Deploy em Produção (servidor IRIS/Caché)

Envia itens ao servidor de produção do repositório atual via API Atelier e compila. Fluxo com aprovação obrigatória — NUNCA enviar nada antes do usuário aprovar a lista.

Este skill roda de um plugin compartilhado entre repositórios — `deploy.py` fica instalado uma vez só, mas config/segredos/backups são sempre locais a cada repositório onde é usado (nunca dentro do plugin). Todo comando abaixo deve ser executado com o diretório de trabalho na **raiz do repositório alvo** (onde fica a pasta `src/`).

## Configuração

Servidor/credenciais em `<raiz do repo>/.claude/dev-deploy-prod/.env` (NÃO versionado). Se o arquivo não existir:
1. Localizar `.env.example` ao lado do `deploy.py` deste skill (caminho mostrado em "Base directory for this skill" no cabeçalho da invocação)
2. Criar a pasta `<raiz do repo>/.claude/dev-deploy-prod/` e copiar o `.env.example` pra lá como `.env`
3. Pedir ao usuário os dados (host:porta, usuário, senha, namespace) — nunca aceitar a senha digitada direto no chat; pedir pra editar o arquivo fora da conversa (ex.: no editor) e confirmar quando salvar

Adicionar ao `.gitignore` do repo alvo, se ainda não tiver:
```
.claude/dev-deploy-prod/.env
.claude/dev-deploy-prod/backups/
```

## 1. Levantar itens

Determinar o que deployar, nesta ordem de preferência:

- Usuário informou commits/range (ex.: `HEAD~2..HEAD`): `git diff --name-only <range>` filtrando `src/`
- Usuário informou arquivos/itens explícitos: usar direto
- Sem argumento: propor o diff `origin/main..HEAD` + working tree; se vazio, propor o último commit (`HEAD~1..HEAD`)

Mapeamento arquivo → item (o script `deploy.py` faz isso sozinho quando recebe `--files`):
- `src/cls/IBTech/Ca/X.cls` → `IBTech.Ca.X.cls` (barras viram pontos)
- `src/oth/ibtech/icfpages/.../pagina.csp` → `/ibtech/icfpages/.../pagina.csp` (mantém barras, adiciona `/` inicial)
- Estáticos (js/css/imagens) e arquivos fora de `src/` não entram — avisar se aparecerem

## 2. Aprovar

Mostrar ao usuário a lista de itens e o servidor de destino. Usar AskUserQuestion: aprovar / editar lista / cancelar. É PRODUÇÃO — sem aprovação explícita, não prosseguir.

## 3. Executar

Usar o caminho absoluto de `deploy.py` mostrado em "Base directory for this skill", com o diretório de trabalho na raiz do repo alvo:

```bash
python "<base directory>/deploy.py" --files "src/cls/A/B.cls,src/oth/ibtech/icfpages/x/y.csp"
```

Ou com itens já mapeados:

```bash
python "<base directory>/deploy.py" --items "IBTech.A.B.cls,/ibtech/icfpages/x/y.csp"
```

O script: valida conexão, **gera backup XML da versão atual de produção** dos itens (rollback) em `<raiz do repo>/.claude/dev-deploy-prod/backups/AAAAMMDD_HHMMSS_<PacoteRaiz>.xml` (ex.: `20260710_101437_IBTech.Ca.CPPA.xml`; pacote raiz comum das classes, ou pasta comum dos CSP se só houver página), envia cada documento (PUT com `ignoreConflict=1`), compila tudo (`flags=cuk`) e aborta no primeiro erro, mostrando a saída do compilador.

Sobre o backup:
- Itens que ainda não existem em produção são apenas avisados (item novo, sem versão anterior)
- `--no-backup` pula a etapa (usar só se o usuário pedir)
- Retenção: mantém só os 3 backups mais recentes na pasta — a cada novo backup, os mais antigos são apagados automaticamente
- Rollback: importar o XML via Studio ou `$system.OBJ.Load("caminho.xml","cuk")` no servidor
- Backups ficam só no repo alvo, fora do plugin — cada repositório mantém os seus

## 4. Pós-deploy

- Se alguma classe `*.Utils` com `buildMenu` estiver no deploy, perguntar se deve regravar o menu e rodar:
  ```bash
  python "<base directory>/deploy.py" --build-menu IBTech.Ca.CCQ.Utils
  ```
  (cria classe temporária `Temp.ClaudeRunBuildMenu` com SqlProc, executa via SQL e remove a classe)
- Consultas SQL de verificação: `deploy.py --query "SELECT ..."` (somente leitura por padrão; UPDATEs exigem aprovação do usuário no chat)

## 5. Confirmar resultado

Reportar: itens enviados, saída de compilação ("Compilation finished successfully"), e o que foi executado no pós-deploy. Lembrar o usuário de testar a tela em produção.

## Regras

- Só deployar o que está compilando sem erro na homologação (perguntar se não souber)
- Configurações de DADOS (registros em tabelas, ex.: `tipoConsulta` de campos do boletim) não vão via deploy — tratar via `--query` com aprovação ou pela tela do sistema
- Erro de compilação em produção: reportar imediatamente com a mensagem exata; não tentar "consertar" direto em produção
- API observações técnicas: nome de CSP na URL usa barras LITERAIS (não %2F); classes usam nome com pontos
