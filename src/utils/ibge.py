# -*- coding: utf-8 -*-
"""Validação de municípios contra a base oficial do IBGE.

Referência: API de Localidades do IBGE (servicodados.ibge.gov.br).
Os arquivos JSON em data/reference/ foram obtidos em:
  - municipios_brasil_ibge.json : /api/v1/localidades/municipios (5.571 registros)
  - municipios_rn_ibge.json     : /api/v1/localidades/estados/24/municipios (167 registros)

Regras de correspondência (documentadas no relatório de qualidade):
  1. Normalização ASCII (NFKD + uppercase) e remoção de pontuação (hífens,
     apóstrofos) — resolve diferenças como "OLHO-D'ÁGUA" x "Olho d'Água".
  2. Correspondência exata contra a lista nacional. Nomes únicos no país recebem
     código IBGE + UF. Nomes repetidos em múltiplos estados ficam AMBÍGUOS e
     NÃO recebem atribuição automática.
  3. Correspondências históricas documentadas (renomeações oficiais e variantes
     de grafia oficiais) são aplicadas ANTES da busca, com registro em
     HISTORICOS abaixo.
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from . import config


def normalizar(texto: str) -> str:
    """Uppercase + remoção de acentos + remoção de pontuação + colapso de espaços."""
    t = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    t = t.upper().strip()
    t = re.sub(r"[-'`’´.]", " ", t)
    t = re.sub(r"\s+", " ", t)
    return t


@dataclass(frozen=True)
class Municipio:
    nome: str
    codigo_ibge: str | None
    uf: str | None
    classe: str          # RN | OUTROS_ESTADOS | AMBIGUO | SEM_CORRESPONDENCIA | NAO_INFORMADO
    observacao: str = ""


# Correspondências históricas/variantes oficiais documentadas
# (ver docs/relatorio_qualidade.md, seção "Municípios").
# Chave = normalização do valor na fonte; valor = nome IBGE alvo.
HISTORICOS = {
    # Grafia oficial IBGE "Assú" — a fonte usa "Açu"/"ACU" para o mesmo município
    "ACU": "Assú",
    # Renomeação: São Miguel de Touros -> São Miguel do Gostoso (RN)
    "SAO MIGUEL DE TOUROS": "São Miguel do Gostoso",
    # Renomeação: Augusto Severo -> Campo Grande (RN), plebiscito de 1991
    "AUGUSTO SEVERO": "Campo Grande",
    # IBGE 2405306 "Januário Cicco" — município atualmente denominado Boa Saúde (RN)
    "BOA SAUDE": "Januário Cicco",
}

NAO_INFORMADO = "NÃO INFORMADO"

# Código IBGE (2 primeiros dígitos do id) -> sigla da UF (fonte oficial IBGE)
UF_POR_CODIGO = {
    "11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO",
    "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB", "26": "PE", "27": "AL",
    "28": "SE", "29": "BA", "31": "MG", "32": "ES", "33": "RJ", "35": "SP", "41": "PR",
    "42": "SC", "43": "RS", "50": "MS", "51": "MT", "52": "GO", "53": "DF",
}


class ValidadorIBGE:
    def __init__(self) -> None:
        br_path = config.REFERENCE_DIR / "municipios_brasil_ibge.json"
        if not br_path.exists():
            raise FileNotFoundError(
                "Base IBGE ausente: execute scripts/baixar_referencia_ibge.py"
            )
        municipios = json.loads(br_path.read_text(encoding="utf-8"))

        self._por_uf: dict[str, dict[str, dict]] = {}
        self._nacional: dict[str, list[dict]] = {}
        for m in municipios:
            uf = self._uf(m)
            nome = m["nome"]
            entry = {"nome": nome, "codigo": str(m["id"]), "uf": uf}
            self._por_uf.setdefault(uf, {}).setdefault(nome, entry)
            self._nacional.setdefault(normalizar(nome), []).append(entry)

    @staticmethod
    def _uf(municipio: dict) -> str:
        try:
            return municipio["regiao-imediata"]["regiao-geografica-intermediaria"]["UF"]["sigla"]
        except (KeyError, TypeError):
            try:
                return municipio["microrregiao"]["mesorregiao"]["UF"]["sigla"]
            except (KeyError, TypeError):
                # fallback determinístico: 2 primeiros dígitos do código IBGE
                return UF_POR_CODIGO.get(str(municipio["id"])[:2], "")

    def resolver(self, nome_fonte: str) -> Municipio:
        original = str(nome_fonte).strip()
        if not original or normalizar(original) == "":
            return Municipio(NAO_INFORMADO.title(), None, None, "NAO_INFORMADO",
                             "Campo vazio na fonte")
        chave = normalizar(original)
        if chave == "NAO INFORMADO":
            return Municipio(NAO_INFORMADO.title(), None, None, "NAO_INFORMADO",
                             "Valor literal 'Não Informado' na fonte")

        alvo = HISTORICOS.get(chave)
        if alvo:
            chave = normalizar(alvo)

        candidatos = self._nacional.get(chave, [])
        if not candidatos:
            return Municipio(original, None, None, "SEM_CORRESPONDENCIA",
                             "Sem correspondência exata na base IBGE nacional")
        if alvo:
            # correspondência histórica documentada
            rn = [c for c in candidatos if c["uf"] == "RN"] or candidatos
            c = rn[0]
            return Municipio(c["nome"], c["codigo"], c["uf"], "RN" if c["uf"] == "RN" else "OUTROS_ESTADOS",
                             f"Correspondência histórica documentada: '{original}' -> {c['nome']}")
        if len(candidatos) == 1:
            c = candidatos[0]
            classe = "RN" if c["uf"] == "RN" else "OUTROS_ESTADOS"
            return Municipio(c["nome"], c["codigo"], c["uf"], classe)
        # Nome existe em múltiplos estados: por regra, NÃO há atribuição
        # automática. EXCEÇÃO DOCUMENTADA: quando exatamente um candidato
        # pertence ao RN (estado do hospital estudado), atribui-se ao RN com
        # observação explícita — caso de 'Parnamirim' (RN 2403251 / PE 2610400).
        # As demais ambiguidades permanecem não atribuídas.
        no_rn = [c for c in candidatos if c["uf"] == "RN"]
        if len(no_rn) == 1:
            c = no_rn[0]
            return Municipio(c["nome"], c["codigo"], c["uf"], "RN",
                             f"Ambíguo nacionalmente ({', '.join(sorted(set(x['uf'] for x in candidatos)))}); "
                             f"atribuído ao RN — único candidato no estado do hospital")
        return Municipio(original, None, None, "AMBIGUO",
                         "Nome existente em mais de um estado; não atribuído automaticamente")


# ------------------------------------------------------------------ UF/Regiões
REGIAO_UF = {
    "N": ["AC", "AP", "AM", "PA", "RO", "RR", "TO"],
    "NE": ["AL", "BA", "CE", "MA", "PB", "PE", "PI", "RN", "SE"],
    "CO": ["DF", "GO", "MS", "MT"],
    "SE": ["ES", "MG", "RJ", "SP"],
    "S": ["PR", "RS", "SC"],
}


def classificacao_geografica(nome_padronizado: str, classe: str, uf: str | None) -> str:
    """Classificação usada nas análises geográficas (documentada, sem inferências)."""
    if classe == "NAO_INFORMADO":
        return "Não informado"
    if classe == "SEM_CORRESPONDENCIA":
        return "Sem correspondência IBGE"
    if classe == "AMBIGUO":
        return "Ambíguo entre estados"
    if uf == "RN":
        return "Natal" if normalizar(nome_padronizado) == "NATAL" else "Interior RN"
    return "Outros estados"
