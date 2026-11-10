# Data Model (EBS-shaped, simplified)

| Table | Key columns | EBS equivalent |
|---|---|---|
| suppliers | supplier_id, supplier_name, site, *bank_account*, *tax_id* | AP_SUPPLIERS / sites / IBY bank accounts |
| po_headers | po_id, supplier_id, currency, buyer | PO_HEADERS_ALL |
| po_lines | po_id, line_num, unit_price, qty_ordered, match_type | PO_LINES_ALL + PO_LINE_LOCATIONS_ALL |
| receipts | receipt_id, po_id, line_num, qty_received, receipt_date | RCV_TRANSACTIONS |
| invoices | invoice_id, invoice_num, supplier_id, invoice_date, amount, status, description | AP_INVOICES_ALL |
| invoice_lines | invoice_id, line_num, po_id, po_line_num, qty_billed, unit_price | AP_INVOICE_LINES_ALL / distributions |
| holds | invoice_id, hold_code, hold_date | AP_HOLDS_ALL |

*Italic* columns are sensitive. No tool selects them; `masking.py` is a second safety net.
Money is stored as TEXT in SQLite and DECIMAL(18,4) in DuckDB/Delta, and always handled as `Decimal` in Python.
