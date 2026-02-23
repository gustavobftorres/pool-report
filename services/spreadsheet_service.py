"""
Google Sheets integration for exporting DataFrames.
"""
import gspread
import pandas as pd
from pathlib import Path
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CREDENTIALS_PATH = PROJECT_ROOT / "credentials.json"


def _format_apy_percentage(value) -> str:
    """Format APY as percentage (e.g. 5.5%). DefiLlama returns decimal (0.055)."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    try:
        num = float(value)
        # DefiLlama returns decimal (0.055 = 5.5%), multiply by 100 if < 1
        if abs(num) < 1 and num != 0:
            num *= 100
        return f"{num:.2f}%"
    except (TypeError, ValueError):
        return str(value)


def _col_letter(n: int) -> str:
    """Convert 1-based column index to Excel column letter (1 -> A, 27 -> AA)."""
    result = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        result = chr(65 + r) + result
    return result


def _format_money(value) -> str:
    """Format number as money (e.g. 1,000,000.00)."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    try:
        num = float(value)
        return f"{num:,.2f}"
    except (TypeError, ValueError):
        return str(value)


def _format_price(value) -> str:
    """Format token price (4-6 decimals, no thousands separator for small values)."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    try:
        num = float(value)
        if num >= 1 or num == 0:
            return f"{num:,.4f}"
        return f"{num:.6f}"  # Small decimals: 0.00001234
    except (TypeError, ValueError):
        return str(value)


def get_client() -> gspread.Client:
    """Return an authorized gspread client."""
    creds = Credentials.from_service_account_file(
        str(CREDENTIALS_PATH),
        scopes=SCOPES
    )
    return gspread.authorize(creds)


def export_dataframe_to_sheet(
    df: pd.DataFrame,
    spreadsheet_name: str = "Landing markets token info",
    sheet_index: int = 0
) -> None:
    """
    Export a DataFrame to a Google Sheet with one value per cell.
    Clears the sheet first, then writes headers and data.

    Args:
        df: The DataFrame to export.
        spreadsheet_name: Name of the Google Spreadsheet.
        sheet_index: Index of the worksheet (0 = first sheet).
    """
    df_export = df.copy()
    for col in df_export.columns:
        df_export[col] = df_export[col].apply(
            lambda x: str(x) if isinstance(x, (list, dict)) else x
        )

    # Format APY as percentage (DefiLlama returns decimal, e.g. 0.055 = 5.5%)
    for col in df_export.columns:
        if col == "apy" or col.endswith("_apy"):
            df_export[col] = df_export[col].apply(_format_apy_percentage)

    # Format price_usd as token price (4-6 decimals)
    for col in df_export.columns:
        if col == "price_usd" or col.endswith("_price_usd"):
            df_export[col] = df_export[col].apply(_format_price)

    # Format tvl_usd, volume, fees, liquidity, fdv_usd, market_cap_usd as money (e.g. 1,000,000.00)
    money_cols = ("volume", "fees", "liquidity", "fdv_usd", "market_cap_usd")
    for col in df_export.columns:
        if col == "tvl_usd" or col.endswith("_tvl_usd"):
            df_export[col] = df_export[col].apply(_format_money)
        if col in money_cols:
            df_export[col] = df_export[col].apply(_format_money)

    values = [df_export.columns.tolist()] + df_export.fillna("").values.tolist()

    client = get_client()
    sheet = client.open(spreadsheet_name).get_worksheet(sheet_index)
    sheet.clear()
    # Update with exact range for variable number of rows (1 header + N data rows)
    num_rows = len(values)
    num_cols = len(df_export.columns)
    if num_rows > 0 and num_cols > 0:
        end_cell = _col_letter(num_cols) + str(num_rows)
        sheet.update(f"A1:{end_cell}", values)
