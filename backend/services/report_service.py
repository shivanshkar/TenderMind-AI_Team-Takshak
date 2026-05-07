import html
from pathlib import Path
from typing import Any, Dict, List

from fastapi.encoders import jsonable_encoder

from backend.config import REPORT_DIR
from backend.models.schemas import Decision, EvaluationResult
from backend.utils.file_utils import write_json


class ReportService:
    def save(self, result: EvaluationResult) -> EvaluationResult:
        json_path = REPORT_DIR / f"{result.evaluation_id}.json"
        html_path = REPORT_DIR / f"{result.evaluation_id}.html"
        result.report_json_path = str(json_path)
        result.report_html_path = str(html_path)
        write_json(json_path, jsonable_encoder(result))
        html_path.write_text(self.render_html(result), encoding="utf-8")
        return result

    def render_html(self, result: EvaluationResult) -> str:
        criteria_names = [criterion.name for criterion in result.criteria]
        rows = []
        for row in result.matrix:
            cells = [f"<th>{html.escape(str(row['Bidder']))}</th>"]
            for name in criteria_names:
                decision = str(row.get(name, ""))
                cells.append(
                    f'<td class="{css_class(decision)}">{html.escape(decision)}</td>'
                )
            rows.append("<tr>" + "".join(cells) + "</tr>")

        explanation_rows = []
        for item in result.evaluations:
            explanation_rows.append(
                "<tr>"
                f"<td>{html.escape(item.bidder_name)}</td>"
                f"<td>{html.escape(item.criterion_name)}</td>"
                f'<td class="{css_class(item.decision.value)}">{html.escape(item.decision.value)}</td>'
                f"<td>{item.confidence:.3f}</td>"
                f"<td>{html.escape(str(item.extracted_value))}</td>"
                f"<td>{html.escape(item.source_document or 'Not found')}</td>"
                f"<td>{html.escape(item.rule_applied)}</td>"
                f"<td>{html.escape(item.reasoning)}</td>"
                "</tr>"
            )

        summary_cards = []
        for bidder, summary in result.summary.items():
            summary_cards.append(
                "<section class='summary-card'>"
                f"<h3>{html.escape(bidder)}</h3>"
                f"<strong>{html.escape(str(summary['recommendation']))}</strong>"
                f"<p>Score: {summary['score_percent']}%</p>"
                f"<p>Pass: {summary['pass']} | Fail: {summary['fail']} | Review: {summary['needs_review']}</p>"
                "</section>"
            )

        return HTML_TEMPLATE.format(
            evaluation_id=html.escape(result.evaluation_id),
            criteria_header="".join(f"<th>{html.escape(name)}</th>" for name in criteria_names),
            matrix_rows="\n".join(rows),
            explanation_rows="\n".join(explanation_rows),
            summary_cards="\n".join(summary_cards),
        )


def css_class(decision: str) -> str:
    if decision == Decision.PASS.value:
        return "pass"
    if decision == Decision.FAIL.value:
        return "fail"
    return "review"


HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>TenderMind AI Report</title>
  <style>
    body {{
      margin: 0;
      font-family: Arial, sans-serif;
      color: #162033;
      background: #f7f8fb;
    }}
    header {{
      padding: 28px 36px;
      background: #122033;
      color: white;
    }}
    main {{
      padding: 28px 36px 44px;
      max-width: 1280px;
      margin: 0 auto;
    }}
    h1, h2, h3 {{
      margin: 0 0 12px;
    }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 12px;
      margin-bottom: 28px;
    }}
    .summary-card {{
      background: white;
      border: 1px solid #d9dee8;
      border-radius: 8px;
      padding: 16px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background: white;
      margin-bottom: 28px;
      border: 1px solid #d9dee8;
    }}
    th, td {{
      border-bottom: 1px solid #e7ebf1;
      padding: 10px 12px;
      text-align: left;
      vertical-align: top;
      font-size: 14px;
    }}
    th {{
      background: #eef2f7;
      font-weight: 700;
    }}
    .pass {{
      background: #ddf7e7;
      color: #116235;
      font-weight: 700;
    }}
    .fail {{
      background: #ffe1df;
      color: #9d2118;
      font-weight: 700;
    }}
    .review {{
      background: #fff2ca;
      color: #755200;
      font-weight: 700;
    }}
  </style>
</head>
<body>
  <header>
    <h1>TenderMind AI Evaluation Report</h1>
    <p>Evaluation ID: {evaluation_id}</p>
  </header>
  <main>
    <section class="summary">
      {summary_cards}
    </section>

    <h2>Evaluation Matrix</h2>
    <table>
      <thead><tr><th>Bidder</th>{criteria_header}</tr></thead>
      <tbody>{matrix_rows}</tbody>
    </table>

    <h2>Per-Criterion Explanations</h2>
    <table>
      <thead>
        <tr>
          <th>Bidder</th>
          <th>Criterion</th>
          <th>Decision</th>
          <th>Confidence</th>
          <th>Extracted value</th>
          <th>Source document</th>
          <th>Rule applied</th>
          <th>Reasoning</th>
        </tr>
      </thead>
      <tbody>{explanation_rows}</tbody>
    </table>
  </main>
</body>
</html>
"""

