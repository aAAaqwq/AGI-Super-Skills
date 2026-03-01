#!/usr/bin/env python3
import sqlite3
import argparse
import sys
import os
from datetime import datetime, timezone


def get_db_connection(db_path, readonly=False):
    if readonly:
        # Use URI for readonly mode
        db_uri = f"file:{db_path}?mode=ro"
        return sqlite3.connect(db_uri, uri=True)
    else:
        return sqlite3.connect(db_path)


def table_exists(conn, table_name):
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    return cursor.fetchone() is not None


def _validate_identifier(name: str) -> None:
    """Raise ValueError if *name* is not a safe SQL identifier (alphanumeric + underscore)."""
    if not name or not all(c.isalnum() or c == "_" for c in name):
        raise ValueError(f"Invalid SQL identifier: {name!r}")


def get_table_columns(conn, table_name):
    _validate_identifier(table_name)
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    return [row[1] for row in cursor.fetchall()]


def mirror_state():
    parser = argparse.ArgumentParser(description="Mirror live trading state to a target paper/livepaper DB.")
    parser.add_argument("--source", required=True, help="Path to the source live DB")
    parser.add_argument("--target", required=True, help="Path to the target paper DB")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be done without writing")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")

    args = parser.parse_args()

    if not os.path.exists(args.source):
        print(f"Error: Source DB does not exist: {args.source}")
        sys.exit(1)

    if not os.path.exists(args.target):
        print(f"Error: Target DB does not exist: {args.target}")
        sys.exit(1)

    try:
        source_conn = get_db_connection(args.source, readonly=True)
        target_conn = get_db_connection(args.target)

        source_cur = source_conn.cursor()

        # 1. Get positions
        source_cur.execute("SELECT * FROM position_state")
        positions = source_cur.fetchall()
        pos_columns = get_table_columns(source_conn, "position_state")

        # 2. Get latest balance
        source_cur.execute("SELECT balance FROM trades ORDER BY id DESC LIMIT 1")
        balance_row = source_cur.fetchone()
        live_balance = balance_row[0] if balance_row else 0.0

        # 3. Get open orders
        orders = []
        order_columns = []
        if table_exists(source_conn, "oms_open_orders"):
            source_cur.execute("SELECT * FROM oms_open_orders")
            orders = source_cur.fetchall()
            order_columns = get_table_columns(source_conn, "oms_open_orders")

        # 4. Get intents
        intents = []
        intent_columns = []
        if table_exists(source_conn, "oms_intents"):
            source_cur.execute("SELECT * FROM oms_intents")
            intents = source_cur.fetchall()
            intent_columns = get_table_columns(source_conn, "oms_intents")

        if args.verbose:
            print(
                f"Read {len(positions)} positions, balance {live_balance}, {len(orders)} orders, {len(intents)} intents from source."
            )

        if args.dry_run:
            print("--- DRY RUN ---")
            print(f"Target DB: {args.target}")
            print(f"Would delete and insert {len(positions)} positions into position_state")
            print(f"Would insert synthetic MIRROR trade with balance {live_balance}")
            print(f"Would delete and insert {len(orders)} orders into oms_open_orders")
            if intents:
                print(f"Would delete and insert {len(intents)} intents into oms_intents")
            print("--- END DRY RUN ---")
            return

        # Start transaction on target
        target_conn.execute("BEGIN TRANSACTION")
        target_cur = target_conn.cursor()

        try:
            # Mirror position_state
            if table_exists(target_conn, "position_state"):
                target_cur.execute("DELETE FROM position_state")
                if positions:
                    for col in pos_columns:
                        _validate_identifier(col)
                    placeholders = ",".join(["?"] * len(pos_columns))
                    target_cur.executemany(
                        f"INSERT INTO position_state ({','.join(pos_columns)}) VALUES ({placeholders})", positions
                    )

            # Mirror balance via synthetic trade
            if table_exists(target_conn, "trades"):
                now_utc = datetime.now(timezone.utc).isoformat()
                target_cur.execute(
                    "INSERT INTO trades (timestamp, action, reason, balance, pnl) VALUES (?, ?, ?, ?, ?)",
                    (now_utc, "SYSTEM", "mirror_live_state", live_balance, 0.0),
                )

            # Mirror oms_open_orders
            if table_exists(target_conn, "oms_open_orders"):
                target_cur.execute("DELETE FROM oms_open_orders")
                if orders:
                    for col in order_columns:
                        _validate_identifier(col)
                    placeholders = ",".join(["?"] * len(order_columns))
                    target_cur.executemany(
                        f"INSERT INTO oms_open_orders ({','.join(order_columns)}) VALUES ({placeholders})", orders
                    )

            # Mirror oms_intents
            if intents and table_exists(target_conn, "oms_intents"):
                target_cur.execute("DELETE FROM oms_intents")
                for col in intent_columns:
                    _validate_identifier(col)
                placeholders = ",".join(["?"] * len(intent_columns))
                target_cur.executemany(
                    f"INSERT INTO oms_intents ({','.join(intent_columns)}) VALUES ({placeholders})", intents
                )

            target_conn.commit()

            print("Successfully mirrored state:")
            print(f" - Positions: {len(positions)}")
            print(f" - Balance: {live_balance}")
            print(f" - Open Orders: {len(orders)}")
            if table_exists(target_conn, "oms_intents"):
                print(f" - Intents: {len(intents)}")

        except Exception as e:
            target_conn.rollback()
            print(f"Error during write transaction: {e}")
            sys.exit(1)
        finally:
            target_conn.close()
            source_conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    mirror_state()
