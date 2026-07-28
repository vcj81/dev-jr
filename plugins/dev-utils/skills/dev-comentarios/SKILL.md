---
name: dev-comentarios
description: Comentários obrigatórios no código, em PT-BR — em arquivo NOVO, explicação didática no topo + comentários inline; em arquivo ALTERADO, um comentário por bloco alterado com Autor (usuário do GitHub), Data/Hora e o porquê da mudança. Usar SEMPRE antes de criar um arquivo novo, ao comentar/documentar alterações pendentes, antes de commitar, ou quando o usuário invocar /dev-comentarios.
---

# Comentários no código

Duas situações, uma regra: nada de código sem comentário em PT-BR.

- **Arquivo novo** → parte A (documentação didática). O usuário está aprendendo a linguagem.
- **Arquivo já existente que foi alterado** → parte B (rastreio da alteração). Quem mudou, quando e por quê.

A parte B é checada pela `dev-commit-push` antes do commit.

---

# Parte A — Arquivo novo (documentação didática)

Todo arquivo novo criado pelo Claude deve sair autoexplicativo, em dois níveis:

1. **Explicação geral no topo** (2–4 linhas): o que o arquivo faz e como se encaixa no sistema, escrita na sintaxe de comentário/docstring da própria linguagem.
2. **Comentários inline**: ao longo do código, explicar os trechos relevantes — o que cada bloco/função faz e, quando houver, a regra de negócio por trás.

Regras:

- Comentar para ensinar, não para repetir o óbvio: explicar o porquê e o papel do trecho, não traduzir linha a linha.
- Ao encerrar, explicar ao usuário em 2–3 frases onde o arquivo entrou e por quê.
- Arquivo novo **não** leva marcador `[Alteração]` — o arquivo inteiro é novo, não há bloco alterado.

## Reforço determinístico (hook)

Existe um hook `PreToolUse` (`scripts/check-novo-arquivo.ps1`) que bloqueia o `Write` de arquivo novo em linguagem mapeada (py, js/ts, java, c/cpp/cs, go, php, rb, ps1, sh, css, html, sql, rs, kt, swift) quando o conteúdo tem mais de 3 linhas não vazias e menos de 2 linhas de comentário. É rede de segurança grosseira — só verifica presença mínima de comentário, não qualidade. Não substitui seguir as regras acima; se o hook bloquear, ajustar o conteúdo e reenviar o `Write`.

---

# Parte B — Arquivo alterado (rastreio da alteração)

## B1. Levantar os blocos alterados

- `git status --short` — arquivos modificados/novos/deletados
- `git diff -U3` e `git diff --cached -U3` — hunks alterados (não staged e staged)

Considerar apenas arquivos de **código** já existentes (modificados). Ficam de fora:

- Arquivos novos → parte A
- Arquivos deletados
- Dados/config/gerados: `.json`, `.md`, `.yml`, `.yaml`, `.lock`, `.csv`, `.env*`, minificados, `dist/`, `build/`, `node_modules/`
- Mudança puramente cosmética (só indentação/espaço em branco, sem mudança de comportamento)

## B2. Pegar o autor e a data/hora reais

Sempre obter do sistema, nunca chutar nem escrever nome fixo.

**Autor** — usuário do GitHub, resolvido nesta ordem (para no primeiro que retornar valor não vazio):

```powershell
gh api user --jq ".login"   # 1º: login real do GitHub (se o gh CLI estiver instalado e autenticado)
git config user.name        # 2º: fallback
```

Se os dois falharem ou vierem vazios, perguntar o usuário do GitHub antes de inserir qualquer comentário — não inventar e não usar "Claude".

**Data/hora**:

```powershell
Get-Date -Format "dd/MM/yyyy HH:mm"
```

Resolver autor e data/hora **uma vez por rodada** e usar o mesmo par em todos os blocos daquela rodada.

## B3. Inserir o comentário em cada bloco alterado

Formato padrão, na sintaxe de comentário da linguagem do arquivo, imediatamente **acima** do bloco alterado e na mesma indentação dele:

```
// [Alteração] Autor: <usuário do GitHub> | Data/Hora: <dd/MM/yyyy HH:mm>
// <o que mudou e por quê, 1–2 linhas>
```

Exemplo já resolvido (autor vindo do B2, não digitado à mão):

```
// [Alteração] Autor: ciaca-jr | Data/Hora: 28/07/2026 14:32
// compara tipo também, senão "0" passava como válido
```

Regras de posicionamento:

- Um comentário por bloco lógico alterado, não por linha. Linhas contíguas que mudaram pelo mesmo motivo = um comentário só.
- Se o bloco alterado é o corpo inteiro de uma função/método, o comentário vai acima da assinatura.
- Se o mesmo arquivo tem alterações independentes em pontos distantes, cada ponto ganha seu comentário.
- Nunca reescrever, reindentar ou reformatar o código ao inserir o comentário — só adicionar linhas.
- Se já existir um `[Alteração]` do mesmo bloco de uma rodada anterior, **não apagar**: adicionar o novo abaixo do antigo (histórico cresce em ordem cronológica).
- Se o mesmo bloco já foi marcado nesta mesma rodada, não duplicar.

## B4. Relatar

Ao terminar, mostrar ao usuário:

- Lista `arquivo:linha` de cada comentário inserido, com o resumo usado
- Arquivos alterados que foram **pulados** e o motivo (novo, dado/config, cosmético)

---

# Sintaxe de comentário por linguagem

| Linguagem | Comentário |
|---|---|
| JS/TS/Java/C/C#/Go/Rust/Kotlin/Swift | `//` |
| CSS/SCSS/LESS | `/* */` |
| Python/Ruby/Shell/PowerShell/YAML | `#` |
| SQL | `--` |
| HTML/XML/Markdown | `<!-- -->` |
| ObjectScript (IRIS/Caché `.cls`/`.mac`/`.inc`) | `//` no corpo do método; `///` acima da definição de classe/método |
| CSP | `<!-- -->` no HTML, `//` dentro de `<script>`/`<script language="cache">` |

# Regras gerais

- Comentários em **PT-BR**; termos técnicos consagrados (test, id, status) podem ficar em inglês.
- Autor é **sempre** o usuário do GitHub resolvido no B2 — nunca nome fixo no texto da skill, nunca "Claude", nunca atribuição de IA.
- O comentário explica o **porquê**, não traduz a linha (`// troca == por ===` é ruim; `// compara tipo também, senão "0" passava como válido` é bom).
- Nunca commitar nem fazer push aqui — esta skill só escreve/edita arquivos. Commit é da `dev-commit-push`.
