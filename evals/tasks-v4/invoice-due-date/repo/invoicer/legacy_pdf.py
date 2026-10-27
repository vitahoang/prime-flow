"""PDF export via wkhtmltopdf.

Superseded in 0.7 by printing the HTML invoice from the browser. Nothing
imports this any more; it is kept because the accountant's old script on the
NAS still shells out to `python -c "import invoicer.legacy_pdf ..."`.
"""

import shutil
import subprocess
import tempfile
from pathlib import Path

WKHTMLTOPDF = "wkhtmltopdf"


def available() -> bool:
    return shutil.which(WKHTMLTOPDF) is not None


def html_to_pdf(html: str, out_path: Path, page_size: str = "A4") -> Path:
    if not available():
        raise RuntimeError("wkhtmltopdf is not installed")
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as fh:
        fh.write(html)
        src = fh.name
    subprocess.run(
        [WKHTMLTOPDF, "--quiet", "--page-size", page_size, src, str(out_path)],
        check=True,
    )
    Path(src).unlink(missing_ok=True)
    return out_path


def export_invoice(store, invoice_id: str, out_dir: Path) -> Path:
    from . import clock, render

    inv = store.invoice(invoice_id)
    cust = store.customer_for(inv)
    html = render.render_html(inv, cust, store.payments_for(inv.id), clock.now())
    return html_to_pdf(html, Path(out_dir) / f"{inv.id}.pdf")
