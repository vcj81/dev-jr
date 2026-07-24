# -*- coding: utf-8 -*-
"""
deploy.py — Deploy de itens no servidor IRIS/Caché de PRODUÇÃO via API Atelier.

Uso:
  python deploy.py --files "src/cls/A/B.cls,src/oth/ibtech/icfpages/x/y.csp"
  python deploy.py --items "IBTech.A.B.cls,/ibtech/icfpages/x/y.csp"
  python deploy.py --build-menu IBTech.Ca.CCQ.Utils
  python deploy.py --query "SELECT TOP 5 ..."

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
import datetime
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

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
    existing = []
    for item in items:
        s, _ = req("GET", doc_url(item), timeout=30)
        if s == 200:
            existing.append(item)
        else:
            print(f"BACKUP: '{item}' não existe em produção (item novo) — sem versão anterior")
    if not existing:
        print("BACKUP: nenhum item pré-existente; nada a exportar.")
        return

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


def prune_backups(bkp_dir, keep=BACKUP_KEEP):
    """Mantém só os `keep` backups mais recentes (nome começa com timestamp, ordem lexical = cronológica)."""
    files = sorted(f for f in os.listdir(bkp_dir) if f.endswith(".xml"))
    for old in files[:-keep] if keep > 0 else files:
        os.remove(os.path.join(bkp_dir, old))
        print(f"BACKUP: removido antigo {old} (retenção: {keep})")


def deploy(items, skip_backup=False):
    check_connection()
    if not skip_backup:
        backup_items(items)
    for item in items:
        path = item_to_file(item)
        if not os.path.isfile(path):
            sys.exit(f"ERRO: arquivo local não encontrado para '{item}': {path}")
        with open(path, encoding="utf-8") as f:
            lines = f.read().splitlines()
        s, b = req("PUT", doc_url(item) + "?ignoreConflict=1", {"enc": False, "content": lines})
        errs = b.get("status", {}).get("errors", [])
        print(f"PUT {item}: HTTP {s}" + (f" ERROS: {errs}" if errs else " ok"))
        if s not in (200, 201) or errs:
            sys.exit("ERRO: falha no envio; compilação abortada.")
    s, b = req("POST", BASE + "/action/compile?flags=cuk", items, timeout=300)
    errs = b.get("status", {}).get("errors", [])
    print(f"COMPILE: HTTP {s}")
    if errs:
        print("ERROS DE COMPILAÇÃO:", json.dumps(errs, indent=1, ensure_ascii=False))
        sys.exit(1)
    print("\n".join(b.get("console", [])))


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
    print("Itens para deploy em PRODUÇÃO:")
    for i in items:
        print("  -", i)
    deploy(items, skip_backup=a.no_backup)


if __name__ == "__main__":
    main()
