import unittest
from pathlib import Path


class MobileChartLayoutTests(unittest.TestCase):
    def test_horizontal_category_charts_scroll_instead_of_compressing_plot(self):
        source = Path(__file__).parents[1].joinpath("analyze_daily_interactive.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("el.classList.toggle('chart-horizontal',horizontal)", source)
        self.assertIn("<div class=\"chart-stage\"><canvas", source)
        self.assertIn(".chartjs-box.chart-horizontal{overflow-x:auto", source)
        self.assertIn(".chartjs-box.chart-horizontal .chart-stage{width:640px;min-width:640px}", source)


if __name__ == "__main__":
    unittest.main()
