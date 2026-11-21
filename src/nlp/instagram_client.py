# -*- coding: utf-8 -*-
"""Cliente da Instagram Graph API oficial (Meta) para coleta de comentários do
perfil público do HUOL/UFRN (https://www.instagram.com/huol_ufrn/).

IMPORTANTE (transparência metodológica):
  - A coleta exige credenciais legítimas: aplicativo aprovado no Meta for
    Developers com as permissões instagram_basic / instagram_manage_comments
    (ou Business Login for Instagram) e um token de acesso válido.
  - Sem credenciais autorizadas, este módulo NÃO inventa comentários: apenas
    documenta a limitação e mantém o pipeline pronto para receber os dados.
  - Formato de entrada/saída: DataFrame com colunas
        id_comentario, texto, data, autor (opcional), curtidas, id_publicacao

Uso:
    from src.nlp.instagram_client import InstagramClient
    cliente = InstagramClient()          # lê IG_ACCESS_TOKEN / IG_USER_ID do .env
    df = cliente.coletar_comentarios()   # DataFrame vazio + diagnóstico se sem token
"""
from __future__ import annotations

import logging
import time

import pandas as pd
import requests

from ..utils import config

log = logging.getLogger(__name__)

BASE_URL = "https://graph.facebook.com"

CAMPOS_COMENTARIOS = "id,text,timestamp,username,like_count"
CAMPOS_MIDIAS = "id,caption,timestamp,media_type,permalink"


class InstagramClient:
    def __init__(self, token: str = "", user_id: str = "", api_version: str = "") -> None:
        self.token = token or config.IG_ACCESS_TOKEN
        self.user_id = user_id or config.IG_USER_ID
        self.api_version = api_version or config.IG_API_VERSION
        self.diagnostico: list[str] = []

    @property
    def configurado(self) -> bool:
        return bool(self.token and self.user_id)

    def _get(self, path: str, params: dict) -> dict:
        url = f"{BASE_URL}/{self.api_version}/{path}"
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def listar_midias(self, limite_paginas: int = 10) -> list[dict]:
        """Lista publicações do perfil (campos oficiais da Graph API)."""
        if not self.configurado:
            self.diagnostico.append("IG_ACCESS_TOKEN / IG_USER_ID não configurados")
            return []
        registros: list[dict] = []
        params = {"fields": CAMPOS_MIDIAS, "limit": 25, "access_token": self.token}
        for _ in range(limite_paginas):
            data = self._get(f"{self.user_id}/media", params)
            registros.extend(data.get("data", []))
            next_url = data.get("paging", {}).get("next")
            if not next_url:
                break
            time.sleep(0.5)  # cortesia com limites de taxa
        return registros

    def coletar_comentarios(self, limite_paginas: int = 10) -> pd.DataFrame:
        """Coleta comentários das publicações do perfil.

        Respeita permissões, autenticação e limites da plataforma. Sem acesso
        autorizado, devolve DataFrame vazio com diagnóstico documentado —
        nunca gera dados fictícios.
        """
        if not self.configurado:
            log.warning(
                "Instagram Graph API não configurada (IG_ACCESS_TOKEN/IG_USER_ID). "
                "Nenhum comentário será coletado — módulo permanece pronto."
            )
            return pd.DataFrame(
                columns=["id_comentario", "texto", "data", "autor", "curtidas", "id_publicacao"]
            )

        linhas = []
        try:
            for midia in self.listar_midias(limite_paginas):
                data = self._get(
                    f"{midia['id']}/comments",
                    {"fields": CAMPOS_COMENTARIOS, "limit": 50, "access_token": self.token},
                )
                for c in data.get("data", []):
                    linhas.append({
                        "id_comentario": c.get("id"),
                        "texto": c.get("text", ""),
                        "data": c.get("timestamp"),
                        "autor": c.get("username"),
                        "curtidas": c.get("like_count", 0),
                        "id_publicacao": midia["id"],
                    })
        except requests.RequestException as exc:
            self.diagnostico.append(f"Falha na API: {exc}")
            log.error("Erro na Instagram Graph API: %s", exc)

        df = pd.DataFrame(
            linhas,
            columns=["id_comentario", "texto", "data", "autor", "curtidas", "id_publicacao"],
        )
        log.info("Comentários coletados: %d", len(df))
        return df
