---
name: dev-novo-arquivo
description: Documentação didática obrigatória em todo arquivo novo de código que o Claude criar — breve explicação geral no topo e comentários inline nos trechos relevantes, em PT-BR, pois o usuário está aprendendo a linguagem. Usar SEMPRE antes de criar um arquivo novo ou quando o usuário invocar /dev-novo-arquivo.
---

# Documentação didática em arquivos novos

O usuário está aprendendo a linguagem. Todo arquivo novo criado pelo Claude deve sair autoexplicativo, em dois níveis:

1. **Explicação geral no topo** (2–4 linhas): o que o arquivo faz e como se encaixa no sistema, escrita na sintaxe de comentário/docstring da própria linguagem.
2. **Comentários inline**: ao longo do código, explicar os trechos relevantes — o que cada bloco/função faz e, quando houver, a regra de negócio por trás.

## Regras

- Comentários e explicações em **PT-BR**; termos técnicos consagrados (test, id, status) podem ficar em inglês.
- Usar a sintaxe de comentário da linguagem do arquivo: `#` em Python, `//` ou `/* */` em JS/TS/CSS, `<!-- -->` em HTML/Markdown, `--` em SQL.
- Comentar para ensinar, não para repetir o óbvio: explicar o porquê e o papel do trecho, não traduzir linha a linha.
- Ao encerrar, explicar ao usuário em 2–3 frases onde o arquivo entrou e por quê.

## Reforço determinístico (hook)

Existe um hook `PreToolUse` (`hooks/check-novo-arquivo.ps1`) que bloqueia o `Write` de arquivo novo em linguagem mapeada (py, js/ts, java, c/cpp/cs, go, php, rb, ps1, sh, css, html, sql, rs, kt, swift) quando o conteúdo tem mais de 3 linhas não vazias e menos de 2 linhas de comentário. É rede de segurança grosseira — só verifica presença mínima de comentário, não qualidade. Não substitui seguir as regras acima; se o hook bloquear, ajustar o conteúdo e reenviar o `Write`.
