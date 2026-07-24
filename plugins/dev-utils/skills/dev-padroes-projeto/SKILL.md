---
name: dev-padroes-projeto
description: Padrões de arquitetura obrigatórios para todo projeto novo ou nova fase de projeto — inclui a exigência de que toda interface web nasça preparada para instalação como PWA. Usar SEMPRE ao iniciar um projeto novo, planejar uma nova fase/módulo com frontend, ou quando o usuário invocar /dev-padroes-projeto.
---

# Padrões de projeto

Padrões de arquitetura que valem para **todos** os projetos do usuário. Consultar ao iniciar um projeto novo, ao planejar uma fase que inclua frontend, e ao revisar propostas de arquitetura.

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
