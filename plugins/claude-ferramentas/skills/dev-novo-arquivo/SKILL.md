---
name: dev-novo-arquivo
description: Padrões obrigatórios do projeto SIGA para criar qualquer arquivo novo (módulo Python, modelo, teste, documento). Usar SEMPRE antes de criar um arquivo novo no repositório ou quando o usuário invocar /dev-novo-arquivo.
---

# Padrões para criação de novos arquivos — SIGA

O usuário está aprendendo Python: ao criar um arquivo novo, explicar em 2–3 frases as decisões de estrutura tomadas (onde o arquivo foi colocado e por quê).

## Regras gerais (valem para todo arquivo)

1. **Idioma PT-BR em tudo**: nomes de funções, variáveis, classes, docstrings, comentários, mensagens e documentos. Termos técnicos consagrados (test, id, status) podem ficar em inglês.
2. **Rastreabilidade obrigatória**: todo arquivo abre com docstring (ou parágrafo introdutório, em Markdown) dizendo O QUE é e citando a origem da decisão — `(Fase N, seção X)`, `(ADR-00X)` ou `(padrão implícito #N)`. Nada existe "porque sim".
3. **Documentação didática obrigatória** (o usuário está aprendendo): todo arquivo novo deve ser comentado usando a sintaxe de comentário da própria linguagem do arquivo (`#` em Python, `//` ou `/* */` em JS/TS/CSS, `<!-- -->` em HTML/Markdown, `--` em SQL), em dois níveis:
   - **Geral**: no topo do arquivo, explicação de 2–4 linhas do que o arquivo faz e como se encaixa no sistema (em Python, dentro da docstring de módulo).
   - **Inline**: comentários ao longo do código explicando os trechos relevantes — o que cada bloco/função/regra faz e, quando houver, a restrição de negócio por trás (ex.: "domiciliar não consome sala — padrão implícito #7").
4. **Localização antes do conteúdo**: decidir a pasta pela camada (ver mapa abaixo). Se a pasta certa não existe, criar — e em pacote Python novo, criar também o `__init__.py`.

## Mapa de camadas (onde cada arquivo mora)

```
apps/api/siga/dominio/   → regra de negócio pura: NÃO importa FastAPI/HTTP
apps/api/siga/           → casca da API (main.py): rotas, request/response
apps/api/tests/          → testes (fora do pacote siga/)
apps/docs/               → documentos de fase: FaseN_NomeDoDocumento.md
.claude/skills/<nome>/   → skills: SKILL.md com frontmatter name + description
```

A dependência só aponta para dentro: `main.py` importa de `dominio/`; `dominio/` nunca importa de `main.py` nem conhece HTTP/JSON.

## Módulo Python (`.py`)

- Docstring de módulo em PT-BR com propósito + referências de rastreabilidade.
- `from __future__ import annotations` logo após a docstring.
- Imports em 3 blocos separados por linha em branco: stdlib → terceiros → locais (`from .modelos import ...`).
- Tipagem moderna sempre: `list[int]`, `int | None`, retorno anotado em toda função.
- Funções auxiliares internas com prefixo `_` (ex.: `_janela`, `_resultado`).
- Toda função pública tem docstring de 1–3 linhas dizendo o papel dela no fluxo (não repetindo a assinatura).

## Modelos de dados

- Pydantic `BaseModel`; enums como `class X(str, enum.Enum)` com valores em snake_case PT-BR (`"segunda"`, `"grupo_sae"`).
- Campos opcionais como `X | None = None`; listas com `Field(default_factory=list)`.
- Invariantes no próprio modelo: `@model_validator(mode="after")` para coerência entre campos (ex.: `hora_fim > hora_inicio`), `@property` para valores derivados (ex.: `turno`).
- Comportamento que depende só do próprio objeto vira método do modelo (`ocupa_agenda()`, `sobrepoe()`), não função solta.

## Testes (`tests/test_*.py`)

- Um arquivo por alvo: `test_validador.py` testa regra de negócio (sem servidor), `test_api.py` testa o contrato HTTP.
- Docstring do arquivo citando a regra de negócio testada e sua origem (Fase/seção).
- Função-fábrica no topo com defaults realistas e `**kwargs` para variação (ex.: `atendimento(**kwargs)`).
- Agrupar por regra em classes `TestNomeDaRegra`, com docstring citando a fonte da regra.
- Nomes de teste que leem como frase: `test_mesmo_profissional_mesmo_horario_conflita`.
- Cenários espelham dados reais (grades de 2026), não valores aleatórios.

## Documentos (`apps/docs/*.md`)

- Nome no padrão `FaseN_NomeDoDocumento.md`.
- Abrir com contexto: qual fase, qual objetivo, quais decisões anteriores o documento consome (ADRs, DER, fluxos).

## README de app novo

Seções na ordem: título com fase, parágrafo do escopo (incluindo o que NÃO é escopo), `## Setup`, `## Rodar os testes`, `## Subir a API` (ou equivalente), tabela de endpoints/comandos, `## Estrutura` com árvore comentada.

## Checklist final antes de encerrar

- [ ] Arquivo na pasta da camada correta (e `__init__.py` se pacote novo)
- [ ] Docstring/introdução com rastreabilidade (Fase/ADR/padrão implícito)
- [ ] Comentário geral de 2–4 linhas no topo + comentários inline nos trechos relevantes, na sintaxe da linguagem do arquivo
- [ ] Tudo em PT-BR, tipagem completa, imports em 3 blocos
- [ ] Se código de produto: teste correspondente criado/atualizado em `tests/`
- [ ] Explicação didática ao usuário sobre onde o arquivo entrou e por quê
