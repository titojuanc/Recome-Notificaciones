"""Plantilla HTML de los mails de RecoMe.

El emisor manda el contenido ya resuelto (título, cuerpo en texto y, opcionalmente,
un dato destacado como un código de verificación); acá solo se le da formato.
Los estilos van en línea porque muchos clientes de correo ignoran `<style>`.
Colores de la paleta «Etiqueta de alquiler» del frontend.
"""
from __future__ import annotations

import html

from src.models.mensaje import Contenido

_FONDO = "#eceae6"
_TARJETA = "#ffffff"
_TINTA = "#1e1b19"
_PAPEL = "#f2eee8"
_TENUE = "#5e5750"
_BORDE = "#d8d3cc"
_ACENTO = "#ff7a1a"
_FUENTE = "'Helvetica Neue', Helvetica, Arial, sans-serif"
_TABLA = 'role="presentation" width="100%" cellspacing="0" cellpadding="0"'

_P = f"margin:0 0 16px;font-size:16px;line-height:1.55;color:{_TINTA};"
_CAJA = (
    f"display:inline-block;padding:14px 28px;border:2px solid {_ACENTO};"
    f"border-radius:8px;background:{_FONDO};"
    "font-family:'Courier New',Courier,monospace;"
    f"font-size:32px;font-weight:700;letter-spacing:8px;color:{_TINTA};"
)
_TARJETA_CSS = (
    f"max-width:560px;background:{_TARJETA};border:1px solid {_BORDE};"
    f"border-radius:12px;overflow:hidden;font-family:{_FUENTE};"
)
_CABECERA = f"background:{_TINTA};padding:18px 28px;border-bottom:4px solid {_ACENTO};"
_MARCA = f"font-size:22px;font-weight:800;letter-spacing:1px;color:{_PAPEL};"
_H1 = f"margin:0 0 20px;font-size:22px;line-height:1.3;color:{_TINTA};"
_PIE = (
    f"padding:16px 28px 24px;border-top:1px solid {_BORDE};"
    f"font-size:12px;line-height:1.5;color:{_TENUE};"
)
_NOTA_PIE = "Este mail lo mandó RecoMe automáticamente; no hace falta responderlo."


def _bloques(contenido: Contenido) -> list[str]:
    """Párrafos del cuerpo (separados por línea en blanco) con el destacado, si hay,
    ubicado después del primero: el dato queda junto a la frase que lo presenta."""
    cuerpo = contenido.cuerpo.replace("\r\n", "\n").split("\n\n")
    bloques = [b.strip() for b in cuerpo if b.strip()]
    if contenido.destacado:
        bloques.insert(min(1, len(bloques)), None)
    return bloques


def texto_plano(contenido: Contenido) -> str:
    """Versión de texto del mail (clientes sin HTML y filtros de spam)."""
    partes = [contenido.destacado if b is None else b for b in _bloques(contenido)]
    return "\n\n".join([*partes, "— RecoMe"]) + "\n"


def _html_bloque(bloque: str | None, destacado: str | None) -> str:
    if bloque is None:
        return (
            '<p style="margin:8px 0 24px;text-align:center;">'
            f'<span style="{_CAJA}">{html.escape(destacado)}</span></p>'
        )
    return f'<p style="{_P}">{html.escape(bloque).replace(chr(10), "<br>")}</p>'


def html_mail(contenido: Contenido) -> str:
    titulo = html.escape(contenido.titulo)
    cuerpo = "".join(_html_bloque(b, contenido.destacado) for b in _bloques(contenido))
    return "\n".join([
        "<!DOCTYPE html>",
        '<html lang="es">',
        '<head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{titulo}</title></head>",
        f'<body style="margin:0;padding:0;background:{_FONDO};">',
        f'<table {_TABLA} style="background:{_FONDO};padding:32px 12px;">',
        '<tr><td align="center">',
        f'<table {_TABLA} style="{_TARJETA_CSS}">',
        f'<tr><td style="{_CABECERA}">',
        f'<span style="{_MARCA}">Reco<span style="color:{_ACENTO};">Me</span></span>',
        "</td></tr>",
        '<tr><td style="padding:28px 28px 12px;">',
        f'<h1 style="{_H1}">{titulo}</h1>',
        cuerpo,
        "</td></tr>",
        f'<tr><td style="{_PIE}">{_NOTA_PIE}</td></tr>',
        "</table>",
        "</td></tr>",
        "</table>",
        "</body>",
        "</html>",
        "",
    ])
