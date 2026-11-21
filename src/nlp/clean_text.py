# -*- coding: utf-8 -*-
"""Limpeza textual de comentários (LGPD: o texto original é sempre preservado
em coluna própria para auditoria).

Etapas:
  1. remoção de URLs;
  2. remoção de menções (@usuario);
  3. tratamento de emojis (remoção, com registro de contagem);
  4. tratamento de hashtags (mantém o termo, remove o '#');
  5. normalização de espaços;
  6. caixa baixa;
  7. remoção de pontuação;
  8. tokenização e remoção de stopwords em português;
  9. lematização com spaCy (pt_core_news_sm) quando disponível — fallback
     para a forma canônica sem lematização.
"""
from __future__ import annotations

import logging
import re
import unicodedata

log = logging.getLogger(__name__)

STOPWORDS_PT = {
    "a", "à", "ao", "aos", "aquela", "aquele", "aquilo", "as", "às", "com", "como",
    "da", "das", "de", "dela", "dele", "deles", "dela", "do", "dos", "e", "ela",
    "ele", "em", "eu", "isso", "isto", "já", "lhe", "lhes", "mais", "mas", "me",
    "meu", "minha", "muito", "na", "não", "nas", "no", "nos", "nós", "o", "os",
    "ou", "para", "pela", "pelo", "por", "que", "quem", "se", "sem", "ser", "seu",
    "sua", "só", "também", "tão", "tem", "um", "uma", "us", "vocês", "voce", "você",
    "vc", "vcs", "ser", "estar", "tá", "ta", "né", "pq", "pra", "pro", "i", "eh",
}

RE_URL = re.compile(r"https?://\S+|www\.\S+")
RE_MENCAO = re.compile(r"@\w+")
RE_EMOJI = re.compile(
    "[\U0001F300-\U0001F9FF\U00002600-\U000027BF\U0001FA70-\U0001FAFF"
    "\U00002700-\U000027BF\U0001F000-\U0001F02F\U0000FE0F\U0000200D]"
)
RE_HASHTAG = re.compile(r"#(\w+)")
RE_PONTUACAO = re.compile(r"[^\w\sáàâãéêíóôõúüç]")

_nlp_pt = None
_nlp_tentado = False


def _obter_spacy():
    """Carrega pt_core_news_sm sob demanda (sem falhar se indisponível)."""
    global _nlp_pt, _nlp_tentado
    if _nlp_tentado:
        return _nlp_pt
    _nlp_tentado = True
    try:
        import spacy  # noqa: PLC0415

        _nlp_pt = spacy.load("pt_core_news_sm", disable=["parser", "ner"])
        log.info("spaCy pt_core_news_sm carregado (lematização ativa)")
    except Exception as exc:  # modelo não baixado / spaCy ausente
        log.warning("Lematização indisponível (%s) — seguindo sem lematização", exc)
        _nlp_pt = None
    return _nlp_pt


def contar_emojis(texto: str) -> int:
    return len(RE_EMOJI.findall(texto))


def limpar_texto(texto: str, remover_stopwords: bool = True,
                 lematizar: bool = True) -> str:
    """Aplica as etapas de limpeza e devolve o texto pronto para modelagem."""
    t = str(texto)
    t = RE_URL.sub(" ", t)
    t = RE_MENCAO.sub(" ", t)
    t = RE_EMOJI.sub(" ", t)
    t = RE_HASHTAG.sub(r"\1", t)          # mantém o termo da hashtag
    t = unicodedata.normalize("NFC", t)
    t = t.lower()
    t = RE_PONTUACAO.sub(" ", t)
    t = re.sub(r"\d+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()

    tokens = [tk for tk in t.split() if len(tk) > 2]
    if remover_stopwords:
        tokens = [tk for tk in tokens if tk not in STOPWORDS_PT]

    resultado = " ".join(tokens)
    if lematizar:
        nlp = _obter_spacy()
        if nlp is not None and resultado:
            doc = nlp(resultado)
            resultado = " ".join(
                tk.lemma_ for tk in doc if not tk.is_space
            )
    return resultado
