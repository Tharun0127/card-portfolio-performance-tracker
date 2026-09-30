"""Generate the Power BI report as a Power BI Project (PBIP) from the star schema.

Power BI Desktop opens powerbi/report/CardPortfolioTracker.pbip directly. The project
is plain text: the semantic model is TMDL and the report is PBIR (one JSON file per
visual), so it can be generated, diffed and reviewed like code.

Measures are read from powerbi/measures.dax, so that file stays the single source.
"""
from __future__ import annotations

import json
import re
import shutil
import uuid
from pathlib import Path

from src.paths import POWERBI_DIR, ROOT

PROJECT = "CardPortfolioTracker"
OUT_DIR = POWERBI_DIR / "report"
MODEL_DIR = OUT_DIR / f"{PROJECT}.SemanticModel"
REPORT_DIR = OUT_DIR / f"{PROJECT}.Report"
BASE_THEME = ROOT / "src" / "powerbi_assets" / "CY24SU10.json"
MEASURE_TABLE = "_Measures"

SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition"
PLATFORM_SCHEMA = ("https://developer.microsoft.com/json-schemas/fabric/gitIntegration/"
                   "platformProperties/2.0.0/schema.json")


def stable_guid(name: str) -> str:
    """Same name, same GUID, so regenerating the project does not churn the files."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"card-portfolio-tracker/{name}"))


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def write_json(path: Path, payload: dict) -> None:
    write(path, json.dumps(payload, indent=2) + "\n")


# --------------------------------------------------------------------------------------
# Semantic model (TMDL)
# --------------------------------------------------------------------------------------

INT, NUM, TEXT = "int64", "double", "string"
M_TYPE = {INT: "Int64.Type", NUM: "type number", TEXT: "type text"}

# table -> [(column, type, hidden, sort_by)]
TABLES: dict[str, list[tuple[str, str, bool, str | None]]] = {
    "fact_customer_quarter": [
        ("scenario_key", INT, True, None), ("customer_id", INT, True, None),
        ("tier_key", INT, True, None), ("tenure_key", INT, True, None),
        ("quarter", TEXT, False, None), ("is_active", INT, True, None),
        ("txn_count", NUM, True, None), ("spend", NUM, True, None),
    ],
    "dim_customer": [
        ("customer_id", INT, True, None), ("attrition_flag", TEXT, False, None),
        ("card_tier", TEXT, False, None), ("tenure_band", TEXT, False, None),
        ("tier_tenure_cell", TEXT, False, None), ("cell_customers", INT, False, None),
        ("cell_sample_flag", TEXT, False, None), ("months_on_book", INT, False, None),
        ("customer_age", INT, False, None), ("gender", TEXT, False, None),
        ("education_level", TEXT, False, None), ("marital_status", TEXT, False, None),
        ("income_category", TEXT, False, None), ("relationship_count", INT, False, None),
        ("months_inactive_12m", INT, False, None), ("contacts_12m", INT, False, None),
        ("credit_limit", NUM, False, None),
    ],
    "dim_tier": [
        ("tier_key", INT, True, None), ("card_tier", TEXT, False, "tier_key"),
        ("customers", INT, False, None), ("sample_note", TEXT, False, None),
    ],
    "dim_tenure": [
        ("tenure_key", INT, True, None), ("tenure_band", TEXT, False, "tenure_key"),
        ("min_months_on_book", INT, False, None), ("max_months_on_book", INT, False, None),
        ("customers", INT, False, None),
    ],
    "dim_scenario": [
        ("scenario_key", INT, True, None), ("scenario_code", TEXT, False, None),
        ("scenario_name", TEXT, False, "scenario_key"),
        ("scenario_description", TEXT, False, None),
    ],
    "dim_bridge_step": [
        ("step_key", INT, True, None), ("step", TEXT, False, "step_key"),
    ],
}

RELATIONSHIPS = [
    ("fact_customer_quarter.customer_id", "dim_customer.customer_id"),
    ("fact_customer_quarter.tier_key", "dim_tier.tier_key"),
    ("fact_customer_quarter.tenure_key", "dim_tenure.tenure_key"),
    ("fact_customer_quarter.scenario_key", "dim_scenario.scenario_key"),
]

WHOLE = "#,0"
MONEY0 = r"\$#,0;-\$#,0;\$#,0"
MONEYK = r"\$#,0,.0\K;-\$#,0,.0\K;\$#,0,.0\K"
MONEY2 = r"\$#,0.00;-\$#,0.00;\$#,0.00"
DEC2 = "#,0.00"
PCT1 = "0.0%;-0.0%;0.0%"
PCT2 = "0.00%;-0.00%;0.00%"

FORMATS = {
    WHOLE: ["Customers Q1", "Customers Q4", "Active Customers Q1", "Active Customers Q4",
            "Attrited Customers", "Scenario Key", "Low N Threshold"],
    # Large dollar amounts are shown in thousands. Besides being easier to read, this keeps
    # the digit grouping identical on machines with different regional settings.
    MONEYK: ["Spend Q1", "Spend Q4", "Spend Change", "Effect Customers", "Effect Active Rate",
             "Effect Txns per Active", "Effect Avg Ticket", "Dominant Effect", "Bridge Value",
             "Log Mean Spend", "Attrited Q4 Spend As Observed", "Spend Change Exit Run-Rate"],
    MONEY0: ["Spend per Customer Q1", "Spend per Customer Q4"],
    MONEY2: ["Avg Ticket Q1", "Avg Ticket Q4", "Effect Check"],
    DEC2: ["Txns Q1", "Txns Q4", "Txns per Active Q1", "Txns per Active Q4",
           "Txns per Customer Q1", "Txns per Customer Q4", "Over Index"],
    PCT2: ["Active Rate Q1", "Active Rate Q4", "Active Rate Change pts"],
    PCT1: ["Spend Change %", "Customers Change %", "Txns per Active Change %",
           "Avg Ticket Change %", "Share Customers", "Share Active Rate",
           "Share Txns per Active", "Share Avg Ticket", "Share of Portfolio Change",
           "Share of Q1 Spend", "Share of Q1 Customers", "Contribution pts",
           "Spend per Customer Change %", "Txns per Customer Change %", "Attrition Rate",
           "Attrited Share of Q1 Spend", "Spend Change % Exit Run-Rate", "Heatmap Value"],
}
FORMAT_OF = {name: fmt for fmt, names in FORMATS.items() for name in names}

MEASURE_INLINE: dict[int, bool] = {}  # did the expression start on the MEASURE line
MEASURE_START = re.compile(r"^\s*MEASURE\s+'_Measures'\[(.+?)\]\s*=\s*(.*)$")


def parse_measures() -> list[dict]:
    """Read every MEASURE block in measures.dax with the comment lines above it."""
    lines = (POWERBI_DIR / "measures.dax").read_text(encoding="utf-8").splitlines()
    measures: list[dict] = []
    comments: list[str] = []
    current: dict | None = None
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("EVALUATE"):
            break
        match = MEASURE_START.match(line)
        if match:
            current = {"name": match.group(1), "description": comments,
                       "expression": [match.group(2)] if match.group(2) else []}
            MEASURE_INLINE[id(current)] = bool(match.group(2))
            measures.append(current)
            comments = []
        elif stripped.startswith("//"):
            current = None
            text = stripped.lstrip("/").strip()
            if text and not text.startswith("---") and not text.startswith("==="):
                comments.append(text)
        elif not stripped:
            current, comments = None, []
        elif current is not None:
            current["expression"].append(line)
    for m in measures:
        inline = [ln.strip() for ln in m["expression"][:1] if MEASURE_INLINE.get(id(m))]
        rest = [ln for ln in m["expression"][len(inline):] if ln.strip()]
        indent = min((len(ln) - len(ln.lstrip()) for ln in rest), default=0)
        m["expression"] = inline + [ln[indent:].rstrip() for ln in rest]
    return measures


def tmdl_name(name: str) -> str:
    return name if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) else "'" + name + "'"


def measure_tmdl(m: dict) -> str:
    out = [f"\t/// {line}" for line in m["description"]]
    expression = m["expression"]
    if len(expression) == 1:
        out.append(f"\tmeasure {tmdl_name(m['name'])} = {expression[0]}")
    else:
        out.append(f"\tmeasure {tmdl_name(m['name'])} =")
        out.extend("\t\t\t" + line for line in expression)
    if m["name"] in FORMAT_OF:
        out.append(f"\t\tformatString: {FORMAT_OF[m['name']]}")
    out.append(f"\t\tlineageTag: {stable_guid('measure/' + m['name'])}")
    return "\n".join(out) + "\n"


def table_tmdl(table: str, columns: list[tuple[str, str, bool, str | None]]) -> str:
    out = [f"table {table}", f"\tlineageTag: {stable_guid('table/' + table)}", ""]
    for name, dtype, hidden, sort_by in columns:
        out.append(f"\tcolumn {name}")
        out.append(f"\t\tdataType: {dtype}")
        if hidden:
            out.append("\t\tisHidden")
        if dtype == INT:
            out.append("\t\tformatString: 0")
        out.append(f"\t\tlineageTag: {stable_guid(f'column/{table}/{name}')}")
        out.append("\t\tsummarizeBy: none")
        out.append(f"\t\tsourceColumn: {name}")
        if sort_by:
            out.append(f"\t\tsortByColumn: {sort_by}")
        out.append("")
        out.append("\t\tannotation SummarizationSetBy = User")
        out.append("")
    types = ", ".join(f'{{"{n}", {M_TYPE[t]}}}' for n, t, _, _ in columns)
    out += [
        f"\tpartition {table} = m",
        "\t\tmode: import",
        "\t\tsource =",
        "\t\t\t\tlet",
        f'\t\t\t\t    Source = Csv.Document(File.Contents(DataFolder & "{table}.csv"), '
        f"[Delimiter = \",\", Columns = {len(columns)}, Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),",
        "\t\t\t\t    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),",
        f'\t\t\t\t    Typed = Table.TransformColumnTypes(Promoted, {{{types}}}, "en-US")',
        "\t\t\t\tin",
        "\t\t\t\t    Typed",
        "",
        "\tannotation PBI_ResultType = Table",
        "",
    ]
    return "\n".join(out)


def measures_table_tmdl(measures: list[dict]) -> str:
    out = [f"/// Home table for every measure. It holds no data.",
           f"table {MEASURE_TABLE}", f"\tlineageTag: {stable_guid('table/_Measures')}", ""]
    out.extend(measure_tmdl(m) for m in measures)
    out += [
        "\tcolumn Value",
        "\t\tdataType: int64",
        "\t\tisHidden",
        "\t\tformatString: 0",
        f"\t\tlineageTag: {stable_guid('column/_Measures/Value')}",
        "\t\tsummarizeBy: none",
        "\t\tisNameInferred",
        "\t\tsourceColumn: [Value]",
        "",
        "\t\tannotation SummarizationSetBy = User",
        "",
        f"\tpartition {MEASURE_TABLE} = calculated",
        "\t\tmode: import",
        "\t\tsource = {0}",
        "",
        "\tannotation PBI_Id = " + stable_guid("pbi/_Measures").replace("-", ""),
        "",
    ]
    return "\n".join(out)


def build_model() -> int:
    measures = parse_measures()
    definition = MODEL_DIR / "definition"
    write_json(MODEL_DIR / "definition.pbism", {"version": "4.1", "settings": {}})
    write_json(MODEL_DIR / ".platform", {
        "$schema": PLATFORM_SCHEMA,
        "metadata": {"type": "SemanticModel", "displayName": PROJECT},
        "config": {"version": "2.0", "logicalId": stable_guid("model")},
    })
    write(definition / "database.tmdl", "database\n\tcompatibilityLevel: 1567\n\n")

    tables = [MEASURE_TABLE, *TABLES]
    order = json.dumps([t for t in TABLES])
    model = [
        "model Model",
        "\tculture: en-US",
        "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
        "\tsourceQueryCulture: en-US",
        "\tdataAccessOptions",
        "\t\tlegacyRedirects",
        "\t\treturnErrorValuesAsNull",
        "",
        "annotation __PBI_TimeIntelligenceEnabled = 0",
        "",
        f"annotation PBI_QueryOrder = {order}",
        "",
        *[f"ref table {t}" for t in tables],
        "",
        "ref expression DataFolder",
        "",
    ]
    write(definition / "model.tmdl", "\n".join(model))

    folder = str(POWERBI_DIR) + "\\"
    write(definition / "expressions.tmdl", "\n".join([
        "/// Folder that holds the star schema CSV files. Change this if the repository moves.",
        f'expression DataFolder = "{folder}" meta [IsParameterQuery = true, Type = "Text", '
        "IsParameterQueryRequired = true]",
        f"\tlineageTag: {stable_guid('expression/DataFolder')}",
        "",
        "\tannotation PBI_ResultType = Text",
        "",
    ]))

    rels = []
    for source, target in RELATIONSHIPS:
        rels += [f"relationship {stable_guid(f'rel/{source}')}", f"\tfromColumn: {source}",
                 f"\ttoColumn: {target}", ""]
    write(definition / "relationships.tmdl", "\n".join(rels))

    write(definition / "tables" / f"{MEASURE_TABLE}.tmdl", measures_table_tmdl(measures))
    for table, columns in TABLES.items():
        write(definition / "tables" / f"{table}.tmdl", table_tmdl(table, columns))
    return len(measures)


# --------------------------------------------------------------------------------------
# Report (PBIR)
# --------------------------------------------------------------------------------------

def lit(value) -> dict:
    if isinstance(value, bool):
        text = "true" if value else "false"
    elif isinstance(value, int):
        text = f"{value}L"
    elif isinstance(value, float):
        text = f"{value}D"
    else:
        text = "'" + str(value).replace("'", "''") + "'"
    return {"expr": {"Literal": {"Value": text}}}


def column(entity: str, prop: str) -> dict:
    return {"Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}


def measure(name: str) -> dict:
    return {"Measure": {"Expression": {"SourceRef": {"Entity": MEASURE_TABLE}}, "Property": name}}


def proj(field: dict, display: str | None = None) -> dict:
    kind = next(iter(field))
    entity = field[kind]["Expression"]["SourceRef"]["Entity"]
    prop = field[kind]["Property"]
    out = {"field": field, "queryRef": f"{entity}.{prop}", "nativeQueryRef": prop}
    if display:
        out["displayName"] = display
    return out


def solid(colour) -> dict:
    return {"solid": {"color": colour if isinstance(colour, dict) and "expr" in colour
                      else lit(colour)}}


def title(text) -> dict:
    """A literal title, or a measure-driven one when given a measure field."""
    expr = {"expr": text} if isinstance(text, dict) else lit(text)
    return {"title": [{"properties": {"show": lit(True), "text": expr, "titleWrap": lit(True),
                                      "fontSize": lit(11.0)}}]}


def no_title() -> dict:
    return {"title": [{"properties": {"show": lit(False)}}]}


def visual(name: str, kind: str, box: tuple[int, int, int, int], *, roles: dict | None = None,
           objects: dict | None = None, container: dict | None = None,
           sort: list | None = None, extra: dict | None = None) -> tuple[str, dict]:
    x, y, w, h = box
    body: dict = {"visualType": kind}
    if roles:
        body["query"] = {"queryState": {role: {"projections": ps} for role, ps in roles.items()}}
        if sort:
            body["query"]["sortDefinition"] = {"sort": sort}
    if objects:
        body["objects"] = objects
    if container:
        body["visualContainerObjects"] = container
    body["drillFilterOtherVisuals"] = True
    if extra:
        body.update(extra)
    return name, {
        "$schema": f"{SCHEMA}/visualContainer/2.0.0/schema.json",
        "name": name,
        "position": {"x": x, "y": y, "z": 0, "height": h, "width": w, "tabOrder": 0},
        "visual": body,
    }


def textbox(name: str, box, text: str, size: int = 10, bold: bool = False,
            colour: str = "#52514e") -> tuple[str, dict]:
    style = {"fontSize": f"{size}pt", "color": colour}
    if bold:
        style["fontWeight"] = "bold"
    return visual(name, "textbox", box, objects={"general": [{"properties": {"paragraphs": [
        {"textRuns": [{"value": text, "textStyle": style}]}]}}]}, container=no_title())


def slicer(name: str, box, entity: str, prop: str, mode: str, label: str,
           sync: str | None = None, horizontal: bool = False):
    objects = {
        "data": [{"properties": {"mode": lit(mode)}}],
        "selection": [{"properties": {"singleSelect": lit(True)}}],
        "header": [{"properties": {"show": lit(True)}}],
    }
    if horizontal:
        objects["general"] = [{"properties": {"orientation": lit(1.0)}}]
    extra = {"syncGroup": {"groupName": sync, "fieldChanges": True, "filterChanges": True}} \
        if sync else None
    return visual(name, "slicer", box, roles={"Values": [proj(column(entity, prop), label)]},
                  objects=objects, container=no_title(), extra=extra)


def kpi_card(name: str, box, heading: str, q1: str, q4: str, change: str):
    return visual(name, "multiRowCard", box,
                  roles={"Values": [proj(measure(q4), "Q4"), proj(measure(q1), "Q1"),
                                    proj(measure(change), "Change vs Q1")]},
                  container=title(heading))


def card(name: str, box, measure_name: str, label: str, size: float = 20.0):
    return visual(name, "card", box, roles={"Values": [proj(measure(measure_name), label)]},
                  objects={"labels": [{"properties": {"fontSize": lit(size), "labelDisplayUnits": lit(1.0)}}],
                           "categoryLabels": [{"properties": {"show": lit(True)}}]},
                  container=no_title())


def bar(name: str, box, heading, category: dict | None, values: list[tuple[str, str | None]],
        colour_by: str | None = None, legend: bool = False, sort: list | None = None):
    roles = {"Y": [proj(measure(m), d) for m, d in values]}
    if category:
        roles = {"Category": [dict(proj(category), active=True)], **roles}
    objects: dict = {
        "labels": [{"properties": {"show": lit(True)}}],
        "legend": [{"properties": {"show": lit(legend), "position": lit("Top")}}],
        "categoryAxis": [{"properties": {"showAxisTitle": lit(False)}}],
        "valueAxis": [{"properties": {"showAxisTitle": lit(False)}}],
    }
    if colour_by:
        objects["dataPoint"] = [{
            "properties": {"fill": solid({"expr": measure(colour_by)})},
            "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}]},
        }]
    return visual(name, "clusteredBarChart", box, roles=roles, objects=objects,
                  container=title(heading), sort=sort)


def waterfall(name: str, box, heading, category: dict, value: str, sort: list | None = None):
    objects = {
        "sentimentColors": [{"properties": {
            "increaseFill": solid("#2a78d6"), "decreaseFill": solid("#e34948"),
            "totalFill": solid("#898781")}}],
        "labels": [{"properties": {"show": lit(True), "labelDisplayUnits": lit(1.0)}}],
        "legend": [{"properties": {"show": lit(False)}}],
        "categoryAxis": [{"properties": {"showAxisTitle": lit(False)}}],
        "valueAxis": [{"properties": {"showAxisTitle": lit(False), "labelDisplayUnits": lit(1.0)}}],
    }
    return visual(name, "waterfallChart", box,
                  roles={"Category": [dict(proj(category), active=True)],
                         "Y": [proj(measure(value))]},
                  objects=objects, container=title(heading), sort=sort)


def table(name: str, box, heading, fields: list):
    """fields: a field, or (field, header text)."""
    pairs = [f if isinstance(f, tuple) else (f, None) for f in fields]
    return visual(name, "tableEx", box, roles={"Values": [proj(f, d) for f, d in pairs]},
                  container=title(heading))


def ascending(field: dict) -> list:
    return [{"field": field, "direction": "Ascending"}]


def descending(field: dict) -> list:
    return [{"field": field, "direction": "Descending"}]


FOOTNOTE = ("Q1 and Q4 are estimates derived from 12-month totals and Q4/Q1 ratios under a "
            "linear trend assumption. See ASSUMPTIONS.md. Public Kaggle dataset, 10,127 customers.")


def shared(page: str, heading: str, scenario_slicer: bool = True) -> list:
    items = [
        textbox(f"{page}_title", (20, 2, 900, 52), heading, size=16, bold=True, colour="#0b0b0b"),
        textbox(f"{page}_footnote", (20, 682, 1240, 30), FOOTNOTE, size=9),
    ]
    if scenario_slicer:
        items.append(slicer(f"{page}_scenario", (940, 4, 320, 66), "dim_scenario",
                            "scenario_name", "Basic", "Scenario", sync="scenario",
                            horizontal=True))
    return items


def page_overview() -> list:
    kpis = [
        ("Spend", "Spend Q1", "Spend Q4", "Spend Change %"),
        ("Customers on book", "Customers Q1", "Customers Q4", "Customers Change %"),
        ("Active rate", "Active Rate Q1", "Active Rate Q4", "Active Rate Change pts"),
        ("Transactions per active", "Txns per Active Q1", "Txns per Active Q4",
         "Txns per Active Change %"),
        ("Average ticket", "Avg Ticket Q1", "Avg Ticket Q4", "Avg Ticket Change %"),
    ]
    items = shared("p1", "Card Portfolio Performance Tracker: KPI overview")
    for i, (heading, q1, q4, change) in enumerate(kpis):
        items.append(kpi_card(f"p1_kpi{i + 1}", (20 + i * 250, 74, 240, 190), heading, q1, q4,
                              change))
    items.append(bar("p1_factors", (20, 272, 610, 402), measure("Title KPI"), None,
                     [("Customers Change %", "Customers on book"),
                      ("Active Rate Change pts", "Active rate"),
                      ("Txns per Active Change %", "Transactions per active"),
                      ("Avg Ticket Change %", "Average ticket")], legend=True))
    items.append(bar("p1_tier", (650, 272, 610, 196), measure("Title Tier"),
                     column("dim_tier", "card_tier"), [("Spend Change %", None)],
                     colour_by="Bar Colour", sort=ascending(column("dim_tier", "card_tier"))))
    items.append(bar("p1_tenure", (650, 478, 610, 196), measure("Title Tenure"),
                     column("dim_tenure", "tenure_band"), [("Spend Change %", None)],
                     colour_by="Bar Colour",
                     sort=ascending(column("dim_tenure", "tenure_band"))))
    return items


def page_bridge() -> list:
    step = column("dim_bridge_step", "step")
    items = shared("p2", "Card Portfolio Performance Tracker: spend bridge")
    items += [
        slicer("p2_tier", (20, 56, 250, 76), "dim_tier", "card_tier", "Dropdown", "Card tier"),
        slicer("p2_tenure", (280, 56, 250, 76), "dim_tenure", "tenure_band", "Dropdown",
               "Tenure band (months)"),
        card("p2_method", (540, 56, 190, 76), "Decomposition Method", "Method", size=11.0),
        card("p2_sample", (740, 56, 190, 76), "Sample Flag", "Sample", size=11.0),
        waterfall("p2_waterfall", (20, 140, 800, 534), measure("Title Bridge"), step,
                  "Bridge Value", sort=ascending(step)),
        table("p2_table", (840, 140, 420, 250), "Bridge values: Q1 spend, four effects, total = Q4 spend",
              [(step, "Step"), (measure("Bridge Value"), "Amount")]),
        visual("p2_shares", "multiRowCard", (840, 400, 420, 274),
               roles={"Values": [proj(measure("Share Customers"), "Customers on book"),
                                 proj(measure("Share Active Rate"), "Active rate"),
                                 proj(measure("Share Txns per Active"), "Transactions per active"),
                                 proj(measure("Share Avg Ticket"), "Average ticket"),
                                 proj(measure("Customers Q1"), "Customers on book, Q1"),
                                 proj(measure("Customers Q4"), "Customers on book, Q4")]},
               container=title("Share of the spend change by factor")),
    ]
    return items


def page_heatmap() -> list:
    label = "_Measures.Heatmap Label"
    cell_selector = {"data": [{"dataViewWildcard": {"matchingOption": 1}}], "metadata": label}
    matrix = visual(
        "p3_matrix", "pivotTable", (20, 60, 780, 330),
        roles={"Rows": [dict(proj(column("dim_tier", "card_tier"), "Card tier"), active=True)],
               "Columns": [dict(proj(column("dim_tenure", "tenure_band"), "Tenure band"),
                                active=True)],
               "Values": [proj(measure("Heatmap Label"))]},
        objects={
            "values": [
                {"properties": {"fontSize": lit(10.0), "wordWrap": lit(True)}},
                {"properties": {"backColor": solid({"expr": measure("Heatmap Colour")}),
                                "fontColor": solid({"expr": measure("Heatmap Font Colour")})},
                 "selector": cell_selector},
            ],
            "subTotals": [{"properties": {"rowSubtotals": lit(False),
                                          "columnSubtotals": lit(False)}}],
            "grid": [{"properties": {"rowPadding": lit(12)}}],
        },
        container=title(measure("Title Heatmap")))
    cell = column("dim_customer", "tier_tenure_cell")
    items = shared("p3", "Card Portfolio Performance Tracker: tier x tenure")
    items += [
        matrix,
        textbox("p3_note", (20, 396, 780, 56),
                "Each cell shows the spend change and the dominant driver. Grey cells have fewer "
                "than 50 customers: low n, not interpreted. Platinum has 20 customers and Gold "
                "116 in total. The colour scale is fixed in steps of ten points of decline."),
        table("p3_table", (20, 458, 780, 216), "Cell detail",
              [(cell, "Cell"), (measure("Customers Q1"), "Customers, Q1"),
               (measure("Spend Change %"), "Spend change"),
               (measure("Dominant Driver"), "Dominant driver"),
               (measure("Over Index"), "Over-index"), (measure("Sample Flag"), "Sample")]),
        bar("p3_contribution", (820, 60, 440, 614), measure("Title Contribution"), cell,
            [("Share of Q1 Spend", "Share of Q1 spend"),
             ("Share of Portfolio Change", "Share of portfolio change")], legend=True,
            sort=descending(measure("Share of Q1 Spend"))),
    ]
    return items


def page_attrition() -> list:
    flag = column("dim_customer", "attrition_flag")
    band = column("dim_tenure", "tenure_band")
    items = shared("p4", "Card Portfolio Performance Tracker: attrition lens (as observed)",
                   scenario_slicer=False)
    cards = [("Attrited Customers", "Attrited customers"),
             ("Attrited Share of Q1 Spend", "Their share of Q1 spend"),
             ("Attrited Q4 Spend As Observed", "Q4 spend that leaves with them"),
             ("Spend Change % Exit Run-Rate", "Spend change, exit run-rate")]
    for i, (name, label) in enumerate(cards):
        items.append(card(f"p4_card{i + 1}", (20 + i * 313, 56, 300, 96), name, label))
    items += [
        bar("p4_behaviour", (20, 162, 610, 250), measure("Title Attrition"), flag,
            [("Spend per Customer Change %", "Spend per customer"),
             ("Txns per Customer Change %", "Transactions per customer"),
             ("Avg Ticket Change %", "Average ticket")], legend=True),
        table("p4_table", (650, 162, 610, 250),
              "Attrited customers spend less per head and cut transactions harder",
              [(flag, "Group"), (measure("Customers Q1"), "Customers"),
               (measure("Share of Q1 Spend"), "Share of Q1 spend"),
               (measure("Spend per Customer Q1"), "Spend per customer, Q1"),
               (measure("Spend per Customer Q4"), "Spend per customer, Q4"),
               (measure("Txns per Customer Q1"), "Txns per customer, Q1"),
               (measure("Txns per Customer Q4"), "Txns per customer, Q4")]),
        waterfall("p4_cohort", (20, 422, 610, 252), measure("Title Cohort"), flag,
                  "Spend Change Exit Run-Rate"),
        bar("p4_rate", (650, 422, 610, 252), measure("Title Attrition Rate"), band,
            [("Attrition Rate", None)], sort=ascending(band)),
    ]
    return items


PAGES = [
    ("p1_overview", "1. KPI overview", page_overview),
    ("p2_bridge", "2. Spend bridge", page_bridge),
    ("p3_heatmap", "3. Tier x tenure", page_heatmap),
    ("p4_attrition", "4. Attrition lens", page_attrition),
]


def build_report(active_page: str = "p1_overview") -> int:
    definition = REPORT_DIR / "definition"
    write_json(REPORT_DIR / "definition.pbir", {
        "version": "4.0",
        "datasetReference": {"byPath": {"path": f"../{PROJECT}.SemanticModel"}},
    })
    write_json(REPORT_DIR / ".platform", {
        "$schema": PLATFORM_SCHEMA,
        "metadata": {"type": "Report", "displayName": PROJECT},
        "config": {"version": "2.0", "logicalId": stable_guid("report")},
    })
    write_json(definition / "version.json", {
        "$schema": f"{SCHEMA}/versionMetadata/1.0.0/schema.json", "version": "2.0.0"})

    theme_name = "CardPortfolioTracker.json"
    resources = REPORT_DIR / "StaticResources"
    (resources / "RegisteredResources").mkdir(parents=True, exist_ok=True)
    (resources / "SharedResources" / "BaseThemes").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(POWERBI_DIR / "theme.json", resources / "RegisteredResources" / theme_name)
    shutil.copyfile(BASE_THEME, resources / "SharedResources" / "BaseThemes" / "CY24SU10.json")

    write_json(definition / "report.json", {
        "$schema": f"{SCHEMA}/report/1.3.0/schema.json",
        "themeCollection": {
            "baseTheme": {"name": "CY24SU10", "reportVersionAtImport": "5.61",
                          "type": "SharedResources"},
            "customTheme": {"name": theme_name, "reportVersionAtImport": "5.64",
                            "type": "RegisteredResources"},
        },
        "resourcePackages": [
            {"name": "SharedResources", "type": "SharedResources",
             "items": [{"name": "CY24SU10", "path": "BaseThemes/CY24SU10.json",
                        "type": "BaseTheme"}]},
            {"name": "RegisteredResources", "type": "RegisteredResources",
             "items": [{"name": theme_name, "path": theme_name, "type": "CustomTheme"}]},
        ],
        "settings": {
            "useStylableVisualContainerHeader": True,
            "exportDataMode": "AllowSummarized",
            "defaultFilterActionIsDataFilter": True,
            "defaultDrillFilterOtherVisuals": True,
            "allowChangeFilterTypes": True,
            "allowInlineExploration": True,
            "useEnhancedTooltips": True,
        },
    })

    write_json(definition / "pages" / "pages.json", {
        "$schema": f"{SCHEMA}/pagesMetadata/1.0.0/schema.json",
        "pageOrder": [name for name, _, _ in PAGES],
        "activePageName": active_page,
    })
    count = 0
    for name, display, builder in PAGES:
        write_json(definition / "pages" / name / "page.json", {
            "$schema": f"{SCHEMA}/page/1.4.0/schema.json",
            "name": name, "displayName": display, "displayOption": "FitToPage",
            "height": 720, "width": 1280,
        })
        for order, (visual_name, payload) in enumerate(builder()):
            payload["position"]["z"] = order * 1000
            payload["position"]["tabOrder"] = order * 1000
            write_json(definition / "pages" / name / "visuals" / visual_name / "visual.json",
                       payload)
            count += 1
    return count


def main(active_page: str = "p1_overview") -> None:
    # Rebuild the generated definition folders. Anything Power BI Desktop saved next to
    # them (cache, local settings) is left alone.
    for folder in (MODEL_DIR / "definition", REPORT_DIR / "definition"):
        if folder.exists():
            shutil.rmtree(folder)
    measures = build_model()
    visuals = build_report(active_page)
    write_json(OUT_DIR / f"{PROJECT}.pbip", {
        "version": "1.0",
        "artifacts": [{"report": {"path": f"{PROJECT}.Report"}}],
        "settings": {"enableAutoRecovery": True},
    })
    write(OUT_DIR / ".gitignore", "**/.pbi/localSettings.json\n**/.pbi/cache.abf\n")
    print(f"Wrote {OUT_DIR / (PROJECT + '.pbip')}: {measures} measures, {len(PAGES)} pages, "
          f"{visuals} visuals")


if __name__ == "__main__":
    main()
