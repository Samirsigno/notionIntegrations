import os
import re
import time
from typing import Any, cast

from notion_client import Client
from notion_client.errors import APIResponseError

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
notion = Client(auth=NOTION_TOKEN)

LIMITE_CARACTERES_NOTION = 2000
LIMITE_RICH_TEXT_ITEMS = 100

PATRON_COMANDO = re.compile(
    r"^(\s*(git|ls|cd|mkdir|touch|rm|cat|echo|pwd|npm|npx|pip|python|python3|docker)\b"
    r"|[AM\?\!]{1,2}\s+\S+"
    r"|Ada Lovelace$"
    r"|On branch \S+"
    r"|nothing to commit.*)"
)
PATRON_LISTA = re.compile(r"^(\-|\*|\d+\.)\s+")
PATRON_INLINE_CODE = re.compile(
    r"((?<!\w)\.git/?|\bgit\s+[a-z\-]+(?:\s+--[a-z\-]+)*|\b[a-zA-Z0-9_\-]+\.(?:txt|md|py|yml|json)\b)"
)


def es_linea_codigo(linea: str) -> bool:
    return bool(PATRON_COMANDO.match(linea))


def es_lista(linea: str) -> bool:
    return bool(PATRON_LISTA.match(linea))


def dividir_en_fragmentos(
    texto: str, max_len: int = LIMITE_CARACTERES_NOTION
) -> list[str]:
    if len(texto) <= max_len:
        return [texto]
    return [texto[i : i + max_len] for i in range(0, len(texto), max_len)]


def obtener_bloques_ordenados(texto: str) -> list[list[str]]:
    texto = texto.replace("\xa0", " ").replace("\u200b", "")
    lineas = [linea.rstrip() for linea in texto.strip().split("\n")]

    bloques: list[list[str]] = []
    bloque_actual: list[str] = []

    for linea in lineas:
        if not linea.strip():
            if bloque_actual and bloque_actual[-1] != "":
                bloque_actual.append("")
            continue

        if not bloque_actual:
            bloque_actual.append(linea)
            continue

        prev = next((l for l in reversed(bloque_actual) if l.strip()), "")
        habia_vacia = bloque_actual[-1] == ""

        if es_lista(linea) or es_linea_codigo(linea) or prev.endswith(":"):
            bloque_actual.append(linea)
        elif (es_linea_codigo(prev) or es_lista(prev)) and not habia_vacia:
            if linea.endswith(":"):
                bloques.append(bloque_actual)
                bloque_actual = [linea]
            else:
                bloque_actual.append(linea)
        else:
            bloques.append(bloque_actual)
            bloque_actual = [linea]

    if bloque_actual:
        bloques.append(bloque_actual)

    bloques.reverse()
    return bloques


def construir_rich_text(texto: str) -> list[dict[str, Any]]:
    partes = PATRON_INLINE_CODE.split(texto)
    rich_text: list[dict[str, Any]] = []

    for i, parte in enumerate(partes):
        if not parte:
            continue
        es_codigo = i % 2 == 1
        for fragmento in dividir_en_fragmentos(parte):
            rich_text.append(
                {
                    "type": "text",
                    "text": {"content": fragmento},
                    "annotations": {"code": es_codigo},
                }
            )

    return rich_text[:LIMITE_RICH_TEXT_ITEMS]


def convertir_a_bloques_notion(bloques_texto: list[list[str]]) -> list[dict[str, Any]]:
    bloques_api: list[dict[str, Any]] = []

    for bloque in bloques_texto:
        while bloque and not bloque[0].strip():
            bloque.pop(0)
        while bloque and not bloque[-1].strip():
            bloque.pop()

        if not bloque:
            continue

        buffer_codigo: list[str] = []

        def vaciar_codigo():
            if buffer_codigo:
                codigo_completo = "\n".join(buffer_codigo)
                rich_text_codigo = [
                    {"type": "text", "text": {"content": frag}}
                    for frag in dividir_en_fragmentos(codigo_completo)
                ][:LIMITE_RICH_TEXT_ITEMS]

                bloques_api.append(
                    {
                        "object": "block",
                        "type": "code",
                        "code": {"rich_text": rich_text_codigo, "language": "bash"},
                    }
                )
                buffer_codigo.clear()

        for linea in bloque:
            if not linea.strip():
                vaciar_codigo()
                continue

            if es_linea_codigo(linea):
                buffer_codigo.append(linea)
            else:
                vaciar_codigo()
                if linea.startswith(("- ", "* ")):
                    bloques_api.append(
                        {
                            "object": "block",
                            "type": "bulleted_list_item",
                            "bulleted_list_item": {
                                "rich_text": construir_rich_text(linea[2:])
                            },
                        }
                    )
                elif re.match(r"^\d+\.\s+", linea):
                    contenido = re.sub(r"^\d+\.\s+", "", linea)
                    bloques_api.append(
                        {
                            "object": "block",
                            "type": "numbered_list_item",
                            "numbered_list_item": {
                                "rich_text": construir_rich_text(contenido)
                            },
                        }
                    )
                else:
                    bloques_api.append(
                        {
                            "object": "block",
                            "type": "paragraph",
                            "paragraph": {"rich_text": construir_rich_text(linea)},
                        }
                    )

        vaciar_codigo()
        bloques_api.append({"object": "block", "type": "divider", "divider": {}})

    if bloques_api and bloques_api[-1]["type"] == "divider":
        bloques_api.pop()

    return bloques_api


def obtener_todos_los_bloques(page_id: str) -> list[dict[str, Any]]:
    """Obtiene todos los bloques activos de la página manejando paginación y tipado."""
    bloques: list[dict[str, Any]] = []
    cursor: str | None = None

    while True:
        params: dict[str, Any] = {"block_id": page_id, "page_size": 100}
        if cursor is not None:
            params["start_cursor"] = cursor

        respuesta = cast(dict[str, Any], notion.blocks.children.list(**params))
        resultados = cast(list[dict[str, Any]], respuesta.get("results") or [])

        for b in resultados:
            if not b.get("archived") and not b.get("in_trash"):
                bloques.append(b)

        next_cursor = respuesta.get("next_cursor")
        if not respuesta.get("has_more") or not isinstance(next_cursor, str):
            break
        cursor = next_cursor

    return bloques


def borrar_bloque_seguro(block_id: str):
    """Elimina un bloque respetando el rate limit de Notion (3 req/s) y reintentando en HTTP 429."""
    for intento in range(3):
        try:
            notion.blocks.delete(block_id=block_id)
            time.sleep(0.35)
            return
        except APIResponseError as e:
            if e.status == 429 and intento < 2:
                time.sleep(2.0 * (intento + 1))
            else:
                raise


def procesar_pagina(page_id: str):
    children = obtener_todos_los_bloques(page_id)
    lineas_extraidas: list[str] = []
    bloques_a_borrar: list[str] = []
