# Padrões de projeto (instruções obrigatórias do plugin dev-utils)

Padrões de arquitetura que valem para **todos** os projetos do usuário que usam este plugin. Estas instruções são carregadas automaticamente no início de cada sessão (hook `SessionStart`) e devem ser seguidas sempre, sem precisar de comando. Aplicar em três momentos:

1. **Projeto novo / fase nova com frontend** — aplicar os padrões desde o início, não deixar "para depois".
2. **Revisão de projeto já existente** — auditar contra os padrões abaixo e propor alterações, uma a uma, para aprovação do usuário (ver seção "Revisão de projeto existente").
3. **Uso contínuo** — em qualquer projeto que use este plugin, ficar atento a gaps contra os Padrões de Projeto Modernos listados aqui e sugerir ajuste ao usuário quando notar um, mesmo sem pedido explícito.

## 1. Toda interface web deve ser instalável como PWA

Qualquer projeto que tenha interface web (site, painel, sistema interno) deve nascer preparado para instalação como Progressive Web App. Isso significa incluir desde o início:

- **Web App Manifest** (`manifest.json`): nome do app, ícones em pelo menos 192x192 e 512x512, `"display": "standalone"`, cor de tema e cor de fundo.
- **Service Worker** registrado, no mínimo com cache básico dos arquivos estáticos (o suficiente para o navegador oferecer o botão "Instalar").
- **HTTPS** em produção (em `localhost` o PWA funciona sem HTTPS, para testes).
- `<link rel="manifest">` e meta tags de tema no HTML principal.

Regras práticas:

- Ao criar o primeiro HTML de um projeto, já criar junto o manifest e o service worker — não deixar "para depois".
- Ao planejar uma fase de frontend, listar o PWA como requisito, não como opcional.
- Testar a instalabilidade com o Chrome/Edge (DevTools → Application → Manifest) antes de considerar a fase concluída.

**Por quê:** os usuários finais dos projetos (ex.: profissionais da APAE no SIGA) acessam por celular e desktop; o PWA dá ícone na tela inicial e experiência de app nativo sem custo de loja de aplicativos nem desenvolvimento separado por plataforma.

## 2. Como aplicar em backends existentes

Se o projeto já tem backend (ex.: FastAPI) e o frontend vier depois, o próprio backend pode servir os arquivos do PWA (manifest, service worker, ícones) como arquivos estáticos — não é preciso servidor separado.

## 3. Acentuação e encoding: UTF-8 em tudo, charset sempre explícito

Texto acentuado (labels, títulos, mensagens) não pode depender da configuração do editor nem do servidor. É isso que faz a tela aparecer certa na homologação e "desconfigurada" em produção — `ConfiguraÃ§Ã£o`, `Configura??o`, `Configura�o`. <!-- acentuacao: ignorar -->

- **Arquivos sempre em UTF-8 sem BOM** — nunca Windows-1252/Latin-1. Ao criar ou editar arquivo, gravar os caracteres acentuados reais (`ç`, `ã`, `é`), sem trocar por ASCII nem por `?`. Ao mexer em arquivo com texto corrompido, não "consertar no olho": usar o `--corrigir` do verificador abaixo.
- **Charset declarado explicitamente em toda saída web** — HTML: `<meta charset="utf-8">`; página CSP (IRIS/Caché): `<csp:content charset="utf-8">` coerente com o `<meta>`; classe que herda de `%CSP.Page`: `Parameter CHARSET = "utf-8";`. Nunca depender do padrão do servidor: homologação e produção podem estar configuradas diferente. (Preferir UTF-8; o essencial é ser explícito e igual nos dois lugares.)
- **Evitar caracteres fora do Latin-1 em textos que vão para o Caché** — aspas curvas, travessão, reticências, marcadores e emoji costumam vir de copiar/colar do Word ou do WhatsApp e viram `?` em servidor Caché 8-bit. Usar o equivalente ASCII (`"`, `-`, `...`) ou a entidade HTML (`&ldquo;`, `&ndash;`, `&hellip;`, `&bull;`).
- **Editor travado em UTF-8 no repositório** — `.vscode/settings.json` com `"files.encoding": "utf8"` e `"files.autoGuessEncoding": false`, e `.editorconfig` com `charset = utf-8`. Se o projeto não tiver, propor a criação (com aprovação). **Antes de travar**, rodar o verificador em todos os arquivos de texto do repositório e converter os que não estiverem em UTF-8 — senão o editor abre esses arquivos com `�` no lugar dos acentos e, ao salvar, a perda vira permanente. <!-- acentuacao: ignorar -->
- **Verificação automática na rotina** — o `/dev-deploy-prod` verifica antes da aprovação, bloqueia arquivo fora de UTF-8 ou com acento corrompido, testa a gravação no servidor com uma sonda e confere cada item depois de gravado e compilado; o `/dev-commit-push` roda a mesma checagem nos arquivos do commit. Avulso: `python <plugin dev-utils>/skills/dev-deploy-prod/acentuacao.py <arquivos>` (`--corrigir` mostra a correção automática; `--corrigir --aplicar` grava).

**Por quê:** os sistemas são em português e usados pelo público final; label com acento quebrado em produção passa impressão de sistema malfeito, e o problema costuma aparecer só depois do deploy, já na tela do usuário.

## 4. Revisão de projeto existente

Quando o usuário pedir para revisar/auditar um projeto já existente, ou ao notar que um projeto usa este plugin sem seguir os padrões acima:

1. **Levantar o estado atual**: procurar `manifest.json`, service worker registrado, `<link rel="manifest">`, meta tags de tema, e checar se produção roda em HTTPS. Para acentuação: rodar o verificador `acentuacao.py` nos arquivos de texto do repositório, conferir charset explícito nas páginas e se existem `.editorconfig` / `.vscode/settings.json` com UTF-8.
2. **Listar os gaps** encontrados contra cada regra das seções 1 e 3 (e futuras regras que forem adicionadas aqui).
3. **Propor alterações uma de cada vez**, em ordem de impacto (ex.: manifest antes de ícones), explicando o "por quê" de cada uma.
4. **Esperar aprovação do usuário antes de aplicar** cada alteração — não aplicar tudo de uma vez sem confirmação.
5. Não sugerir reescrita ou refatoração fora do escopo destes padrões (isso é trabalho de outra ferramenta/skill).
