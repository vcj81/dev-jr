---
name: dev-padroes-projeto
description: Padrões de arquitetura obrigatórios para todo projeto que usa este plugin — inclui a exigência de que toda interface web nasça preparada para instalação como PWA. Usar SEMPRE ao iniciar um projeto novo, planejar uma nova fase/módulo com frontend, ao revisar/auditar um projeto já existente contra esses padrões, ou quando o usuário invocar /dev-padroes-projeto.
---

# Padrões de projeto

Padrões de arquitetura que valem para **todos** os projetos do usuário que usam este plugin. Consultar em três momentos:

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

## 3. Revisão de projeto existente

Quando o usuário pedir para revisar/auditar um projeto já existente, ou ao notar que um projeto usa este plugin sem seguir os padrões acima:

1. **Levantar o estado atual**: procurar `manifest.json`, service worker registrado, `<link rel="manifest">`, meta tags de tema, e checar se produção roda em HTTPS.
2. **Listar os gaps** encontrados contra cada regra da seção 1 (e futuras regras que forem adicionadas aqui).
3. **Propor alterações uma de cada vez**, em ordem de impacto (ex.: manifest antes de ícones), explicando o "por quê" de cada uma.
4. **Esperar aprovação do usuário antes de aplicar** cada alteração — não aplicar tudo de uma vez sem confirmação.
5. Não sugerir reescrita ou refatoração fora do escopo dos padrões desta skill (isso é trabalho de outra ferramenta/skill).
