"""Modelo interno: ResultadoEnvio. Ver data-model.md §2."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ResultadoEnvio(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id_mensaje: int
    estado: Literal["exitoso", "fallo_transitorio", "fallo_definitivo"]
    canal: Literal["push", "mail"]
    detalle: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
