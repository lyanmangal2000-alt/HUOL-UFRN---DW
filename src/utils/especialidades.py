# -*- coding: utf-8 -*-
"""Padronização de especialidades hospitalares.

A base possui 49 especialidades distintas, todas em maiúsculas, com acentuação
inconsistente entre arquivos (ex.: "HEMATOLOGIA PEDIATRICA" x "HEMATOLOGIA
PEDIÁTRICA"). A auditoria comprovou que NÃO há colisões após normalização de
case/acento — ou seja, cada chave ASCII identifica uma única especialidade.

Aqui padronizamos:
  1. chave técnica = normalização ASCII (case/acento/pontuação ignorados);
  2. nome padrão = forma com acentuação correta em português e capitalização
     título, mantendo a semântica da fonte (nenhuma especialidade é mesclada
     ou desmembrada).

Qualquer especialidade nova (não mapeada) entra no padrão por fallback
(title-case preservando os acentos da fonte) e é sinalizada no relatório de
qualidade, evitando perda silenciosa de informação.
"""
from __future__ import annotations

import re
import unicodedata

# chave ASCII -> nome padrão com acentuação correta
ESPECIALIDADES_PADRAO = {
    "ALERGOLOGIA PEDIATRICA": "Alergologia Pediátrica",
    "CARDIOLOGIA": "Cardiologia",
    "CARDIOLOGIA PEDIATRICA": "Cardiologia Pediátrica",
    "CIRURGIA BARIATRICA": "Cirurgia Bariátrica",
    "CIRURGIA CARDIACA": "Cirurgia Cardíaca",
    "CIRURGIA CARDIOVASCULAR": "Cirurgia Cardiovascular",
    "CIRURGIA DE CABECA E PESCOCO": "Cirurgia de Cabeça e Pescoço",
    "CIRURGIA DO APARELHO DIGESTIVO": "Cirurgia do Aparelho Digestivo",
    "CIRURGIA GERAL": "Cirurgia Geral",
    "CIRURGIA ONCOLOGICA": "Cirurgia Oncológica",
    "CIRURGIA PEDIATRICA GERAL": "Cirurgia Pediátrica Geral",
    "CIRURGIA PLASTICA": "Cirurgia Plástica",
    "CIRURGIA TORACICA": "Cirurgia Torácica",
    "CIRURGIA VASCULAR": "Cirurgia Vascular",
    "CLINICA GERAL": "Clínica Geral",
    "DERMATOLOGIA": "Dermatologia",
    "ENDOCRINOLOGIA": "Endocrinologia",
    "ENDOCRINOLOGIA PEDIATRICA": "Endocrinologia Pediátrica",
    "GASTROENTEROLOGIA": "Gastroenterologia",
    "GASTROENTEROLOGIA PEDIATRICA": "Gastroenterologia Pediátrica",
    "GERIATRIA": "Geriatria",
    "HEMATOLOGIA": "Hematologia",
    "HEMATOLOGIA PEDIATRICA": "Hematologia Pediátrica",
    "INFECTOLOGIA PEDIATRICA": "Infectologia Pediátrica",
    "MASTOLOGIA": "Mastologia",
    "MEDICINA INTENSIVA": "Medicina Intensiva",
    "MEDICINA INTERVENCIONISTA": "Medicina Intervencionista",
    "NEFROLOGIA": "Nefrologia",
    "NEFROLOGIA PEDIATRICA": "Nefrologia Pediátrica",
    "NEUROCIRURGIA": "Neurocirurgia",
    "NEUROLOGIA": "Neurologia",
    "NEUROLOGIA PEDIATRICA": "Neurologia Pediátrica",
    "ODONTOLOGIA CLINICA": "Odontologia Clínica",
    "ODONTOLOGIA CIRURGIA BUCOMAXILO FACIAL": "Odontologia — Cirurgia Bucomaxilofacial",
    "OFTALMOLOGIA": "Oftalmologia",
    "ONCO HEMATOLOGIA PEDIATRICO": "Oncologia Hematologia Pediátrica",
    "ONCOLOGIA CLINICA": "Oncologia Clínica",
    "ONCOLOGIA HEMATOLOGIA": "Oncologia Hematologia",
    "OTORRINOLARINGOLOGIA": "Otorrinolaringologia",
    "PEDIATRIA": "Pediatria",
    "PSIQUIATRIA PEDIATRICA": "Psiquiatria Pediátrica",
    "PNEUMOLOGIA": "Pneumologia",
    "PNEUMOLOGIA PEDIATRICA": "Pneumologia Pediátrica",
    "POS TRANSPLANTE": "Pós-Transplante",
    "PRE TRANSPLANTE": "Pré-Transplante",
    "PROCTOLOGIA": "Proctologia",
    "PSIQUIATRIA": "Psiquiatria",
    "PSIQUIATRIA PEDIATRICA": "Psiquiatria Pediátrica",
    "REUMATOLOGIA": "Reumatologia",
    "REUMATOLOGIA PEDIATRICA": "Reumatologia Pediátrica",
    "UROLOGIA": "Urologia",
}

NOME_PADRAO_POR_CHAVE = {k.upper(): v for k, v in ESPECIALIDADES_PADRAO.items()}


def chave_ascii(texto: str) -> str:
    t = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    t = re.sub(r"[-'`’´.]", " ", t).upper()
    return re.sub(r"\s+", " ", t).strip()


def padronizar_especialidade(valor: str) -> tuple[str, bool]:
    """Retorna (nome_padronizado, usou_fallback).

    Fallback: quando a especialidade não está no mapa, retorna o valor em
    Title Case preservando os acentos da fonte e sinaliza para auditoria.
    """
    original = str(valor).strip()
    if not original:
        return "NÃO INFORMADO", False
    chave = chave_ascii(original)
    if chave in NOME_PADRAO_POR_CHAVE:
        return NOME_PADRAO_POR_CHAVE[chave], False
    fallback = re.sub(r"\s+", " ", original).title()
    return fallback, True
