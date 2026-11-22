"""Colour palettes and the Qt stylesheet (QSS) generated from them."""

from __future__ import annotations

from dataclasses import dataclass

from invaders.core.entities import AlienKind


@dataclass(frozen=True)
class GuiPalette:
    key: str
    label: str
    bg_top: str
    bg_bottom: str
    panel: str
    panel_border: str
    accent: str
    accent2: str
    text: str
    muted: str
    danger: str
    aliens: dict[AlienKind, str]
    player: str
    player_bullet: str
    slow_bullet: str
    fast_bullet: str
    ufo: str
    bunker: dict[int, str]
    explosion: tuple[str, str, str]
    stars: tuple[str, str, str]


CLASSIC = GuiPalette(
    key="classic",
    label="Klasyczny",
    bg_top="#0B0F2A",
    bg_bottom="#02030A",
    panel="#141A3D",
    panel_border="#2A3470",
    accent="#4FD8FF",
    accent2="#FF4FD8",
    text="#E6E9FF",
    muted="#8890C0",
    danger="#FF3C5A",
    aliens={AlienKind.SQUID: "#FF4FD8", AlienKind.CRAB: "#4FD8FF", AlienKind.OCTOPUS: "#8DFF4F"},
    player="#3CF0A0",
    player_bullet="#FFF275",
    slow_bullet="#FF9F1C",
    fast_bullet="#FF3C5A",
    ufo="#FF2E63",
    bunker={3: "#2ECC71", 2: "#F1C40F", 1: "#E74C3C"},
    explosion=("#FFFFFF", "#FFD23F", "#FF6B35"),
    stars=("#2E3456", "#5A6290", "#B8C2FF"),
)

NEON = GuiPalette(
    key="neon",
    label="Neon",
    bg_top="#1A0033",
    bg_bottom="#05000C",
    panel="#22003F",
    panel_border="#5A00A0",
    accent="#FF00E6",
    accent2="#00F0FF",
    text="#FBEAFF",
    muted="#B48CD8",
    danger="#FF073A",
    aliens={AlienKind.SQUID: "#FF00FF", AlienKind.CRAB: "#00FFFF", AlienKind.OCTOPUS: "#FFFF00"},
    player="#39FF14",
    player_bullet="#FFFFFF",
    slow_bullet="#FF6EC7",
    fast_bullet="#FF073A",
    ufo="#FF9900",
    bunker={3: "#00E5FF", 2: "#BF00FF", 1: "#FF007F"},
    explosion=("#FFFFFF", "#FF00FF", "#7A00FF"),
    stars=("#3A0066", "#7F00B2", "#FF8CF0"),
)

GREEN = GuiPalette(
    key="green",
    label="Zielony monitor",
    bg_top="#062006",
    bg_bottom="#010601",
    panel="#0A240A",
    panel_border="#1E5C1E",
    accent="#39FF14",
    accent2="#B6FF9E",
    text="#C8FFB8",
    muted="#5CA04C",
    danger="#FF5C5C",
    aliens={AlienKind.SQUID: "#D8FFC8", AlienKind.CRAB: "#7CFF5C", AlienKind.OCTOPUS: "#2FD12F"},
    player="#B6FF9E",
    player_bullet="#FFFFFF",
    slow_bullet="#5CC74A",
    fast_bullet="#D4FF5C",
    ufo="#E8FFE0",
    bunker={3: "#39FF14", 2: "#22A80C", 1: "#126B05"},
    explosion=("#FFFFFF", "#9DFF7A", "#2F8F1F"),
    stars=("#0E330E", "#1E5C1E", "#5CC74A"),
)

PALETTES: dict[str, GuiPalette] = {p.key: p for p in (CLASSIC, NEON, GREEN)}


def get_palette(key: str) -> GuiPalette:
    return PALETTES.get(key, CLASSIC)


def stylesheet(p: GuiPalette) -> str:
    return f"""
    QWidget {{
        color: {p.text};
        font-family: "Segoe UI", "Inter", "Helvetica Neue", sans-serif;
        font-size: 15px;
    }}
    QMainWindow, #Root {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 {p.bg_top}, stop:1 {p.bg_bottom});
    }}
    QStackedWidget > QWidget {{ background: transparent; }}
    #Card {{
        background: {p.panel};
        border: 1px solid {p.panel_border};
        border-radius: 16px;
    }}
    #Title {{
        font-size: 44px; font-weight: 800; letter-spacing: 6px; color: {p.accent};
    }}
    #Subtitle {{ color: {p.muted}; font-size: 15px; font-style: italic; }}
    #PageTitle {{
        font-size: 28px; font-weight: 800; color: {p.accent}; letter-spacing: 2px;
    }}
    #Hint {{ color: {p.muted}; font-size: 13px; }}
    #Hud {{
        background: {p.panel}; border-bottom: 1px solid {p.panel_border};
    }}
    #HudLabel {{ color: {p.muted}; font-size: 13px; font-weight: 600; letter-spacing: 1px; }}
    #HudValue {{
        color: {p.text}; font-size: 18px; font-weight: 800; font-family: Consolas, monospace;
    }}
    #HudAccent {{ color: {p.accent}; font-size: 18px; font-weight: 800; }}
    #Lives {{ color: {p.player}; font-size: 18px; font-weight: 800; }}
    QPushButton {{
        background: {p.panel_border};
        border: 2px solid transparent;
        border-radius: 10px;
        padding: 10px 22px;
        font-weight: 700;
        min-width: 120px;
    }}
    QPushButton:hover {{ background: {p.accent}; color: {p.bg_bottom}; }}
    QPushButton:focus {{ border: 2px solid {p.accent2}; }}
    QPushButton:pressed {{ background: {p.accent2}; color: {p.bg_bottom}; }}
    QPushButton:disabled {{ background: {p.panel}; color: {p.muted}; }}
    QPushButton#Primary {{ background: {p.accent}; color: {p.bg_bottom}; }}
    QPushButton#Primary:hover {{ background: {p.accent2}; }}
    QPushButton#Danger {{ background: {p.danger}; color: white; }}
    QPushButton#MenuButton {{
        font-size: 18px; padding: 12px 28px; min-width: 280px; text-align: left;
    }}
    QPushButton#Small {{ min-width: 36px; padding: 4px 10px; }}
    QRadioButton, QCheckBox {{ spacing: 10px; padding: 6px; font-weight: 600; }}
    QRadioButton::indicator, QCheckBox::indicator {{
        width: 16px; height: 16px; border: 2px solid {p.muted}; background: {p.bg_bottom};
    }}
    QRadioButton::indicator {{ border-radius: 10px; }}
    QCheckBox::indicator {{ border-radius: 4px; }}
    QRadioButton::indicator:checked, QCheckBox::indicator:checked {{
        background: {p.accent}; border: 2px solid {p.accent2};
    }}
    QRadioButton:checked {{ color: {p.accent}; }}
    QRadioButton:focus, QCheckBox:focus {{
        border: 1px solid {p.accent2}; border-radius: 6px;
    }}
    QComboBox {{
        background: {p.bg_bottom}; border: 1px solid {p.panel_border};
        border-radius: 8px; padding: 6px 10px; min-height: 22px;
    }}
    QSpinBox {{
        background: {p.bg_bottom}; border: 1px solid {p.panel_border};
        border-radius: 8px; min-height: 34px; font-size: 17px; font-weight: 700;
        padding: 0 8px;
    }}
    QSpinBox::up-button, QSpinBox::down-button {{
        subcontrol-origin: border; width: 0px; border: none;
    }}
    QComboBox:focus, QSpinBox:focus {{ border: 2px solid {p.accent}; }}
    QComboBox QAbstractItemView {{
        background: {p.panel}; selection-background-color: {p.accent};
        selection-color: {p.bg_bottom};
    }}
    QTableWidget {{
        background: {p.bg_bottom}; alternate-background-color: {p.panel};
        gridline-color: {p.panel_border}; border: 1px solid {p.panel_border};
        border-radius: 8px; selection-background-color: {p.accent};
        selection-color: {p.bg_bottom};
    }}
    QHeaderView::section {{
        background: {p.panel_border}; color: {p.text}; padding: 6px; border: none;
        font-weight: 700;
    }}
    QProgressBar {{
        background: {p.bg_bottom}; border: 1px solid {p.panel_border}; border-radius: 8px;
        text-align: center; height: 20px;
    }}
    QProgressBar::chunk {{ background: {p.accent}; border-radius: 7px; }}
    QTextBrowser {{
        background: transparent; border: none; font-size: 15px;
    }}
    QToolTip {{
        background: {p.panel}; color: {p.text}; border: 1px solid {p.accent}; padding: 4px;
    }}
    QMessageBox {{ background: {p.panel}; }}
    QDialog {{ background: {p.panel}; }}
    #InitialLetter {{
        font-size: 36px; font-weight: 800; font-family: Consolas, monospace;
        color: {p.text}; background: {p.bg_bottom}; border: 2px solid {p.panel_border};
        border-radius: 8px; min-width: 52px; qproperty-alignment: AlignCenter;
    }}
    #InitialLetter[current="true"] {{ border: 2px solid {p.accent}; color: {p.accent}; }}
    """
