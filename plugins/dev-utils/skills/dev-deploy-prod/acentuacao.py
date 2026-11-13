# -*- coding: utf-8 -*-
"""
acentuacao.py — Verifica (e, se pedido, corrige) problemas de acentuação/encoding
em arquivos de código ANTES de eles irem para o servidor.

Por que existe: texto acentuado (labels, títulos, mensagens) que aparece certo na
homologação e "desconfigurado" em produção. Exemplos do estrago que este módulo pega:
    "ConfiguraÃ§Ã£o"   "Configura??o"   "Configura�o"        (acentuacao: ignorar)
Ele encontra, só olhando os arquivos (sem servidor), as causas que nascem no código:

  1. arquivo salvo em Windows-1252/Latin-1 em vez de UTF-8;
  2. "mojibake": texto UTF-8 que já foi lido como Latin-1 e salvo de novo
     (o "ç" virou dois caracteres) — dá para desfazer automaticamente;
  3. acento já perdido ("?" ou U+FFFD no lugar da letra) — só redigitando;
  4. caractere fora do Latin-1 (aspas curvas do Word, travessão, reticências,
     emoji) em arquivo que vai para o Caché: servidor 8-bit pode trocar por "?";
  5. BOM UTF-8 no início do arquivo (caractere invisível que vai junto no envio);
  6. página CSP / classe %CSP.Page sem charset explícito: a codificação da saída
     fica dependendo do padrão de cada servidor (homologação ≠ produção).

Quem usa:
  - deploy.py (mesma pasta) importa este módulo e bloqueia o deploy se houver ERRO;
  - skill dev-commit-push roda a linha de comando abaixo nos arquivos do commit.

Falso positivo: uma linha que contenha o texto "acentuacao: ignorar" (em comentário)
é pulada na verificação e na correção automática.

Linha de comando (não precisa de servidor nem de .env):
  python acentuacao.py arq1.csp arq2.cls              -> verifica (código de saída 1 se houver ERRO)
  python acentuacao.py --corrigir arq1.csp            -> mostra o que seria corrigido, sem gravar
  python acentuacao.py --corrigir --aplicar arq1.csp  -> grava as correções automáticas
"""
import argparse
import codecs
import collections
import os
import re
import sys
import unicodedata

# Níveis dos achados: ERRO bloqueia o deploy; AVISO e INFO só informam.
ERRO, AVISO, INFO = "ERRO", "AVISO", "INFO"

# Um achado = um problema encontrado. linha=0 quando vale para o arquivo inteiro.
Achado = collections.namedtuple("Achado", "nivel linha mensagem trecho")

BOM_UTF8 = b"\xef\xbb\xbf"

# Linha com este texto é pulada (válvula de escape para falso positivo).
MARCADOR_IGNORAR = "acentuacao: ignorar"

# Extensões de fonte que vão para dentro do Caché/IRIS — só nelas faz sentido
# avisar de caractere fora do Latin-1 (servidor 8-bit não grava).
EXT_CACHE = {".cls", ".mac", ".inc", ".int", ".csp"}

# ---------------------------------------------------------------------------
# Padrões de detecção
# ---------------------------------------------------------------------------

# Caracteres que o Windows-1252 coloca na faixa 0x80–0x9F (onde o Latin-1 só tem
# controles invisíveis). Aparecem quando bytes UTF-8 são lidos como Windows-1252.
_CP1252_EXTRAS = "€‚ƒ„…†‡ˆ‰Š‹ŒŽ‘’“”•–—˜™š›œžŸ"
# Um "byte de continuação" UTF-8 (0x80–0xBF) depois de lido como Windows-1252/Latin-1.
_CONT = "[\u0080-\u00BF" + _CP1252_EXTRAS + "]"

# Mojibake típico de português: o "ç" (bytes C3 A7) lido como Latin-1 vira "Ã" + "§";
# o "º" (C2 BA) vira "Â" + "º"; o travessão (E2 80 93) vira "â" + "€" + "“".
# As letras-guia Ã, Â e â praticamente nunca aparecem seguidas desses caracteres
# em texto legítimo — por isso é ERRO. A mesma expressão desfaz o estrago
# (ver corrigir_mojibake).
RE_MOJIBAKE = re.compile("[ÃÂ]" + _CONT + "|â" + _CONT + "{2}")

# Controles C1 (U+0080–U+009F): invisíveis, só aparecem como resto de conversão errada.
RE_C1 = re.compile("[\u0080-\u009F]")

# Acento que virou "?": "Configura??o", "Usu?rio", "N?O".  (acentuacao: ignorar)
# Ignora query string de URL ("pagina.csp?id=1"). O pattern match do ObjectScript
# (x?1N, x?.A) não casa, porque depois do "?" vem dígito ou ponto. É só AVISO:
# ternário colado ("a?b:c") também casa.  (acentuacao: ignorar)
RE_INTERROGACAO = re.compile(r"[A-Za-zÀ-ÿ]\?{1,3}(?![A-Za-z_]\w*=)[A-Za-zÀ-ÿ]")

# "Palavra" para comparar enviado x devolvido pelo servidor: letras/dígitos e
# qualquer caractere não-ASCII (assim aspas curvas, travessões etc. também contam).
RE_PALAVRA = re.compile(r"(?:\w|[^\x00-\x7F])+")

# Charset declarado na página CSP (<csp:content charset> ou %response.CharSet) e no <meta>.
RE_CSP_CHARSET = re.compile(
    r"<csp:content\b[^>]*\bcharset\s*=\s*[\"']?([\w-]+)|%response\.CharSet\s*=\s*\"([\w-]+)\"", re.I)
RE_META_CHARSET = re.compile(r"<meta\b[^>]*\bcharset\s*=\s*[\"']?([\w-]+)", re.I)

# Classe que herda direto de %CSP.Page (ou página ZEN) gera HTML e deveria declarar CHARSET.
RE_CLASSE_PAGINA = re.compile(
    r"^Class\s+\S+\s+Extends\s+\(?[^{\[]*?(%CSP\.Page|%ZEN\.Component\.page)\b", re.I | re.M)
RE_PARAM_CHARSET = re.compile(r"^Parameter\s+CHARSET\b", re.I | re.M)

# Sugestão de troca para os caracteres fora do Latin-1 mais comuns (vêm do Word/WhatsApp).
SUGESTOES = {
    "“": '" ou &ldquo;', "”": '" ou &rdquo;', "‘": "' ou &lsquo;", "’": "' ou &rsquo;",
    "–": "- ou &ndash;", "—": "- ou &mdash;", "…": "... ou &hellip;", "•": "- ou &bull;",
    "€": "&euro;", "™": "&trade;", "​": "remover (espaço invisível)",
    " ": "remover (quebra de linha Unicode)", " ": "remover (quebra de parágrafo Unicode)",
}


# ---------------------------------------------------------------------------
# Tratadores de codec: os 5 bytes que o Windows-1252 não define (81 8D 8F 90 9D)
# viram os controles C1 de mesmo número, como faria uma leitura em Latin-1.
# ---------------------------------------------------------------------------

def _le_como_latin1(erro):
    return erro.object[erro.start:erro.end].decode("latin-1"), erro.end


def _grava_como_latin1(erro):
    trecho = erro.object[erro.start:erro.end]
    if all(ord(c) < 0x100 for c in trecho):
        return trecho.encode("latin-1"), erro.end
    raise erro


codecs.register_error("acentuacao_le_latin1", _le_como_latin1)
codecs.register_error("acentuacao_grava_latin1", _grava_como_latin1)


def console_utf8():
    """Força saída UTF-8 no console. No Windows o padrão é cp1252: os acentos saem
    trocados e alguns caracteres (ex.: U+FFFD) derrubam o script com UnicodeEncodeError."""
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Leitura do arquivo
# ---------------------------------------------------------------------------

def decodificar(dados):
    """Converte os bytes do arquivo em texto UTF-8 (sem BOM).

    Devolve (texto, achados). texto é None quando o arquivo NÃO é UTF-8 válido —
    nesse caso os achados apontam as linhas problemáticas.
    """
    achados = []
    if dados.startswith(BOM_UTF8):
        achados.append(Achado(AVISO, 1, "arquivo começa com BOM UTF-8 (caractere invisível) — padrão é UTF-8 "
                                        "sem BOM; o deploy remove sozinho e --corrigir tira do arquivo", ""))
        dados = dados[len(BOM_UTF8):]
    try:
        return dados.decode("utf-8"), achados
    except UnicodeDecodeError:
        pass
    # Não é UTF-8: aponta linha a linha (uma sequência UTF-8 nunca atravessa o \n).
    for n, bruta in enumerate(dados.split(b"\n"), 1):
        try:
            bruta.decode("utf-8")
        except UnicodeDecodeError:
            achados.append(Achado(ERRO, n, "linha fora de UTF-8 (arquivo salvo como Windows-1252/Latin-1) — "
                                           "converter com --corrigir", _resumir(_de_1252(bruta))))
    return None, achados


def linhas(texto):
    """Quebra o texto em linhas só em \\n, \\r\\n ou \\r.

    str.splitlines() também quebra em U+0085, U+2028, \\x0c etc. — usar ele no envio
    ao servidor alteraria o conteúdo do arquivo quando esses caracteres aparecem.
    """
    partes = texto.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if partes and partes[-1] == "":
        partes.pop()  # \n final do arquivo não é uma linha a mais
    return partes


def _de_1252(bruta):
    return bruta.decode("cp1252", errors="acentuacao_le_latin1")


# ---------------------------------------------------------------------------
# Análise
# ---------------------------------------------------------------------------

def analisar_linhas(lista, unicode_servidor=None, checar_latin1=True):
    """Procura problemas de acentuação linha a linha. Devolve lista de Achado.

    unicode_servidor: True/False se já se sabe se o servidor de destino é Unicode
    (decide se caractere fora do Latin-1 é só INFO ou AVISO); None = não se sabe.
    checar_latin1: False para arquivos que não vão para dentro do Caché.
    """
    achados = []
    for n, linha in enumerate(lista, 1):
        if MARCADOR_IGNORAR in linha:
            continue
        if "\ufffd" in linha:
            achados.append(Achado(ERRO, n, "acento já perdido: caractere '\ufffd' no lugar da letra — redigitar o "
                                           "texto (copiar da homologação)", _token(linha, linha.index("\ufffd"))))
        m = RE_MOJIBAKE.search(linha)
        if m:
            tok = _token(linha, m.start())
            achados.append(Achado(ERRO, n, "acentuação corrompida (UTF-8 lido como Latin-1, ex.: '\u00c3\u00a7' no "
                                           "lugar de 'ç') — corrigível com --corrigir",
                                  f"{tok}  →  {corrigir_mojibake(tok)}"))
        elif RE_C1.search(linha):
            achados.append(Achado(ERRO, n, "caractere de controle invisível (U+0080–U+009F), resto de conversão "
                                           "Windows-1252/Latin-1 — corrigível com --corrigir",
                                  f"{_resumir(_visivel(linha))}  →  {_resumir(corrigir_mojibake(linha))}"))
        m = RE_INTERROGACAO.search(linha)
        if m:
            achados.append(Achado(AVISO, n, "possível acento perdido (letra virou '?') — conferir com a homologação",
                                  _token(linha, m.start() + 1)))
        # Olha a linha já sem mojibake: os restos da corrupção (ex.: U+0192, U+20AC)
        # já foram apontados acima e somem com a correção.
        fora = sorted({c for c in corrigir_mojibake(linha) if ord(c) > 0xFF and c != "\ufffd"}) if checar_latin1 else []
        if fora:
            if unicode_servidor:
                nivel, msg = INFO, ("caractere fora do Latin-1 — servidor é Unicode e grava normalmente; só "
                                    "aparece errado se a página usar charset Latin-1")
            else:
                nivel, msg = AVISO, "caractere fora do Latin-1 — em servidor Caché 8-bit pode virar '?'"
            achados.append(Achado(nivel, n, msg, ", ".join(_descrever(c) for c in fora)))
    return achados


def analisar_charset(caminho, texto):
    """Confere se a página declara o charset de saída (CSP e classes %CSP.Page)."""
    ext = os.path.splitext(caminho)[1].lower()
    if ext == ".csp":
        csp = RE_CSP_CHARSET.search(texto)
        meta = RE_META_CHARSET.search(texto)
        if not csp and re.search(r"<html\b", texto, re.I):
            return [Achado(AVISO, 0, "página CSP sem charset explícito — incluir <csp:content charset=\"utf-8\"> "
                                     "(coerente com o <meta>) para a saída não depender do padrão do servidor, "
                                     "que pode ser diferente entre homologação e produção",
                           f"<meta> declara {meta.group(1)}" if meta else "")]
        if csp and meta:
            valor_csp = csp.group(1) or csp.group(2)
            if _norm_charset(valor_csp) != _norm_charset(meta.group(1)):
                return [Achado(AVISO, 0, "charset do <csp:content>/%response.CharSet diferente do <meta> — o "
                                         "navegador pode exibir os acentos errado",
                               f"csp: {valor_csp} | meta: {meta.group(1)}")]
    elif ext == ".cls":
        if RE_CLASSE_PAGINA.search(texto) and not RE_PARAM_CHARSET.search(texto):
            return [Achado(AVISO, 0, "classe de página (%CSP.Page/ZEN) sem Parameter CHARSET — incluir "
                                     "Parameter CHARSET = \"utf-8\"; para a saída não depender do padrão do servidor",
                           "")]
    return []


def analisar_arquivo(caminho, dados, unicode_servidor=None):
    """Análise completa de um arquivo (bytes lidos do disco). Devolve lista de Achado."""
    texto, achados = decodificar(dados)
    if texto is None:
        return achados  # sem texto válido não dá para analisar o resto
    vai_pro_cache = os.path.splitext(caminho)[1].lower() in EXT_CACHE
    return (achados
            + analisar_linhas(linhas(texto), unicode_servidor, checar_latin1=vai_pro_cache)
            + analisar_charset(caminho, texto))


def palavras_acentuadas(lista):
    """Conta as "palavras" que têm pelo menos um caractere não-ASCII.

    Comparar essa contagem entre o que foi enviado e o que o servidor devolveu
    mostra se algum acento foi trocado, sem se confundir com diferenças de
    formatação (espaços, quebras) que o servidor possa introduzir.
    """
    contagem = collections.Counter()
    for linha in lista:
        for palavra in RE_PALAVRA.findall(linha):
            if not palavra.isascii():
                contagem[palavra] += 1
    return contagem


def sem_acento(palavra):
    """'Usuário' -> 'Usuario', 'Ação' -> 'Acao' (decompõe e tira os sinais diacríticos)."""
    return "".join(c for c in unicodedata.normalize("NFD", palavra) if not unicodedata.combining(c))


def acentos_removidos(antes, depois):
    """Palavras acentuadas em `antes` que, em `depois`, aparecem só na forma sem acento.

    Ex.: produção tem "Usuário" e o arquivo local passou a ter "Usuario" no lugar —
    sinal de arquivo que perdeu a acentuação (nenhuma outra checagem pega isso,
    porque "Usuario" é ASCII puro). Devolve lista de (palavra_antes, palavra_depois).
    """
    def todas(lista):
        return collections.Counter(p for linha in lista for p in RE_PALAVRA.findall(linha))

    ta, td = todas(antes), todas(depois)
    trocas = []
    for palavra in palavras_acentuadas(antes) - palavras_acentuadas(depois):
        simples = sem_acento(palavra)
        if simples != palavra and td[simples] > ta[simples]:
            trocas.append((palavra, simples))
    return sorted(trocas)


def comparar(enviado, recebido):
    """Diferenças de acentuação entre as linhas enviadas e as devolvidas pelo servidor.

    Devolve lista de textos descrevendo o problema (vazia = acentos intactos).
    """
    pe, pr = palavras_acentuadas(enviado), palavras_acentuadas(recebido)
    problemas = []
    faltando, sobrando = pe - pr, pr - pe
    if faltando:
        problemas.append("enviadas e NÃO devolvidas iguais: " + _amostra(faltando))
    if sobrando:
        problemas.append("devolvidas pelo servidor de outro jeito: " + _amostra(sobrando))
    return problemas


# ---------------------------------------------------------------------------
# Correção automática (só o que dá para desfazer sem adivinhar)
# ---------------------------------------------------------------------------

def _desfaz_sequencia(m):
    """Volta os caracteres aos bytes originais (ex.: "Ã" + "§" -> C3 A7) e relê como
    UTF-8 ("ç"). Se os bytes não formarem UTF-8 válido, mantém como estava."""
    s = m.group(0)
    try:
        return s.encode("cp1252", errors="acentuacao_grava_latin1").decode("utf-8")
    except UnicodeError:
        return s


def _desfaz_c1(m):
    """Controle C1 solto (ex.: U+0093) era um byte Windows-1252 lido como Latin-1 (aspa curva)."""
    c = m.group(0)
    try:
        return bytes([ord(c)]).decode("cp1252")
    except UnicodeDecodeError:
        return c  # byte que nem o Windows-1252 define: fica para correção manual


def corrigir_mojibake(texto):
    """Desfaz o mojibake. Repete até 3 vezes porque o texto pode ter sido
    corrompido mais de uma vez (cada passada desfaz uma camada)."""
    for _ in range(3):
        novo = RE_C1.sub(_desfaz_c1, RE_MOJIBAKE.sub(_desfaz_sequencia, texto))
        if novo == texto:
            break
        texto = novo
    return texto


def corrigir_arquivo(dados):
    """Monta a versão corrigida dos bytes do arquivo: tira BOM, converte linhas
    Windows-1252 para UTF-8 e desfaz mojibake. Preserva as quebras de linha (CRLF/LF).

    Devolve (dados_novos, mudancas) — mudancas é lista de (linha, tipo, texto_final).
    """
    mudancas = []
    if dados.startswith(BOM_UTF8):
        dados = dados[len(BOM_UTF8):]
        mudancas.append((0, "BOM", "removido do início do arquivo"))
    saida = []
    for n, bruta in enumerate(dados.split(b"\n"), 1):
        try:
            linha, tipo = bruta.decode("utf-8"), None
        except UnicodeDecodeError:
            linha, tipo = _de_1252(bruta), "Windows-1252 → UTF-8"
        # Linha marcada para ignorar: só converte o encoding, não mexe no texto.
        nova = linha if MARCADOR_IGNORAR in linha else corrigir_mojibake(linha)
        if nova != linha:
            tipo = (tipo + " + " if tipo else "") + f"mojibake: {_resumir(_visivel(linha))}  →"
        if tipo:
            mudancas.append((n, tipo, _resumir(nova)))
        saida.append(nova.encode("utf-8"))
    return b"\n".join(saida), mudancas


# ---------------------------------------------------------------------------
# Apresentação
# ---------------------------------------------------------------------------

def _resumir(texto, limite=110):
    texto = texto.strip()
    return texto if len(texto) <= limite else texto[:limite] + "…"


def _visivel(texto):
    """Troca controles C1 invisíveis por \\x93 etc., para aparecerem no relatório."""
    return RE_C1.sub(lambda m: f"\\x{ord(m.group(0)):02x}", texto)


def _token(linha, pos):
    """Palavra (até espaços) que contém a posição pos — mostra o problema em contexto curto."""
    ini = linha.rfind(" ", 0, pos) + 1
    fim = linha.find(" ", pos)
    return _resumir(linha[ini:fim if fim != -1 else len(linha)], 60)


def _descrever(c):
    nome = unicodedata.name(c, "sem nome").lower()
    visivel = c if c.isprintable() else ""
    sugestao = f" → {SUGESTOES[c]}" if c in SUGESTOES else ""
    return f"{visivel} U+{ord(c):04X} {nome}{sugestao}".strip()


def _amostra(contagem, limite=8):
    itens = [f"'{p}'" + (f" ×{q}" if q > 1 else "") for p, q in contagem.most_common(limite)]
    resto = len(contagem) - limite
    return ", ".join(itens) + (f" (+{resto})" if resto > 0 else "")


def _norm_charset(nome):
    """utf-8/UTF8 -> utf8; iso-8859-1/latin1/windows-1252 -> latin1 (navegador trata igual)."""
    n = nome.lower().replace("-", "").replace("_", "")
    return "latin1" if n in ("iso88591", "latin1", "l1", "cp1252", "windows1252") else n


def resumo(achados):
    """Contagem por nível, ex.: {'ERRO': 2, 'AVISO': 1}."""
    return collections.Counter(a.nivel for a in achados)


def formatar(nome, achados, limite=5):
    """Texto do relatório de um arquivo, agrupando achados iguais (máx. `limite` linhas cada)."""
    if not achados:
        return f"  ok    {nome}"
    ordem = {ERRO: 0, AVISO: 1, INFO: 2}
    grupos = {}
    for a in sorted(achados, key=lambda a: (ordem[a.nivel], a.linha)):
        grupos.setdefault((a.nivel, a.mensagem), []).append(a)
    saida = [f"  {nome}"]
    for (nivel, msg), lista in grupos.items():
        saida.append(f"    [{nivel}] {msg}")
        for a in lista[:limite]:
            if a.linha or a.trecho:
                onde = f"linha {a.linha}" if a.linha else "arquivo"
                saida.append(f"        {onde}: {a.trecho}" if a.trecho else f"        {onde}")
        if len(lista) > limite:
            saida.append(f"        (+{len(lista) - limite} linha(s) com o mesmo problema)")
    return "\n".join(saida)


# ---------------------------------------------------------------------------
# Linha de comando
# ---------------------------------------------------------------------------

def main():
    console_utf8()
    p = argparse.ArgumentParser(description="Verifica/corrige acentuação e encoding de arquivos de código")
    p.add_argument("arquivos", nargs="+", help="arquivos a verificar")
    p.add_argument("--corrigir", action="store_true", help="mostra as correções automáticas possíveis (não grava)")
    p.add_argument("--aplicar", action="store_true", help="junto com --corrigir: grava as correções nos arquivos")
    a = p.parse_args()
    if a.aplicar and not a.corrigir:
        p.error("--aplicar só vale junto com --corrigir")

    total = collections.Counter()
    for caminho in a.arquivos:
        if not os.path.isfile(caminho):
            print(f"  [ERRO] {caminho}: arquivo não encontrado")
            total[ERRO] += 1
            continue
        with open(caminho, "rb") as f:
            dados = f.read()
        if b"\x00" in dados:
            print(f"  --    {caminho} (binário — ignorado)")
            continue

        if not a.corrigir:
            achados = analisar_arquivo(caminho, dados)
            total.update(resumo(achados))
            print(formatar(caminho, achados))
            continue

        novos, mudancas = corrigir_arquivo(dados)
        if not mudancas:
            print(f"  ok    {caminho}: nada a corrigir automaticamente")
        else:
            estado = "APLICADA(S)" if a.aplicar else "(prévia, nada gravado)"
            print(f"  {caminho}: {len(mudancas)} correção(ões) {estado}")
            for n, tipo, final in mudancas:
                print(f"        {'linha ' + str(n) if n else 'arquivo'} [{tipo}] {final}")
            if a.aplicar:
                with open(caminho, "wb") as f:
                    f.write(novos)
        # O que sobra depois da correção automática precisa de mão humana (U+FFFD, '?').
        restantes = [x for x in analisar_arquivo(caminho, novos) if x.nivel == ERRO]
        if restantes:
            print(formatar(caminho + " — precisa correção manual", restantes))
            total[ERRO] += len(restantes)

    print(f"\nResumo: {total[ERRO]} erro(s), {total[AVISO]} aviso(s), {total[INFO]} informação(ões)")
    sys.exit(1 if total[ERRO] else 0)


if __name__ == "__main__":
    main()
