"""Visual presets for the main window and recording indicator."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    name: str
    description: str
    canvas: str
    panel: str
    field: str
    line: str
    text: str
    muted: str
    accent: str
    button: str
    on_button: str
    hover: str
    dark: bool = False


THEMES = {
    "graphite": Theme(
        "蘋果科技風", "石墨黑、銀灰與冷藍", "#151516", "#202022", "#18181A",
        "#414145", "#F5F5F7", "#B4B4BD", "#92C6FF", "#A2CEFF", "#142238", "#343439", True,
    ),
    "paper": Theme(
        "日系和紙", "和紙白、淺木色與抹茶綠", "#F4F2EB", "#FCFBF7", "#FFFFFF",
        "#D8D6C8", "#30382F", "#5E685A", "#44634A", "#47684F", "#FFFFFF", "#E4ECDF",
    ),
    "clay": Theme(
        "陶土工作室", "燕麥白、赤陶與深咖啡", "#EFE4DA", "#FFF6EE", "#FFFCF8",
        "#DFC4B1", "#432E27", "#735449", "#9A432C", "#A14932", "#FFFFFF", "#F2D9C8",
    ),
}
