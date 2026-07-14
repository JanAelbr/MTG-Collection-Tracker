"""Parse and plan deck card list imports in set;number;finish CSV format."""

from __future__ import annotations

import sqlite3

from util.card_finishes import normalize_finish
from util.deck_helpers import resolve_deck_row


def deck_print_key(set_code: str, collector_number: str, finish: int) -> tuple[str, str, int]:
    return (str(set_code).upper(), str(collector_number).strip(), int(finish))


def _is_finish_token(value: str) -> bool:
    text = str(value or "").strip().lower()
    if not text:
        return False
    if text in {"0", "1", "2", "nonfoil", "non-foil", "foil", "etched", "etchedfoil", "etched-foil"}:
        return True
    try:
        return int(text) in {0, 1, 2}
    except ValueError:
        return False


def parse_deck_csv(text: str) -> tuple[list[dict], list[dict]]:
    entries: list[dict] = []
    errors: list[dict] = []

    for line_num, raw_line in enumerate(str(text or "").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("//"):
            continue

        remove_prefix = False
        if line.startswith("-"):
            remove_prefix = True
            line = line[1:].strip()
            if not line:
                errors.append({"line": line_num, "message": "Missing card data after '-'"})
                continue

        parts = [part.strip() for part in line.split(";")]
        if len(parts) < 2:
            errors.append(
                {
                    "line": line_num,
                    "message": "Expected set;number or set;number;finish or set;number;finish;qty",
                }
            )
            continue

        set_code = parts[0].upper()
        collector_number = parts[1]
        finish_raw = ""
        qty = 1

        if len(parts) == 2:
            finish_raw = ""
        elif len(parts) == 3:
            if _is_finish_token(parts[2]):
                finish_raw = parts[2]
            elif parts[2] == "":
                finish_raw = ""
            else:
                try:
                    qty = int(parts[2])
                except ValueError:
                    errors.append({"line": line_num, "message": f"Invalid finish or quantity '{parts[2]}'"})
                    continue
        else:
            finish_raw = parts[2]
            if parts[3] != "":
                try:
                    qty = int(parts[3])
                except ValueError:
                    errors.append({"line": line_num, "message": f"Invalid quantity '{parts[3]}'"})
                    continue

        if not set_code:
            errors.append({"line": line_num, "message": "Set code is required"})
            continue
        if not collector_number:
            errors.append({"line": line_num, "message": "Collector number is required"})
            continue

        if remove_prefix:
            qty = -abs(qty)

        entries.append(
            {
                "line": line_num,
                "set_code": set_code,
                "collector_number": collector_number,
                "finish_raw": finish_raw,
                "qty": qty,
            }
        )

    return entries, errors


def resolve_csv_entries(
    cursor: sqlite3.Cursor,
    entries: list[dict],
) -> tuple[list[dict], list[dict]]:
    resolved: list[dict] = []
    errors: list[dict] = []

    for entry in entries:
        finish = normalize_finish(entry.get("finish_raw"), default=0)
        row = resolve_deck_row(
            cursor,
            {
                "set_code": entry["set_code"],
                "collector_number": entry["collector_number"],
                "finish": finish,
                "qty": abs(int(entry.get("qty") or 1)),
                "section": "main",
                "owned_qty": 0,
                "sort_order": 0,
            },
        )
        if not row.get("set_code") or not row.get("collector_number"):
            errors.append(
                {
                    "line": entry["line"],
                    "message": f"Unknown print {entry['set_code']} #{entry['collector_number']}",
                }
            )
            continue

        image_uri = ""
        image_row = cursor.execute(
            """
            SELECT image_uri FROM cards
            WHERE set_code = ? AND collector_number = ?
            """,
            (row["set_code"], row["collector_number"]),
        ).fetchone()
        if image_row and image_row[0]:
            image_uri = image_row[0]

        resolved.append(
            {
                "line": entry["line"],
                "setCode": row["set_code"],
                "collectorNumber": row["collector_number"],
                "finish": row["finish"],
                "cardName": row["card_name"],
                "inCatalog": bool(row.get("in_catalog")),
                "imageUri": image_uri,
                "qty": int(entry["qty"]),
            }
        )

    return resolved, errors


def _aggregate_targets(resolved: list[dict], mode: str) -> dict[tuple[str, str, int], dict]:
    targets: dict[tuple[str, str, int], dict] = {}

    for entry in resolved:
        key = deck_print_key(entry["setCode"], entry["collectorNumber"], entry["finish"])
        qty = int(entry["qty"])

        if mode == "merge":
            delta = qty
            if key in targets:
                targets[key]["qty"] += delta
            else:
                targets[key] = {**entry, "qty": delta}
            continue

        absolute = max(0, abs(qty)) if qty >= 0 else 0
        if key in targets:
            targets[key]["qty"] += absolute
        else:
            targets[key] = {**entry, "qty": absolute}

    if mode == "merge":
        for key, target in list(targets.items()):
            target["qty"] = max(-99, min(99, int(target["qty"])))
            if target["qty"] == 0:
                del targets[key]

    return targets


def load_section_cards(
    conn: sqlite3.Connection,
    *,
    deck_id: int,
    section: str,
) -> dict[tuple[str, str, int], dict]:
    rows = conn.execute(
        """
        SELECT dc.deck_card_id, dc.set_code, dc.collector_number, dc.finish, dc.qty,
               dc.owned_qty, dc.card_name, dc.in_catalog, c.image_uri
        FROM deck_cards dc
        LEFT JOIN cards c
          ON c.set_code = dc.set_code AND c.collector_number = dc.collector_number
        WHERE dc.deck_id = ? AND dc.section = ?
        """,
        (deck_id, section),
    ).fetchall()

    current: dict[tuple[str, str, int], dict] = {}
    for row in rows:
        key = deck_print_key(row["set_code"], row["collector_number"], row["finish"])
        current[key] = {
            "deckCardId": row["deck_card_id"],
            "setCode": row["set_code"],
            "collectorNumber": row["collector_number"],
            "finish": row["finish"],
            "cardName": row["card_name"],
            "inCatalog": bool(row["in_catalog"]),
            "imageUri": row["image_uri"] or "",
            "currentQty": int(row["qty"]),
            "ownedQty": int(row["owned_qty"]),
        }
    return current


def build_csv_import_plan(
    conn: sqlite3.Connection,
    *,
    deck_id: int,
    csv: str,
    mode: str,
    section: str,
) -> dict:
    normalized_mode = str(mode or "merge").strip().lower()
    if normalized_mode not in {"merge", "set", "replace"}:
        normalized_mode = "merge"

    section_name = str(section or "main").strip().lower()
    if section_name not in {"commander", "main", "sideboard"}:
        section_name = "main"

    entries, parse_errors = parse_deck_csv(csv)
    resolved, resolve_errors = resolve_csv_entries(conn.cursor(), entries)
    errors = parse_errors + resolve_errors

    current = load_section_cards(conn, deck_id=deck_id, section=section_name)
    targets = _aggregate_targets(resolved, normalized_mode)

    changes: list[dict] = []
    keys_to_check = set(current.keys())

    if normalized_mode == "replace":
        keys_to_check |= set(targets.keys())
        for key in keys_to_check:
            current_row = current.get(key)
            target_row = targets.get(key)
            current_qty = int(current_row["currentQty"]) if current_row else 0
            target_qty = max(0, min(99, int(target_row["qty"]))) if target_row else 0
            _append_change(changes, current_row, target_row, current_qty, target_qty, section_name)
        return _plan_payload(changes, errors, normalized_mode, section_name)

    if normalized_mode == "set":
        for key, target_row in targets.items():
            current_row = current.get(key)
            current_qty = int(current_row["currentQty"]) if current_row else 0
            target_qty = max(0, min(99, int(target_row["qty"])))
            _append_change(changes, current_row, target_row, current_qty, target_qty, section_name)
        return _plan_payload(changes, errors, normalized_mode, section_name)

    for key, target_row in targets.items():
        current_row = current.get(key)
        current_qty = int(current_row["currentQty"]) if current_row else 0
        delta = int(target_row["qty"])
        target_qty = max(0, min(99, current_qty + delta))
        _append_change(changes, current_row, target_row, current_qty, target_qty, section_name)

    return _plan_payload(changes, errors, normalized_mode, section_name)


def _append_change(
    changes: list[dict],
    current_row: dict | None,
    target_row: dict | None,
    current_qty: int,
    target_qty: int,
    section: str,
) -> None:
    if current_qty == target_qty:
        return

    source = target_row or current_row
    if not source:
        return

    if current_qty == 0 and target_qty > 0:
        action = "add"
    elif target_qty == 0:
        action = "remove"
    else:
        action = "update"

    changes.append(
        {
            "action": action,
            "setCode": source["setCode"],
            "collectorNumber": source["collectorNumber"],
            "finish": source["finish"],
            "cardName": source["cardName"],
            "inCatalog": bool(source.get("inCatalog")),
            "imageUri": source.get("imageUri") or "",
            "section": section,
            "currentQty": current_qty,
            "newQty": target_qty,
            "delta": target_qty - current_qty,
        }
    )


def _plan_payload(
    changes: list[dict],
    errors: list[dict],
    mode: str,
    section: str,
) -> dict:
    summary = {
        "add": sum(1 for change in changes if change["action"] == "add"),
        "update": sum(1 for change in changes if change["action"] == "update"),
        "remove": sum(1 for change in changes if change["action"] == "remove"),
        "errors": len(errors),
        "totalChanges": len(changes),
    }
    return {
        "valid": len(errors) == 0,
        "canApply": len(errors) == 0 and len(changes) > 0,
        "mode": mode,
        "section": section,
        "errors": errors,
        "changes": changes,
        "summary": summary,
    }
