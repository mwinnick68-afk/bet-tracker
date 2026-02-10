from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from src.db import get_db_path, init_db, now_iso
from src.metrics import profit


DB_DEFAULT = get_db_path(None)  # data/bets.db


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def fetch_bets(conn: sqlite3.Connection) -> pd.DataFrame:
    rows = conn.execute(
        """
        SELECT id, date, sport, book, type, team_or_player, odds_american, stake, result, notes
        FROM bets
        ORDER BY date DESC, id DESC
        """
    ).fetchall()
    df = pd.DataFrame([dict(r) for r in rows])
    if df.empty:
        return df

    # Normalize types
    df["odds_american"] = pd.to_numeric(df["odds_american"], errors="coerce")
    df["stake"] = pd.to_numeric(df["stake"], errors="coerce")
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
    df["result"] = df["result"].astype(str)

    # Profit column
    df["profit"] = df.apply(
        lambda r: float(profit(float(r["stake"]), float(r["odds_american"]), str(r["result"]))),
        axis=1,
    )
    return df


def insert_bet(
    conn: sqlite3.Connection,
    *,
    bet_date: date,
    sport: str,
    book: str,
    bet_type: str,
    team_or_player: str,
    odds_american: int,
    stake: float,
    result: str,
    notes: str,
) -> bool:
    # store consistent result casing (same as your CLI pattern)
    res = result.strip()
    created_at = now_iso()

    cur = conn.execute(
        """
        INSERT OR IGNORE INTO bets
        (date, sport, book, type, team_or_player, odds_american, stake, result, notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            bet_date.isoformat(),
            sport.strip(),
            book.strip(),
            bet_type.strip(),
            team_or_player.strip(),
            float(odds_american),
            float(stake),
            res,
            (notes or "").strip(),
            created_at,
        ),
    )
    conn.commit()
    return cur.rowcount == 1


def update_result(conn: sqlite3.Connection, bet_id: int, result: str) -> None:
    conn.execute("UPDATE bets SET result = ? WHERE id = ?", (result.strip(), bet_id))
    conn.commit()


st.set_page_config(page_title="Bet Tracker", layout="wide")
st.title("🏈 Bet Tracker")


# Sidebar: DB path + filters
st.sidebar.header("Settings")
db_path_str = st.sidebar.text_input("DB path", value=str(DB_DEFAULT))
db_path = Path(db_path_str)

with connect(db_path) as conn:
    init_db(conn)

    df = fetch_bets(conn)

    st.sidebar.header("Filters")
    if df.empty:
        st.info("No bets in the database yet. Use the **Add Bet** form below.")
    else:
        min_date = df["date"].min()
        max_date = df["date"].max()
        date_range = st.sidebar.date_input("Date range", value=(min_date, max_date))
        if isinstance(date_range, tuple) and len(date_range) == 2:
            start_date, end_date = date_range
        else:
            start_date, end_date = min_date, max_date

        sports = ["(all)"] + sorted(df["sport"].dropna().astype(str).unique().tolist())
        books = ["(all)"] + sorted(df["book"].dropna().astype(str).unique().tolist())
        results = ["(all)"] + sorted(df["result"].dropna().astype(str).unique().tolist())

        sport_sel = st.sidebar.selectbox("Sport", sports)
        book_sel = st.sidebar.selectbox("Book", books)
        result_sel = st.sidebar.selectbox("Result", results)

        # Apply filters
        f = df.copy()
        f = f[(f["date"] >= start_date) & (f["date"] <= end_date)]
        if sport_sel != "(all)":
            f = f[f["sport"] == sport_sel]
        if book_sel != "(all)":
            f = f[f["book"] == book_sel]
        if result_sel != "(all)":
            f = f[f["result"] == result_sel]
    # end else

# Main: KPIs + Table
if df.empty:
    st.stop()

# Use filtered df if it exists
f = locals().get("f", df)

k1, k2, k3, k4 = st.columns(4)
total_stake = float(f["stake"].sum()) if not f.empty else 0.0
total_profit = float(f["profit"].sum()) if not f.empty else 0.0
roi = (total_profit / total_stake) if total_stake > 0 else 0.0
wins = (f["result"].astype(str).str.upper() == "W").sum()
losses = (f["result"].astype(str).str.upper() == "L").sum()
win_rate = (wins / (wins + losses)) if (wins + losses) > 0 else 0.0

k1.metric("Total Stake", f"{total_stake:.2f}")
k2.metric("Total Profit", f"{total_profit:.2f}")
k3.metric("ROI", f"{roi * 100:.1f}%")
k4.metric("Win Rate (W vs L)", f"{win_rate * 100:.1f}%")

st.subheader("Bets")
st.dataframe(
    f[
        [
            "id",
            "date",
            "sport",
            "book",
            "type",
            "team_or_player",
            "odds_american",
            "stake",
            "result",
            "profit",
            "notes",
        ]
    ],
    use_container_width=True,
    hide_index=True,
)

# Forms
st.divider()
c1, c2 = st.columns(2)

with c1:
    st.subheader("Add Bet")
    with st.form("add_bet_form", clear_on_submit=True):
        bet_date = st.date_input("Date", value=date.today())
        sport = st.text_input("Sport", value="NBA")
        book = st.text_input("Book", value="DK")
        bet_type = st.text_input("Type", value="spread")
        team_or_player = st.text_input("Team / Player", value="Knicks -3.5")
        odds_american = st.number_input("Odds (American)", value=-110, step=1)
        stake = st.number_input("Stake", value=50.0, step=1.0, min_value=0.01)
        result = st.selectbox("Result", ["open", "W", "L", "P"])
        notes = st.text_input("Notes", value="")
        submitted = st.form_submit_button("Add")

    if submitted:
        with connect(db_path) as conn:
            init_db(conn)
            ok = insert_bet(
                conn,
                bet_date=bet_date,
                sport=sport,
                book=book,
                bet_type=bet_type,
                team_or_player=team_or_player,
                odds_american=int(odds_american),
                stake=float(stake),
                result=str(result),
                notes=notes,
            )
        if ok:
            st.success("Inserted bet.")
        else:
            st.warning("Skipped duplicate bet.")
        st.rerun()

with c2:
    st.subheader("Update Result")
    if f.empty:
        st.info("No bets match current filters.")
    else:
        # choose from ALL df (not filtered) so you can find it even if filters hide it
        options = df[["id", "date", "sport", "book", "team_or_player", "result"]].copy()
        options["label"] = (
            options["id"].astype(str)
            + " | "
            + options["date"].astype(str)
            + " | "
            + options["sport"].astype(str)
            + " | "
            + options["book"].astype(str)
            + " | "
            + options["team_or_player"].astype(str)
            + " | "
            + options["result"].astype(str)
        )
        choice = st.selectbox("Select bet", options["label"].tolist())
        bet_id = int(choice.split("|")[0].strip())

        new_result = st.selectbox("New result", ["open", "W", "L", "P"])
        if st.button("Update"):
            with connect(db_path) as conn:
                init_db(conn)
                update_result(conn, bet_id, new_result)
            st.success(f"Updated bet {bet_id} → {new_result}")
            st.rerun()
