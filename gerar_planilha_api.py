"""Gera/atualiza uma planilha XLSX com precos da Albion Online Data API."""

import argparse
import csv
import gzip
import json
import os
import subprocess
import sys
import zipfile
import zlib
from datetime import datetime, timezone
from xml.etree import ElementTree as ET
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from modules.albion_html_generator import AlbionHTMLGenerator
from modules.albion_items import build_api_item_id, get_category_items


API_HOSTS = {
    "west": "https://west.albion-online-data.com",
    "east": "https://east.albion-online-data.com",
    "europe": "https://europe.albion-online-data.com",
}

ROYAL_CITIES = [
    "Bridgewatch",
    "Caerleon",
    "Fort Sterling",
    "Lymhurst",
    "Martlock",
    "Thetford",
]
BLACK_MARKET = "Black Market"
DEFAULT_LOCATIONS = ROYAL_CITIES + [BLACK_MARKET]
FIELDNAMES = [
    "Gerado em",
    "Categoria",
    "Item",
    "Tier",
    "Encantamento",
    "API ID",
    "Black Market pedido venda",
    "Black Market venda atualizado",
    *[f"{city} venda min" for city in ROYAL_CITIES],
]

SHEET_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
ET.register_namespace("", SHEET_NS)
ET.register_namespace("r", REL_NS)


def parse_number_list(value, allowed_values):
    numbers = []
    for part in value.split(","):
        part = part.strip().replace(".", "")
        if not part:
            continue
        try:
            number = int(part)
        except ValueError:
            raise argparse.ArgumentTypeError(f"Valor invalido: {part}")
        if number not in allowed_values:
            allowed = ", ".join(str(item) for item in sorted(allowed_values))
            raise argparse.ArgumentTypeError(f"Use apenas: {allowed}")
        numbers.append(number)
    return numbers


def parse_args():
    parser = argparse.ArgumentParser(
        description="Atualiza XLSX com precos do Black Market e menores vendas das cidades."
    )
    parser.add_argument(
        "--category",
        choices=["armas", "armaduras", "ambos"],
        default="ambos",
        help="Categoria que sera incluida na planilha.",
    )
    parser.add_argument(
        "--server",
        choices=sorted(API_HOSTS),
        default="west",
        help="Servidor da Albion Online Data API.",
    )
    parser.add_argument(
        "--tiers",
        default="5,6,7,8",
        type=lambda value: parse_number_list(value, {5, 6, 7, 8}),
        help="Tiers separados por virgula. Exemplo: 5,6,7,8",
    )
    parser.add_argument(
        "--enchants",
        default="0,1,2,3",
        type=lambda value: parse_number_list(value, {0, 1, 2, 3}),
        help="Encantamentos separados por virgula. Exemplo: 0,1,2,3",
    )
    parser.add_argument(
        "--quality",
        default="1,2,3",
        type=lambda value: parse_number_list(value, {1, 2, 3, 4, 5}),
        help="Qualidades separadas por virgula. Padrao: 1,2,3.",
    )
    parser.add_argument(
        "--output",
        default="reports/albion_api_prices.csv",
        help="Caminho dos dados gerados. Use .csv; o atualizador .ps1 converte para .xlsx pelo Excel.",
    )
    parser.add_argument(
        "--html-output",
        default="reports/market_analysis.html",
        help="Caminho do relatorio HTML gerado com os mesmos dados da API.",
    )
    parser.add_argument(
        "--no-html",
        action="store_true",
        help="Nao gerar o relatorio HTML.",
    )
    parser.add_argument(
        "--timeout",
        default=25,
        type=int,
        help="Timeout das chamadas HTTP em segundos.",
    )
    return parser.parse_args()


def selected_categories(category):
    if category == "ambos":
        return ["armas", "armaduras"]
    return [category]


def build_catalog(category, tiers, enchants):
    catalog = []
    category_items = get_category_items()

    for category_name in selected_categories(category):
        for item_name in category_items[category_name]:
            for tier in tiers:
                tier_label = f"T{tier}"
                for enchant in enchants:
                    item_id = build_api_item_id(item_name, tier_label, f".{enchant}")
                    if not item_id:
                        continue
                    catalog.append({
                        "category": category_name,
                        "item_name": item_name,
                        "tier": tier_label,
                        "enchantment": f".{enchant}",
                        "item_id": item_id,
                    })
    return catalog


def build_api_url(host, item_ids, locations, quality):
    ids_path = quote(",".join(item_ids), safe=",@_")
    locations_param = quote(",".join(locations), safe=",")
    return (
        f"{host}/api/v2/stats/prices/{ids_path}.json"
        f"?locations={locations_param}&qualities={quality}"
    )


def build_history_api_url(host, item_ids, location, quality, time_scale=24):
    ids_path = quote(",".join(item_ids), safe=",@_")
    location_param = quote(location, safe="")
    return (
        f"{host}/api/v2/stats/history/{ids_path}.json"
        f"?locations={location_param}&qualities={quality}&time-scale={time_scale}"
    )


def chunk_ids_for_url(url_builder, item_ids, max_url_length=3900):
    chunk = []
    for item_id in item_ids:
        candidate = chunk + [item_id]
        if chunk and len(url_builder(candidate)) > max_url_length:
            yield chunk
            chunk = [item_id]
        else:
            chunk = candidate
    if chunk:
        yield chunk


def chunk_ids(host, item_ids, locations, quality, max_url_length=3900):
    return chunk_ids_for_url(
        lambda candidate: build_api_url(host, candidate, locations, quality),
        item_ids,
        max_url_length=max_url_length,
    )


def fetch_prices(host, item_ids, locations, quality, timeout):
    prices = {}
    chunks = list(chunk_ids(host, item_ids, locations, quality))

    for index, chunk in enumerate(chunks, start=1):
        url = build_api_url(host, chunk, locations, quality)
        print(f"Baixando lote {index}/{len(chunks)} ({len(chunk)} itens)...")
        request = Request(
            url,
            headers={
                "Accept-Encoding": "gzip, deflate",
                "User-Agent": "albion-market-tracker-csv/1.0",
            },
        )

        payload = fetch_url(request, url, timeout)

        for entry in json.loads(payload):
            item_id = entry.get("item_id")
            city = entry.get("city")
            if not item_id or not city:
                continue
            prices.setdefault(item_id, {}).setdefault(city, []).append(entry)

    return prices


def fetch_daily_sales_history(host, item_ids, quality, timeout):
    history = {}
    chunks = list(
        chunk_ids_for_url(
            lambda candidate: build_history_api_url(host, candidate, BLACK_MARKET, quality),
            item_ids,
        )
    )

    for index, chunk in enumerate(chunks, start=1):
        url = build_history_api_url(host, chunk, BLACK_MARKET, quality)
        print(f"Baixando historico {index}/{len(chunks)} ({len(chunk)} itens)...")
        request = Request(
            url,
            headers={
                "Accept-Encoding": "gzip, deflate",
                "User-Agent": "albion-market-tracker-csv/1.0",
            },
        )

        payload = fetch_url(request, url, timeout)

        for entry in json.loads(payload):
            item_id = entry.get("item_id")
            data_points = entry.get("data") or []
            if not item_id or not data_points:
                continue
            latest = max(data_points, key=lambda data: data.get("timestamp", ""))
            candidate = {
                "item_count": positive_int(latest.get("item_count")),
                "timestamp": latest.get("timestamp", ""),
            }
            current = history.get(item_id)
            if not current or history_sort_key(candidate) > history_sort_key(current):
                history[item_id] = candidate

    return history


def fetch_url(request, url, timeout):
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = response.read()
            encoding = response.headers.get("Content-Encoding", "").lower()
            if encoding == "gzip":
                payload = gzip.decompress(payload)
            elif encoding == "deflate":
                payload = zlib.decompress(payload)
            return payload.decode("utf-8")
    except HTTPError as exc:
        raise RuntimeError(f"API respondeu HTTP {exc.code}: {url}") from exc
    except URLError as exc:
        if "unknown url type: https" not in str(exc):
            raise RuntimeError(f"Nao foi possivel acessar a API: {exc}") from exc

    return fetch_url_with_powershell(url, timeout)


def fetch_url_with_powershell(url, timeout):
    command = [
        "powershell",
        "-NoProfile",
        "-Command",
        (
            "$ProgressPreference='SilentlyContinue'; "
            "[Net.ServicePointManager]::SecurityProtocol = "
            "[Net.SecurityProtocolType]::Tls12 -bor [Net.SecurityProtocolType]::Tls13; "
            f"(Invoke-WebRequest -UseBasicParsing -TimeoutSec {int(timeout)} "
            "-Headers @{'Accept-Encoding'='gzip, deflate'; "
            "'User-Agent'='albion-market-tracker-csv/1.0'} "
            f"-Uri {json.dumps(url)}).Content"
        ),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout + 5)
    if result.returncode != 0:
        error = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"Nao foi possivel acessar a API pelo PowerShell: {error}")
    return result.stdout


def positive_int(value):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 0
    return parsed if parsed > 0 else 0


def best_sell_entry(price_entries, city):
    candidates = []
    for entry in price_entries.get(city, []):
        sell_price = positive_int(entry.get("sell_price_min"))
        if sell_price:
            candidates.append(entry)
    if not candidates:
        return {}
    return min(candidates, key=lambda entry: positive_int(entry.get("sell_price_min")))


def history_sort_key(entry):
    return (
        str(entry.get("timestamp", "")),
        positive_int(entry.get("item_count")),
    )


def build_rows(catalog, prices, history, generated_at):
    rows = []
    for item in catalog:
        price_entries = prices.get(item["item_id"], {})
        black_market_sell_entry = best_sell_entry(price_entries, BLACK_MARKET)
        black_market_sell = positive_int(black_market_sell_entry.get("sell_price_min"))

        city_values = {}
        for city in ROYAL_CITIES:
            city_entry = best_sell_entry(price_entries, city)
            city_values[city] = positive_int(city_entry.get("sell_price_min"))

        row = {
            "Gerado em": generated_at,
            "Categoria": item["category"],
            "Item": item["item_name"],
            "Tier": item["tier"],
            "Encantamento": item["enchantment"],
            "API ID": item["item_id"],
            "Black Market pedido venda": black_market_sell or "",
            "Black Market venda atualizado": black_market_sell_entry.get("sell_price_min_date", ""),
        }

        for city in ROYAL_CITIES:
            row[f"{city} venda min"] = city_values[city] or ""

        rows.append(row)

    rows.sort(
        key=lambda row: (
            row["Categoria"],
            row["Item"],
            row["Tier"],
            row["Encantamento"],
        )
    )
    return rows


def save_spreadsheet(rows, output_path):
    output = Path(output_path)
    if output.suffix.lower() == ".csv":
        return save_csv(rows, output)
    raise RuntimeError("Para gerar/atualizar XLSX, use atualizar_planilha_api.ps1 ou atualizar_planilha_api.bat.")


def save_csv(rows, output):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)

    try:
        write_csv_file(output, FIELDNAMES, rows)
        return output
    except PermissionError:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        fallback = output.with_name(f"{output.stem}_{timestamp}{output.suffix}")
        write_csv_file(fallback, FIELDNAMES, rows)
        print(f"Arquivo original em uso: {output}")
        print(f"Salvei uma copia atualizada em: {fallback}")
        return fallback


def write_csv_file(output, fieldnames, rows):
    with output.open("w", newline="", encoding="utf-8-sig") as file_handle:
        writer = csv.DictWriter(file_handle, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)


def save_xlsx(rows, output):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)

    try:
        if output.exists():
            write_updated_xlsx(output, output, FIELDNAMES, rows)
        else:
            write_new_xlsx(output, FIELDNAMES, rows)
        return output
    except PermissionError as exc:
        raise RuntimeError(
            f"Nao consegui atualizar {output}. Feche a planilha no Excel/LibreOffice "
            "e aguarde o OneDrive liberar o arquivo antes de tentar novamente."
        ) from exc


def ensure_output_is_writable(output_path):
    output = Path(output_path)
    if output.suffix.lower() != ".xlsx" or not output.exists():
        return

    temp_path = output.with_name(f".{output.stem}.locktest{output.suffix}")
    try:
        with zipfile.ZipFile(output, "r"):
            pass
        output.replace(temp_path)
        temp_path.replace(output)
    except PermissionError as exc:
        raise RuntimeError(
            f"A planilha principal esta aberta ou travada: {output}. "
            "Feche o arquivo e rode o atualizador novamente."
        ) from exc
    finally:
        if temp_path.exists() and not output.exists():
            temp_path.replace(output)


def qn(name):
    return f"{{{SHEET_NS}}}{name}"


def col_letter(index):
    letters = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def cell_ref(row_index, column_index):
    return f"{col_letter(column_index)}{row_index}"


def value_cell(row_index, column_index, value, style_id=None):
    cell = ET.Element(qn("c"), {"r": cell_ref(row_index, column_index)})
    if style_id:
        cell.set("s", style_id)

    if isinstance(value, int):
        ET.SubElement(cell, qn("v")).text = str(value)
        return cell

    cell.set("t", "inlineStr")
    inline_string = ET.SubElement(cell, qn("is"))
    text = ET.SubElement(inline_string, qn("t"))
    text.text = "" if value is None else str(value)
    return cell


def build_sheet_data(fieldnames, rows, style_map=None):
    style_map = style_map or {}
    sheet_data = ET.Element(qn("sheetData"))
    data = [dict(zip(fieldnames, fieldnames))]
    data.extend(rows)

    for row_index, row_data in enumerate(data, start=1):
        row = ET.SubElement(sheet_data, qn("row"), {"r": str(row_index)})
        for column_index, field in enumerate(fieldnames, start=1):
            coordinate = cell_ref(row_index, column_index)
            column = col_letter(column_index)
            style_id = (
                style_map.get(coordinate)
                or (style_map.get(f"{column}2") if row_index > 1 else None)
                or (style_map.get(f"{column}1") if row_index == 1 else None)
            )
            row.append(value_cell(row_index, column_index, row_data.get(field, ""), style_id))

    return sheet_data


def collect_style_map(sheet_root):
    style_map = {}
    sheet_data = sheet_root.find(qn("sheetData"))
    if sheet_data is None:
        return style_map

    for cell in sheet_data.iter(qn("c")):
        coordinate = cell.get("r")
        style_id = cell.get("s")
        if coordinate and style_id:
            style_map[coordinate] = style_id
    return style_map


def update_dimension(sheet_root, row_count, column_count):
    dimension = sheet_root.find(qn("dimension"))
    if dimension is not None:
        dimension.set("ref", f"A1:{cell_ref(row_count, column_count)}")


def update_auto_filter(sheet_root, row_count, column_count):
    auto_filter = sheet_root.find(qn("autoFilter"))
    if auto_filter is not None:
        auto_filter.set("ref", f"A1:{cell_ref(row_count, column_count)}")


def replace_sheet_data(sheet_root, fieldnames, rows):
    style_map = collect_style_map(sheet_root)
    old_sheet_data = sheet_root.find(qn("sheetData"))
    new_sheet_data = build_sheet_data(fieldnames, rows, style_map)
    children = list(sheet_root)

    if old_sheet_data is None:
        sheet_root.append(new_sheet_data)
    else:
        sheet_root.remove(old_sheet_data)
        insert_at = children.index(old_sheet_data)
        sheet_root.insert(insert_at, new_sheet_data)

    update_dimension(sheet_root, len(rows) + 1, len(fieldnames))
    update_auto_filter(sheet_root, len(rows) + 1, len(fieldnames))


def first_sheet_path(workbook):
    workbook_xml = ET.fromstring(workbook.read("xl/workbook.xml"))
    rels_xml = ET.fromstring(workbook.read("xl/_rels/workbook.xml.rels"))
    sheet = workbook_xml.find(qn("sheets")).find(qn("sheet"))
    rel_id = sheet.get(f"{{{REL_NS}}}id")

    for rel in rels_xml:
        if rel.get("Id") == rel_id:
            target = rel.get("Target").replace("\\", "/")
            target = target.lstrip("/")
            return target if target.startswith("xl/") else "xl/" + target

    return "xl/worksheets/sheet1.xml"


def write_updated_xlsx(source, destination, fieldnames, rows):
    source = Path(source)
    destination = Path(destination)
    temp_path = destination.with_name(f".{destination.stem}.tmp{destination.suffix}")

    with zipfile.ZipFile(source, "r") as source_zip:
        sheet_path = first_sheet_path(source_zip)
        sheet_root = ET.fromstring(source_zip.read(sheet_path))
        replace_sheet_data(sheet_root, fieldnames, rows)
        updated_sheet = ET.tostring(sheet_root, encoding="utf-8", xml_declaration=True)

        with zipfile.ZipFile(temp_path, "w", zipfile.ZIP_DEFLATED) as target_zip:
            for item in source_zip.infolist():
                content = updated_sheet if item.filename == sheet_path else source_zip.read(item.filename)
                target_zip.writestr(item, content)

    try:
        os.replace(temp_path, destination)
    except PermissionError:
        temp_path.unlink(missing_ok=True)
        raise


def write_new_xlsx(output, fieldnames, rows):
    sheet_xml = new_sheet_xml(fieldnames, rows)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as workbook:
        workbook.writestr("[Content_Types].xml", content_types_xml())
        workbook.writestr("_rels/.rels", root_rels_xml())
        workbook.writestr("docProps/app.xml", app_xml())
        workbook.writestr("docProps/core.xml", core_xml())
        workbook.writestr("xl/workbook.xml", workbook_xml())
        workbook.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml())
        workbook.writestr("xl/styles.xml", styles_xml())
        workbook.writestr("xl/worksheets/sheet1.xml", sheet_xml)


def new_sheet_xml(fieldnames, rows):
    root = ET.Element(qn("worksheet"))
    ET.SubElement(root, qn("dimension"), {"ref": f"A1:{cell_ref(len(rows) + 1, len(fieldnames))}"})

    sheet_views = ET.SubElement(root, qn("sheetViews"))
    sheet_view = ET.SubElement(sheet_views, qn("sheetView"), {"workbookViewId": "0"})
    ET.SubElement(sheet_view, qn("pane"), {"ySplit": "1", "topLeftCell": "A2", "activePane": "bottomLeft", "state": "frozen"})

    cols = ET.SubElement(root, qn("cols"))
    widths = [14, 28, 9, 13, 18, 14, 24, 18, 16, 20, 16, 16, 16, 20]
    for index, width in enumerate(widths[:len(fieldnames)], start=1):
        ET.SubElement(cols, qn("col"), {"min": str(index), "max": str(index), "width": str(width), "customWidth": "1"})

    style_map = {f"{col_letter(index)}1": "1" for index in range(1, len(fieldnames) + 1)}
    root.append(build_sheet_data(fieldnames, rows, style_map))
    ET.SubElement(root, qn("autoFilter"), {"ref": f"A1:{cell_ref(len(rows) + 1, len(fieldnames))}"})
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def content_types_xml():
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>"""


def root_rels_xml():
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>"""


def workbook_xml():
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="Precos" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>"""


def workbook_rels_xml():
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""


def styles_xml():
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="2">
    <font><sz val="11"/><name val="Arial"/></font>
    <font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Arial"/></font>
  </fonts>
  <fills count="3">
    <fill><patternFill patternType="none"/></fill>
    <fill><patternFill patternType="gray125"/></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FF111111"/><bgColor indexed="64"/></patternFill></fill>
  </fills>
  <borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="2">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
    <xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/>
  </cellXfs>
  <cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>"""


def app_xml():
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">
  <Application>Albion Market Tracker</Application>
</Properties>"""


def core_xml():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:creator>Albion Market Tracker</dc:creator>
  <dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified>
</cp:coreProperties>"""


def main():
    args = parse_args()
    host = API_HOSTS[args.server]
    generated_at = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    catalog = build_catalog(args.category, args.tiers, args.enchants)
    item_ids = sorted({item["item_id"] for item in catalog})

    ensure_output_is_writable(args.output)
    print(f"Itens unicos na consulta: {len(item_ids)}")
    prices = fetch_prices(host, item_ids, DEFAULT_LOCATIONS, args.quality, args.timeout)
    rows = build_rows(catalog, prices, {}, generated_at)
    saved_path = save_spreadsheet(rows, args.output)

    print(f"Planilha gerada: {saved_path}")
    if not args.no_html:
        html_generator = AlbionHTMLGenerator()
        html = html_generator.generate_from_api_rows(
            rows,
            timestamp=generated_at,
            categories=selected_categories(args.category),
            server=args.server,
        )
        html_generator.save_html(html, args.html_output)
        print(f"HTML gerado: {args.html_output}")
    print("Se for XLSX, voce pode estilizar a planilha e rodar novamente sem perder os estilos.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrompido pelo usuario.")
        sys.exit(130)
    except Exception as exc:
        print(f"Erro: {exc}")
        sys.exit(1)
