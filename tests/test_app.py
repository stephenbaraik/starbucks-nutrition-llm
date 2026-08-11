from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).parents[1] / "app.py"
DATA_DIR = Path(__file__).parents[1] / "data" / "raw"


def test_app_waits_for_both_csvs_before_showing_tabs(monkeypatch):
    """With nothing uploaded yet, the app must ask for the CSVs and not render tabs."""
    monkeypatch.setenv("GROQ_API_KEY", "")
    app = AppTest.from_file(APP_PATH).run(timeout=20)

    assert not app.exception
    assert len(app.tabs) == 0
    assert len(app.chat_input) == 0


def test_dashboard_starts_with_the_data_chat(monkeypatch):
    """Once both CSVs are uploaded, the app must load and keep Chat as the landing tab."""
    monkeypatch.setenv("GROQ_API_KEY", "")
    app = AppTest.from_file(APP_PATH).run(timeout=20)
    app.file_uploader[0].set_value([
        ("starbucks-menu-nutrition-drinks.csv", (DATA_DIR / "starbucks-menu-nutrition-drinks.csv").read_bytes(), "text/csv"),
        ("starbucks-menu-nutrition-food.csv", (DATA_DIR / "starbucks-menu-nutrition-food.csv").read_bytes(), "text/csv"),
    ])
    app.run(timeout=20)

    assert not app.exception
    assert [tab.label for tab in app.tabs] == ["Chat", "Data & Stats", "Charts"]
    assert len(app.chat_input) == 1
