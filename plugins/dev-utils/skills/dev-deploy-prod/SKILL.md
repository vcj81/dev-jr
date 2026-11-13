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

## 1.1. Verificar acentuação (sempre, antes da aprovação)

Problema que evita: labels/textos acentuados certos na homologação e "desconfigurados" em produção. Rodar com os mesmos itens do passo 1 — **não grava nada** em produção (só leitura):

```bash
python "<base directory>/deploy.py" --verificar --files "src/cls/A/B.cls,src/oth/ibtech/icfpages/x/y.csp"
```

O que confere (detalhes em `acentuacao.py`):

- **Arquivos locais** — ERRO (bloqueia): arquivo fora de UTF-8 (salvo como Windows-1252/Latin-1), texto corrompido (`ç` virou dois caracteres, ex.: `Ã` + `§`), acento já perdido (`�` no lugar da letra). AVISO: possível acento que virou `?`, caractere fora do Latin-1 (aspas curvas, travessão, reticências — servidor Caché 8-bit troca por `?`), BOM, página CSP/classe `%CSP.Page` sem charset explícito, `<csp:content>` e `<meta>` com charsets diferentes. <!-- acentuacao: ignorar -->
- **Servidor** — se é Unicode ou 8-bit (pela versão da API Atelier).
- **Versão atual de produção** — INFO se produção já está hoje com acento quebrado (o deploy corrige); AVISO se uma palavra acentuada em produção chegaria sem acento (`Usuário` → `Usuario`).

Se houver **ERRO**: não seguir para a aprovação. Mostrar os problemas e:

1. Para o que é corrigível (Windows-1252, texto corrompido, BOM), mostrar a prévia: `python "<base directory>/acentuacao.py" --corrigir <arquivos>` (não grava).
2. Perguntar com AskUserQuestion: aplicar a correção / corrigir manualmente / cancelar. Só com aprovação, rodar com `--corrigir --aplicar` e repetir o `--verificar`.
3. Acento já perdido (`�`, `?`) não tem correção automática: redigitar copiando o texto da homologação. <!-- acentuacao: ignorar -->
4. Arquivo corrigido precisa ser commitado (`/dev-utils:dev-commit-push`) — lembrar o usuário. Se o arquivo estava corrompido no repositório, a homologação provavelmente também está: perguntar se quer reenviar para lá.

Falso positivo: o usuário pode marcar a linha com um comentário contendo `acentuacao: ignorar`. Seguir com ERRO só com aprovação explícita, usando `--ignorar-acentuacao` no passo 3.

**AVISOs** não bloqueiam, mas entram no resumo do passo 2 para o usuário decidir.

## 2. Aprovar

Mostrar ao usuário a lista de itens, o servidor de destino e o **resultado da verificação de acentuação** (ok / quantos avisos, com um resumo de cada um). Usar AskUserQuestion: aprovar / editar lista / cancelar. É PRODUÇÃO — sem aprovação explícita, não prosseguir.

## 3. Executar

Usar o caminho absoluto de `deploy.py` mostrado em "Base directory for this skill", com o diretório de trabalho na raiz do repo alvo:

```bash
python "<base directory>/deploy.py" --files "src/cls/A/B.cls,src/oth/ibtech/icfpages/x/y.csp"
```

Ou com itens já mapeados:

```bash
python "<base directory>/deploy.py" --items "IBTech.A.B.cls,/ibtech/icfpages/x/y.csp"
```

O script repete a verificação do passo 1.1 (bloqueia se surgir ERRO) e acrescenta três checagens no servidor:

- **Sonda, antes de tocar nos itens reais**: grava um documento temporário com todos os caracteres acentuados que serão enviados, lê de volta e apaga — classe `Temp.ClaudeSondaEnc` (se houver classe/rotina no deploy) e página `zzClaudeSondaEnc.csp` na pasta da primeira CSP (se houver página). Se o servidor devolver algum caractere trocado, o deploy é bloqueado antes do backup e do envio, mostrando cada troca (ex.: `'“' U+201C → '?'`). Se a sonda não puder ser gravada, sai um AVISO de teste inconclusivo e o deploy segue (a conferência pós-gravação ainda protege).
- **Conferência pós-gravação**: depois do PUT de cada item, lê de volta e compara as palavras acentuadas. Divergência **cancela a compilação** e mostra o caminho do backup para rollback.
- **Páginas CSP compiladas**: depois de compilar, localiza a classe gerada de cada CSP (parâmetro `CSPURL`) e procura texto corrompido nela, informando também o charset de saída. Se achar, termina com ALERTA (código de saída 1): a página já está no ar com acento quebrado — avisar o usuário na hora e oferecer o rollback. Se a classe gerada não for localizada, só informa (conferir a tela manualmente).

Em seguida o script: valida conexão, **gera backup XML da versão atual de produção** dos itens (rollback) em `<raiz do repo>/.claude/dev-deploy-prod/backups/AAAAMMDD_HHMMSS_<PacoteRaiz>.xml` (ex.: `20260710_101437_IBTech.Ca.CPPA.xml`; pacote raiz comum das classes, ou pasta comum dos CSP se só houver página), envia cada documento (PUT com `ignoreConflict=1`), compila tudo (`flags=cuk`) e aborta no primeiro erro, mostrando a saída do compilador.

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

Reportar: itens enviados, resultado da verificação de acentuação (sonda, conferência pós-gravação e páginas CSP compiladas), saída de compilação ("Compilation finished successfully"), e o que foi executado no pós-deploy. Lembrar o usuário de testar a tela em produção — conferindo os textos acentuados.

## 6. Artefato (Claude Artifact)

Se o projeto tiver um Artefato publicado associado (URL `https://claude.ai/code/artifact/...` referenciada em README, docs, CLAUDE.md, memória do projeto ou mencionada pelo usuário na conversa), perguntar ao usuário se deseja atualizá-lo com o resultado deste deploy. Ex.: `https://claude.ai/code/artifact/06cd525f-77c1-4215-8267-a9feee6e9b2f`.

- Se sim: usar a ferramenta Artifact com `action: "publish"` e o mesmo `url`, apontando pro arquivo local correspondente (não criar artefato novo).
- Se não souber a URL do artefato, usar `action: "list"` pra localizar antes de perguntar.
- Nunca atualizar sem confirmação explícita do usuário.

## Regras

- Só deployar o que está compilando sem erro na homologação (perguntar se não souber)
- Configurações de DADOS (registros em tabelas, ex.: `tipoConsulta` de campos do boletim) não vão via deploy — tratar via `--query` com aprovação ou pela tela do sistema
- Erro de compilação em produção: reportar imediatamente com a mensagem exata; não tentar "consertar" direto em produção
- Acentuação: nunca pular o passo 1.1; `--ignorar-acentuacao` só com aprovação explícita do usuário depois de ver os problemas. Arquivo fora de UTF-8 bloqueia sempre (não há como enviar sem estragar os acentos). Corrigir sempre no arquivo local (e commitar), nunca direto em produção
- Os documentos temporários da sonda (`Temp.ClaudeSondaEnc`, `zzClaudeSondaEnc.csp`) são apagados pelo próprio script; se ele avisar que não conseguiu apagar, avisar o usuário para remover manualmente
- API observações técnicas: nome de CSP na URL usa barras LITERAIS (não %2F); classes usam nome com pontos
