# -*- coding: utf-8 -*-
# [Alteração] Autor: vcj81 | Data/Hora: 13/11/2026 11:46
# documenta a verificação de acentuação (--verificar / --ignorar-acentuacao) no cabeçalho.
"""
deploy.py — Deploy de itens no servidor IRIS/Caché de PRODUÇÃO via API Atelier.

Uso:
  python deploy.py --files "src/cls/A/B.cls,src/oth/ibtech/icfpages/x/y.csp"
  python deploy.py --items "IBTech.A.B.cls,/ibtech/icfpages/x/y.csp"
  python deploy.py --verificar --files "..."   (só verifica acentuação, não envia nada)
  python deploy.py --build-menu IBTech.Ca.CCQ.Utils
  python deploy.py --query "SELECT TOP 5 ..."

Verificação de acentuação (automática em todo deploy; ver acentuacao.py):
  1. arquivos locais: UTF-8 válido, sem texto corrompido/acento perdido (ERRO bloqueia);
  2. versão atual em produção (só leitura): acento já quebrado lá, ou palavra que
     está acentuada em produção e chegaria SEM acento;
  3. sonda: grava um documento temporário com os acentos usados, lê de volta e
     apaga — se o servidor trocar algum caractere, bloqueia ANTES de mexer nos itens;
  4. depois de gravar cada item: lê de volta e confere as palavras acentuadas —
     divergência cancela a compilação;
  5. depois de compilar: confere os textos da classe gerada de cada página CSP.
--verificar roda só as etapas 1 e 2 (nada é gravado). --ignorar-acentuacao rebaixa
os ERROs de acentuação para aviso (usar só com aprovação explícita do usuário).

Antes de enviar, a versão ATUAL de produção dos itens é exportada em XML
(rollback) para <repo>/.claude/dev-deploy-prod/backups/AAAAMMDD_HHMMSS_<PacoteRaiz>.xml.
Pular com --no-backup.

O script roda como skill de um plugin (compartilhado entre projetos) — por isso
REPO_ROOT é sempre o diretório atual (execute com cwd na raiz do repo alvo, como
já indicam os comandos do SKILL.md), nunca calculado a partir de onde o script
está instalado.

Configuração: arquivo <repo>/.claude/dev-deploy-prod/.env (ver .env.example ao
lado deste script — fica local a cada repositório, nunca no plugin).
"""
import argparse
import base64
# [Alteração] Autor: vcj81 | Data/Hora: 13/11/2026 16:43
# collections e re (abaixo) são usados pela verificação de acentuação (contagem de
# palavras acentuadas; versão do servidor, marcadores da sonda e charset da CSP).
import collections
import datetime
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

# [Alteração] Autor: vcj81 | Data/Hora: 13/11/2026 11:46
# módulo de verificação de acentuação (mesma pasta) + console em UTF-8: no Windows a
# saída padrão é cp1252 e as mensagens com acento saíam trocadas ("Conexão" sem o "ã").
import acentuacao
from acentuacao import ERRO, AVISO

acentuacao.console_utf8()

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Repo alvo = diretório de onde o script é chamado (sempre a raiz do projeto)
REPO_ROOT = os.getcwd()
# Config/segredos/backups ficam no repo alvo, nunca junto do script (que pode
# estar instalado globalmente como skill de plugin, compartilhado entre repos)
CONFIG_DIR = os.path.join(REPO_ROOT, ".claude", "dev-deploy-prod")
ENV_PATH = os.path.join(CONFIG_DIR, ".env")
BACKUP_DIR = os.path.join(CONFIG_DIR, "backups")
# Backups ficam só localmente no projeto; mantém apenas os N mais recentes
BACKUP_KEEP = 3


def load_env():
    env = {}
    if not os.path.isfile(ENV_PATH):
        example = os.path.join(SCRIPT_DIR, ".env.example")
        sys.exit(f"ERRO: {ENV_PATH} não existe. Copie {example} pra lá e preencha.")
    with open(ENV_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    for k in ("PROD_HOST", "PROD_USER", "PROD_PASSWORD", "PROD_NAMESPACE"):
        if not env.get(k):
            sys.exit(f"ERRO: variável {k} ausente no .env")
    return env


ENV = load_env()
BASE = f"http://{ENV['PROD_HOST']}/api/atelier/v1/{ENV['PROD_NAMESPACE']}"
AUTH = base64.b64encode(f"{ENV['PROD_USER']}:{ENV['PROD_PASSWORD']}".encode()).decode()


def req(method, url, payload=None, timeout=120):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    r = urllib.request.Request(url, data=data, method=method)
    r.add_header("Authorization", "Basic " + AUTH)
    r.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {"raw": body[:1000]}


def doc_url(item):
    # CSP: barras LITERAIS na URL (%2F retorna 404). Classes: nome com pontos.
    if item.startswith("/"):
        return BASE + "/doc" + urllib.parse.quote(item)
    return BASE + "/doc/" + urllib.parse.quote(item, safe="")


def map_file_to_item(path):
    """src/cls/A/B.cls -> A.B.cls | src/oth/x/y.csp -> /x/y.csp | None se não mapeável."""
    rel = path.replace("\\", "/").lstrip("./")
    if rel.startswith("src/cls/") and rel.endswith(".cls"):
        return rel[len("src/cls/"):-len(".cls")].replace("/", ".") + ".cls"
    if rel.startswith("src/mac/") and rel.endswith(".mac"):
        return rel[len("src/mac/"):-len(".mac")].replace("/", ".") + ".mac"
    if rel.startswith("src/inc/") and rel.endswith(".inc"):
        return rel[len("src/inc/"):-len(".inc")].replace("/", ".") + ".inc"
    if rel.startswith("src/oth/") and rel.endswith(".csp"):
        return "/" + rel[len("src/oth/"):]
    return None


def item_to_file(item):
    """Caminho local do item (para ler o conteúdo)."""
    if item.startswith("/"):
        return os.path.join(REPO_ROOT, "src", "oth", *item.lstrip("/").split("/"))
    base, ext = item.rsplit(".", 1)
    return os.path.join(REPO_ROOT, "src", ext, *base.split(".")) + "." + ext


def check_connection():
    s, b = req("GET", BASE, timeout=15)
    if s != 200:
        sys.exit(f"ERRO: sem conexão com {BASE} (HTTP {s}): {json.dumps(b)[:300]}")
    print(f"Conexão ok: {ENV['PROD_HOST']} ns {ENV['PROD_NAMESPACE']}")


# [Alteração] Autor: vcj81 | Data/Hora: 13/11/2026 11:46
# Verificação de acentuação antes/durante/depois do deploy: labels que estavam
# certos na homologação chegavam com acento quebrado em produção.
# ---------------------------------------------------------------------------
# Verificação de acentuação
# ---------------------------------------------------------------------------

# Nomes dos documentos temporários da sonda (etapa 3) — apagados logo após o teste.
SONDA_CLASSE = "Temp.ClaudeSondaEnc"
SONDA_CSP = "zzClaudeSondaEnc.csp"
# Marcadores ASCII em volta da amostra: eles não sofrem com encoding, então dá para
# achar a amostra na volta mesmo que os acentos tenham sido trocados.
SONDA_INI, SONDA_FIM = "#SONDA-INI#", "#SONDA-FIM#"


def erros_api(b):
    """Lista de erros que a API Atelier devolve em status.errors (vazia = ok)."""
    return (b.get("status") or {}).get("errors") or []


def conteudo_doc(b):
    """Linhas de um documento devolvido pelo GET /doc da API Atelier."""
    conteudo = (b.get("result") or {}).get("content")
    return conteudo if isinstance(conteudo, list) else []


def bloquear(motivo, ignorar):
    """Para o deploy por problema de acentuação — ou só avisa, com --ignorar-acentuacao."""
    if ignorar:
        print(f"\nAVISO: {motivo} — seguindo mesmo assim por --ignorar-acentuacao")
        return
    sys.exit(f"\nDEPLOY BLOQUEADO: {motivo}\n"
             "Nada dos itens reais foi enviado. Corrija e rode de novo; para seguir mesmo assim "
             "(só com aprovação do usuário), repita com --ignorar-acentuacao.")


def servidor_unicode():
    """Diz se o servidor de produção é Unicode: (True|False|None, texto da versão).

    A versão vem de GET /api/atelier/ — ex.: "Cache for Windows (x86-64) 2018.1 (Build 184U)".
    O "U" no fim do build indica instalação Unicode; IRIS é sempre Unicode. Num Caché
    8-bit, caractere fora do Latin-1 (aspas curvas, travessão, emoji) não é gravado.
    """
    s, b = req("GET", f"http://{ENV['PROD_HOST']}/api/atelier/", timeout=15)
    versao = (((b.get("result") or {}).get("content") or {}).get("version") or "") if s == 200 else ""
    if "IRIS" in versao.upper():
        return True, versao
    m = re.search(r"\(Build ([^)]*)\)", versao)
    return (m.group(1).strip().endswith("U") if m else None), versao


def ler_locais(items):
    """Bytes do arquivo local de cada item (sai com erro se algum não existir)."""
    dados = {}
    for item in items:
        path = item_to_file(item)
        if not os.path.isfile(path):
            sys.exit(f"ERRO: arquivo local não encontrado para '{item}': {path}")
        with open(path, "rb") as f:
            dados[item] = f.read()
    return dados


def linhas_para_envio(item, dados):
    """Texto que vai para o servidor: UTF-8 sem BOM, quebrado só em \\n/\\r\\n.

    Arquivo fora de UTF-8 não tem como ser enviado sem estragar os acentos —
    esse caso bloqueia sempre, mesmo com --ignorar-acentuacao.
    """
    texto, _ = acentuacao.decodificar(dados)
    if texto is None:
        path = item_to_file(item)
        sys.exit(f"ERRO: '{path}' não está em UTF-8 — converta antes de enviar:\n"
                 f'  python "{os.path.join(SCRIPT_DIR, "acentuacao.py")}" --corrigir "{path}"')
    return acentuacao.linhas(texto)


def verificar_locais(items, locais, unicode_srv, ignorar=False):
    """Etapa 1 — local, nada é gravado: analisa os arquivos que serão enviados."""
    print("\n== Acentuação: arquivos locais ==")
    total = collections.Counter()
    for item in items:
        path = item_to_file(item)
        achados = acentuacao.analisar_arquivo(path, locais[item], unicode_srv)
        total.update(acentuacao.resumo(achados))
        print(acentuacao.formatar(os.path.relpath(path, REPO_ROOT), achados))
    print(f"Resumo: {total[ERRO]} erro(s), {total[AVISO]} aviso(s)")
    if total[ERRO]:
        bloquear(f"{total[ERRO]} erro(s) de acentuação nos arquivos locais", ignorar)


def comparar_com_producao(items, enviar):
    """Etapa 2 — só leitura: compara com a versão ATUAL de produção.

    Mostra (a) se produção já está hoje com acento quebrado — o deploy corrige — e
    (b) palavras acentuadas em produção que no arquivo local aparecem SEM acento
    ("Usuário" virou "Usuario"), sinal de arquivo que perdeu a acentuação.
    """
    print("\n== Acentuação: versão atual em produção (só leitura) ==")
    for item in items:
        s, b = req("GET", doc_url(item), timeout=30)
        if s != 200:
            print(f"  novo  {item} (ainda não existe em produção)")
            continue
        remoto = conteudo_doc(b)
        quebrados = [a for a in acentuacao.analisar_linhas(remoto, checar_latin1=False) if a.nivel == ERRO]
        perdidos = acentuacao.acentos_removidos(remoto, enviar[item])
        if not quebrados and not perdidos:
            print(f"  ok    {item}")
            continue
        print(f"  {item}")
        if quebrados:
            print(f"    [INFO] produção HOJE já tem {len(quebrados)} linha(s) com acento quebrado — "
                  "este deploy substitui pelo conteúdo local (que passou na etapa 1)")
            for a in quebrados[:3]:
                print(f"        linha {a.linha}: {a.trecho}")
        if perdidos:
            print("    [AVISO] palavras acentuadas em produção chegariam SEM acento (conferir com a homologação):")
            print("        " + ", ".join(f"'{antes}' → '{depois}'" for antes, depois in perdidos[:8]))


def sonda_encoding(items, enviar, ignorar=False):
    """Etapa 3 — antes de mexer nos itens reais: grava um documento TEMPORÁRIO com
    todos os caracteres acentuados que serão enviados, lê de volta e apaga.

    Se o servidor devolver algo diferente, os itens reais sofreriam a mesma troca:
    o deploy é bloqueado. Testa os dois caminhos de gravação que existem: classe/
    rotina (vai para o banco) e página CSP (vira arquivo no disco do servidor).
    """
    print("\n== Acentuação: sonda de gravação em produção ==")

    def acentuados(grupo):
        """Caracteres não-ASCII visíveis usados pelos itens do grupo, sem repetição."""
        return "".join(sorted({c for i in grupo for linha in enviar[i] for c in linha
                               if ord(c) > 127 and c.isprintable()}))

    # Cada caminho de gravação é testado só com os caracteres dos itens que vão por ele.
    classes = [i for i in items if not i.startswith("/")]
    csps = [i for i in items if i.startswith("/")]
    alvos = []
    amostra = acentuados(classes)
    if amostra:
        alvos.append(("classe", SONDA_CLASSE + ".cls", amostra, [
            f"Class {SONDA_CLASSE} Extends %RegisteredObject",
            "{", "",
            "/// Sonda temporaria de encoding do deploy.py - removida automaticamente",
            f'Parameter SONDA = "{SONDA_INI}{amostra}{SONDA_FIM}";',
            "", "}",
        ]))
    amostra = acentuados(csps)
    if amostra:
        pasta = csps[0].rsplit("/", 1)[0]
        alvos.append(("página CSP", f"{pasta}/{SONDA_CSP}", amostra, [
            "<!-- sonda temporaria de encoding do deploy.py - removida automaticamente -->",
            f"<p>{SONDA_INI}{amostra}{SONDA_FIM}</p>",
        ]))
    if not alvos:
        print("  dispensada: nenhum caractere acentuado nos arquivos")
        return

    falhas = 0
    for tipo, nome, amostra, conteudo in alvos:
        s, b = req("PUT", doc_url(nome) + "?ignoreConflict=1", {"enc": False, "content": conteudo})
        if s not in (200, 201) or erros_api(b):
            print(f"  AVISO {tipo}: sonda não pôde ser gravada (HTTP {s}) — teste inconclusivo: {erros_api(b)}")
            continue
        try:
            s, b = req("GET", doc_url(nome), timeout=30)
            m = re.search(re.escape(SONDA_INI) + "(.*?)" + re.escape(SONDA_FIM), "\n".join(conteudo_doc(b)), re.S)
            recebido = m.group(1) if m else None
        finally:
            sd, bd = req("DELETE", doc_url(nome), timeout=30)
            if sd != 200 or erros_api(bd):
                print(f"  AVISO: não consegui apagar a sonda {nome} (HTTP {sd}) — apagar manualmente")
        if recebido == amostra:
            print(f"  ok    {tipo}: {len(amostra)} caractere(s) gravado(s) e lido(s) sem alteração: {amostra}")
        else:
            falhas += 1
            print(f"  [ERRO] {tipo}: o servidor ALTEROU caracteres na gravação")
            print("        " + descrever_troca(amostra, recebido))
    if falhas:
        bloquear("o servidor de produção não grava os acentos destes arquivos sem alterá-los "
                 "(ver sonda acima)", ignorar)


def descrever_troca(enviado, recebido):
    """Explica caractere a caractere o que o servidor trocou na sonda."""
    if recebido is None:
        return "a amostra não voltou (marcadores não encontrados na leitura)"
    if len(enviado) == len(recebido):
        trocas = [f"'{e}' U+{ord(e):04X} → '{r}' U+{ord(r):04X}" for e, r in zip(enviado, recebido) if e != r]
        return "trocas: " + ", ".join(trocas)
    return f"enviado: {enviado} | devolvido: {recebido}"


def conferir_gravacao(item, enviado):
    """Etapa 4 — depois do PUT: lê o item de volta e compara as palavras acentuadas."""
    s, b = req("GET", doc_url(item), timeout=30)
    if s != 200:
        return [f"não foi possível ler o item de volta (HTTP {s})"]
    return acentuacao.comparar(enviado, conteudo_doc(b))


def conferir_csp_compilado(item, enviado):
    """Etapa 5 — depois de compilar, só para páginas CSP (melhor esforço, só leitura).

    O compilador CSP gera uma classe a partir do arquivo (parâmetro CSPURL = URL da
    página). Se ele ler o arquivo com uma codificação diferente da gravada, os textos
    da classe gerada saem quebrados mesmo com o arquivo certo — o caso típico de
    "na homologação está certo e em produção não". Devolve True se achou problema.
    """
    url = item.replace("'", "''")
    sql = ("SELECT parent FROM %Dictionary.ParameterDefinition "
           f"WHERE Name = 'CSPURL' AND UPPER(_Default) = UPPER('{url}')")
    s, b = req("POST", BASE + "/action/query", {"query": sql}, timeout=60)
    achou = (b.get("result") or {}).get("content") or []
    if s != 200 or erros_api(b) or not achou:
        print(f"  --    {item}: classe gerada não localizada — conferir a tela manualmente")
        return False
    classe = list(achou[0].values())[0]
    s, b = req("GET", doc_url(classe + ".cls"), timeout=30)
    gerado = conteudo_doc(b)
    if s != 200 or not gerado:
        print(f"  --    {item}: não consegui ler a classe gerada {classe} — conferir a tela manualmente")
        return False

    def qtd_erros(lista):
        return sum(1 for a in acentuacao.analisar_linhas(lista, checar_latin1=False) if a.nivel == ERRO)

    m = re.search(r'^Parameter\s+CHARSET\s*=\s*"([^"]*)"', "\n".join(gerado), re.M | re.I)
    charset = f"charset de saída {m.group(1)}" if m else "sem Parameter CHARSET: saída no padrão do servidor"
    if qtd_erros(gerado) > qtd_erros(enviado):
        quebrados = [a for a in acentuacao.analisar_linhas(gerado, checar_latin1=False) if a.nivel == ERRO]
        print(f"  [ALERTA] {item} → {classe}: textos da página compilada estão com acento quebrado ({charset})")
        for a in quebrados[:3]:
            print(f"        linha {a.linha}: {a.trecho}")
        return True
    print(f"  ok    {item} → {classe} ({charset})")
    return False


def preparar(items, ignorar=False):
    """Etapas 1 e 2 (nada é gravado). Devolve (unicode_srv, linhas a enviar por item)."""
    unicode_srv, versao = servidor_unicode()
    tipo = {True: "Unicode", False: "8-bit (caractere fora do Latin-1 não é gravado)", None: "não identificado"}
    print(f"Servidor: {versao or 'versão não informada'} — {tipo[unicode_srv]}")
    locais = ler_locais(items)
    verificar_locais(items, locais, unicode_srv, ignorar)
    enviar = {item: linhas_para_envio(item, locais[item]) for item in items}
    comparar_com_producao(items, enviar)
    return unicode_srv, enviar


def verificar(items):
    """--verificar: roda só as etapas que não gravam nada em produção."""
    check_connection()
    preparar(items)
    print("\nVerificação concluída sem erros de acentuação. No deploy, antes de enviar os itens, "
          "a sonda testa a gravação no servidor e cada item é conferido depois de gravado.")


def backup_label(items):
    """Pacote/pasta raiz comum dos itens, para compor o nome do arquivo de backup.

    Prefere o pacote das classes (ex.: IBTech.Ca.CPPA); se só houver CSP, usa a
    pasta comum com barras trocadas por pontos. Comparação case-insensitive,
    preservando a grafia do primeiro item.
    """
    cls_pkgs = [i.split(".")[:-2] for i in items if not i.startswith("/")]
    csp_dirs = [i.strip("/").split("/")[:-1] for i in items if i.startswith("/")]
    paths = cls_pkgs or csp_dirs
    if not paths:
        return ""
    common = []
    for segs in zip(*paths):
        if all(s.lower() == segs[0].lower() for s in segs):
            common.append(segs[0])
        else:
            break
    return ".".join(common)


def backup_items(items):
    """Exporta do servidor a versão ATUAL dos itens (XML Caché) antes de sobrescrever.

    Usa classe temporária com SqlProc (mesmo padrão do --build-menu): o export vai
    para chunks em um global e é lido via SQL, pois a API Atelier não devolve o
    formato XML de export diretamente.
    """
    # [Alteração] Autor: vcj81 | Data/Hora: 13/11/2026 11:46
    # devolve o caminho do backup (None se não houve) — a conferência de acentuação
    # usa nas instruções de rollback quando cancela a compilação.
    existing = []
    for item in items:
        s, _ = req("GET", doc_url(item), timeout=30)
        if s == 200:
            existing.append(item)
        else:
            print(f"BACKUP: '{item}' não existe em produção (item novo) — sem versão anterior")
    if not existing:
        print("BACKUP: nenhum item pré-existente; nada a exportar.")
        return None

    tmp = "Temp.ClaudeBackupXML"
    gbl = "^CacheTempClaudeBkp"
    cls = [
        f"Class {tmp} Extends %RegisteredObject",
        "{", "",
        "ClassMethod prep(itens As %String) As %String [ SqlProc ]",
        "{",
        f" kill {gbl}",
        " set st=##class(%Stream.TmpCharacter).%New()",
        " set sc=$SYSTEM.OBJ.ExportToStream(itens,.st,\"-d\")",
        ' if $SYSTEM.Status.IsError(sc) quit "ERRO: "_$SYSTEM.Status.GetErrorText(sc)',
        " do st.Rewind()",
        " set n=0",
        f" while 'st.AtEnd {{ set n=n+1,{gbl}(n)=st.Read(100000) }}",
        f" set {gbl}=n",
        ' quit "ok:"_n',
        "}", "",
        "ClassMethod chunk(i As %Integer) As %String [ SqlProc ]",
        "{",
        f" quit $get({gbl}(i))",
        "}", "",
        "ClassMethod done() As %String [ SqlProc ]",
        "{",
        f" kill {gbl}",
        ' quit "ok"',
        "}", "", "}",
    ]
    req("PUT", doc_url(tmp + ".cls") + "?ignoreConflict=1", {"enc": False, "content": cls})
    s, b = req("POST", BASE + "/action/compile?flags=cuk", [tmp + ".cls"])
    errs = b.get("status", {}).get("errors", [])
    if errs:
        sys.exit(f"ERRO ao compilar classe temporária de backup: {errs}")

    def sql_result(query):
        s, b = req("POST", BASE + "/action/query", {"query": query}, timeout=300)
        content = b.get("result", {}).get("content") or []
        errs = b.get("status", {}).get("errors")
        if errs or not content:
            sys.exit(f"ERRO no backup (SQL): {errs}")
        return list(content[0].values())[0]

    itens_sql = ",".join(existing).replace("'", "''")
    try:
        ret = sql_result(f"SELECT {tmp}_prep('{itens_sql}') AS r")
        if not str(ret).startswith("ok:"):
            sys.exit(f"ERRO no export de backup: {ret}")
        n = int(str(ret).split(":")[1])
        xml = "".join(sql_result(f"SELECT {tmp}_chunk({i}) AS r") for i in range(1, n + 1))
    finally:
        req("POST", BASE + "/action/query", {"query": f"SELECT {tmp}_done() AS r"})
        req("DELETE", doc_url(tmp + ".cls"))

    bkp_dir = BACKUP_DIR
    os.makedirs(bkp_dir, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    label = backup_label(existing)
    name = f"{stamp}_{label}.xml" if label else f"{stamp}.xml"
    path = os.path.join(bkp_dir, name)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(xml)
    print(f"BACKUP: {len(existing)} item(ns) exportado(s) para {path}")
    prune_backups(bkp_dir)
    return path


def prune_backups(bkp_dir, keep=BACKUP_KEEP):
    """Mantém só os `keep` backups mais recentes (nome começa com timestamp, ordem lexical = cronológica)."""
    files = sorted(f for f in os.listdir(bkp_dir) if f.endswith(".xml"))
    for old in files[:-keep] if keep > 0 else files:
        os.remove(os.path.join(bkp_dir, old))
        print(f"BACKUP: removido antigo {old} (retenção: {keep})")


# [Alteração] Autor: vcj81 | Data/Hora: 13/11/2026 11:46
# encaixa a verificação de acentuação no fluxo: etapas 1-3 antes do backup/envio,
# conferência de cada item logo após o PUT (divergência cancela a compilação) e
# conferência das páginas CSP compiladas. O texto enviado agora sai de
# acentuacao.linhas() (sem BOM, sem quebrar em U+2028/U+0085 como o splitlines()).
def deploy(items, skip_backup=False, ignorar=False):
    check_connection()
    _, enviar = preparar(items, ignorar)
    sonda_encoding(items, enviar, ignorar)
    backup = None
    if not skip_backup:
        backup = backup_items(items)

    print("\n== Envio ==")
    divergentes = []
    for item in items:
        lines = enviar[item]
        s, b = req("PUT", doc_url(item) + "?ignoreConflict=1", {"enc": False, "content": lines})
        errs = b.get("status", {}).get("errors", [])
        print(f"PUT {item}: HTTP {s}" + (f" ERROS: {errs}" if errs else " ok"))
        if s not in (200, 201) or errs:
            sys.exit("ERRO: falha no envio; compilação abortada.")
        problemas = conferir_gravacao(item, lines)
        if problemas:
            divergentes.append(item)
            print(f"  [ERRO] acentuação mudou na gravação de {item}:")
            for p in problemas:
                print(f"        {p}")
        else:
            qtd = sum(acentuacao.palavras_acentuadas(lines).values())
            print(f"  acentos conferidos após gravar: ok ({qtd} palavra(s) acentuada(s))")
    if divergentes and not ignorar:
        rollback = (f'importar o backup "{backup}" ($system.OBJ.Load("<caminho>.xml","cuk") ou Studio)'
                    if backup else "sem backup desta rodada (itens novos ou --no-backup)")
        sys.exit("\nCOMPILAÇÃO CANCELADA: o servidor gravou os acentos diferente do arquivo local.\n"
                 f"Itens JÁ ENVIADOS mas NÃO compilados: {', '.join(items)}\n"
                 "(páginas CSP com autocompile podem já estar servindo o conteúdo novo)\n"
                 f"Para desfazer: {rollback}.\n"
                 "Se for falso positivo (com aprovação do usuário): repetir o deploy com "
                 "--ignorar-acentuacao, que reenvia e compila.")
    if divergentes:
        print("AVISO: divergência de acentuação ignorada por --ignorar-acentuacao — compilando mesmo assim")

    s, b = req("POST", BASE + "/action/compile?flags=cuk", items, timeout=300)
    errs = b.get("status", {}).get("errors", [])
    print(f"COMPILE: HTTP {s}")
    if errs:
        print("ERROS DE COMPILAÇÃO:", json.dumps(errs, indent=1, ensure_ascii=False))
        sys.exit(1)
    print("\n".join(b.get("console", [])))

    csps = [i for i in items if i.startswith("/")]
    if csps:
        print("\n== Acentuação: páginas CSP compiladas ==")
        alertas = [i for i in csps if conferir_csp_compilado(i, enviar[i])]
        if alertas:
            rollback = f'importar o backup "{backup}"' if backup else "sem backup desta rodada"
            sys.exit(f"\nALERTA: deploy concluído, mas {len(alertas)} página(s) compilaram com acento quebrado: "
                     f"{', '.join(alertas)}.\nProvável causa: o compilador CSP de produção lê o arquivo com "
                     "codificação diferente da homologação. Testar a tela agora; para desfazer: "
                     f"{rollback}.")


def build_menu(utils_class):
    check_connection()
    tmp = "Temp.ClaudeRunBuildMenu"
    cls = [
        f"Class {tmp} Extends %RegisteredObject",
        "{", "",
        "ClassMethod run() As %String [ SqlProc ]",
        "{",
        f" set sc=##class({utils_class}).buildMenu(0)",
        ' quit $select($$$ISOK(sc):"ok",1:$SYSTEM.Status.GetErrorText(sc))',
        "}", "", "}",
    ]
    req("PUT", doc_url(tmp + ".cls") + "?ignoreConflict=1", {"enc": False, "content": cls})
    s, b = req("POST", BASE + "/action/compile?flags=cuk", [tmp + ".cls"])
    errs = b.get("status", {}).get("errors", [])
    if errs:
        sys.exit(f"ERRO ao compilar classe temporária: {errs}")
    # SQL: esquema Temp, proc ClaudeRunBuildMenu_run
    s, b = req("POST", BASE + "/action/query", {"query": f"SELECT {tmp}_run() AS resultado"})
    print("buildMenu:", b.get("result", {}).get("content", b.get("status", {}).get("errors")))
    req("DELETE", doc_url(tmp + ".cls"))
    print("Classe temporária removida.")


def run_query(sql):
    check_connection()
    s, b = req("POST", BASE + "/action/query", {"query": sql}, timeout=120)
    content = b.get("result", {}).get("content")
    errs = b.get("status", {}).get("errors")
    print(json.dumps(content if content is not None else errs, indent=1, ensure_ascii=False))


def main():
    p = argparse.ArgumentParser(description="Deploy em produção via API Atelier")
    p.add_argument("--files", help="Arquivos do repo separados por vírgula (mapeados para itens)")
    p.add_argument("--items", help="Itens já no formato Caché separados por vírgula")
    p.add_argument("--build-menu", metavar="CLASSE", help="Executa buildMenu da classe Utils informada")
    p.add_argument("--query", help="Executa uma consulta SQL e mostra o resultado")
    p.add_argument("--no-backup", action="store_true", help="Pula o backup XML pré-deploy")
    # [Alteração] Autor: vcj81 | Data/Hora: 13/11/2026 11:46
    # opções da verificação de acentuação (ver cabeçalho do arquivo).
    p.add_argument("--verificar", action="store_true",
                   help="Só verifica acentuação dos itens (arquivos locais + produção, só leitura); não envia nada")
    p.add_argument("--ignorar-acentuacao", action="store_true",
                   help="Rebaixa os ERROs de acentuação para aviso (só com aprovação explícita do usuário)")
    a = p.parse_args()

    if a.query:
        run_query(a.query)
        return
    if a.build_menu:
        build_menu(a.build_menu)
        return

    items = []
    if a.files:
        for f in a.files.split(","):
            f = f.strip()
            if not f:
                continue
            item = map_file_to_item(f)
            if item is None:
                print(f"AVISO: '{f}' não mapeável (estático ou fora de src/) — pulado")
            else:
                items.append(item)
    if a.items:
        items += [i.strip() for i in a.items.split(",") if i.strip()]
    if not items:
        p.error("informe --files, --items, --build-menu ou --query")
    # [Alteração] Autor: vcj81 | Data/Hora: 13/11/2026 11:46
    # --verificar para antes do envio; o deploy recebe a opção --ignorar-acentuacao.
    print("Itens para " + ("VERIFICAÇÃO de acentuação" if a.verificar else "deploy em PRODUÇÃO") + ":")
    for i in items:
        print("  -", i)
    if a.verificar:
        verificar(items)
        return
    deploy(items, skip_backup=a.no_backup, ignorar=a.ignorar_acentuacao)


if __name__ == "__main__":
    main()
