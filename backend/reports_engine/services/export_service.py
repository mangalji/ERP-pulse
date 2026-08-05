"""
Generic ExportService.

Renders a normalized ``{ headers, rows, summary }`` report payload to
any supported format (PDF, XLSX, CSV, JSON). The service is fully
generic — it knows nothing about report types, only about tabular data.

PDF and XLSX use ``reportlab`` and ``openpyxl`` respectively (both
optional). CSV and JSON are built with the stdlib. If an optional
library is missing, the export raises a clear error.
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from reports_engine.models import ExportFormat


class ExportService:
    """Render a report payload to the requested format and return bytes + mimetype."""

    FORMAT_MIME = {
        ExportFormat.CSV: 'text/csv',
        ExportFormat.JSON: 'application/json',
        ExportFormat.PDF: 'application/pdf',
        ExportFormat.XLSX: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    }

    def export(self, *, payload: dict, fmt: str) -> tuple[bytes, str, str]:
        """
        Returns ``(data_bytes, mimetype, file_extension)``.
        """
        fmt = fmt.upper()
        if fmt not in self.FORMAT_MIME:
            raise ValueError(f'Unsupported export format: {fmt}')

        headers = payload.get('headers', [])
        rows = payload.get('rows', [])

        if fmt == ExportFormat.JSON:
            data = self._to_json(payload)
            return data, self.FORMAT_MIME[fmt], 'json'

        if fmt == ExportFormat.CSV:
            data = self._to_csv(headers, rows)
            return data, self.FORMAT_MIME[fmt], 'csv'

        if fmt == ExportFormat.XLSX:
            data = self._to_xlsx(headers, rows)
            return data, self.FORMAT_MIME[fmt], 'xlsx'

        if fmt == ExportFormat.PDF:
            data = self._to_pdf(payload)
            return data, self.FORMAT_MIME[fmt], 'pdf'

        raise ValueError(f'Unsupported export format: {fmt}')

    def _to_json(self, payload: dict) -> bytes:
        return json.dumps(payload, indent=2, default=str).encode('utf-8')

    def _to_csv(self, headers: list[str], rows: list[list[Any]]) -> bytes:
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        if headers:
            writer.writerow(headers)
        for row in rows:
            writer.writerow(self._flatten(row))
        return buffer.getvalue().encode('utf-8')

    def _to_xlsx(self, headers: list[str], rows: list[list[Any]]) -> bytes:
        try:
            from openpyxl import Workbook
        except ImportError as exc:
            raise RuntimeError('XLSX export requires openpyxl. pip install openpyxl') from exc

        wb = Workbook()
        ws = wb.active
        ws.title = 'Report'
        if headers:
            ws.append(headers)
        for row in rows:
            ws.append(self._flatten(row))
        output = io.BytesIO()
        wb.save(output)
        return output.getvalue()

    def _to_pdf(self, payload: dict) -> bytes:
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4, landscape
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
        except ImportError as exc:
            raise RuntimeError('PDF export requires reportlab. pip install reportlab') from exc

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(A4))
        styles = getSampleStyleSheet()
        story = []

        summary = payload.get('summary') or {}
        if summary:
            title = Paragraph(
                f"{payload.get('report_type', 'Enterprise')} Report",
                styles['Title'],
            )
            story.append(title)
            story.append(Spacer(1, 8))
            summary_text = ', '.join(f'{k}: {v}' for k, v in summary.items() if v is not None)
            if summary_text:
                story.append(Paragraph(summary_text, styles['Normal']))
                story.append(Spacer(1, 8))

        headers = payload.get('headers', [])
        rows = payload.get('rows', [])
        table_data = [headers] + [self._flatten(row) for row in rows]
        table = Table(table_data, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4f46e5')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.whitesmoke]),
                ]
            )
        )
        story.append(table)
        doc.build(story)
        return buffer.getvalue()

    @staticmethod
    def _flatten(row: list[Any]) -> list[Any]:
        """Flatten dict/list cells into displayable strings for tabular formats."""
        flattened = []
        for cell in row:
            if isinstance(cell, (dict, list)):
                flattened.append(json.dumps(cell, default=str))
            else:
                flattened.append(cell)
        return flattened
