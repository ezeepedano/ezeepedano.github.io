"""
Centralized PDF rendering utility using xhtml2pdf (fast) with
WeasyPrint fallback (slower but more CSS-capable).

All PDF generation across the ERP should use this module's
``render_to_pdf`` function so there is a single, consistent
entry-point for HTML → PDF conversion.
"""
import io
import logging

from django.conf import settings
from django.http import HttpResponse
from django.template.loader import get_template

logger = logging.getLogger(__name__)


def render_to_pdf(template_path, context, filename='report.pdf'):
    """Render a Django HTML template to a PDF HttpResponse.

    Uses xhtml2pdf (pisa) for fast rendering. Falls back to
    WeasyPrint if xhtml2pdf is not installed.

    Parameters
    ----------
    template_path : str
        Path to the Django template (e.g. ``'reports/quotation_pdf.html'``).
    context : dict
        Template context variables.
    filename : str, optional
        The filename suggested to the browser.

    Returns
    -------
    HttpResponse
        A response with ``content_type='application/pdf'``.
    """
    template = get_template(template_path)
    html_string = template.render(context)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{filename}"'

    try:
        # ── Fast path: xhtml2pdf ──
        from xhtml2pdf import pisa

        result_buffer = io.BytesIO()
        pisa_status = pisa.CreatePDF(
            src=html_string,
            dest=result_buffer,
            encoding='utf-8',
            link_callback=_link_callback,
        )

        if pisa_status.err:
            logger.error("xhtml2pdf reported %s errors", pisa_status.err)
            return HttpResponse('Error al generar el PDF.', status=500)

        response.write(result_buffer.getvalue())
        result_buffer.close()

    except ImportError:
        # ── Fallback: WeasyPrint (slower) ──
        try:
            from weasyprint import HTML
            pdf_bytes = HTML(
                string=html_string,
                base_url=str(settings.BASE_DIR),
            ).write_pdf()
            response.write(pdf_bytes)
        except Exception:
            logger.exception("Error generating PDF with WeasyPrint")
            return HttpResponse('Error al generar el PDF.', status=500)
    except Exception:
        logger.exception("Error generating PDF")
        return HttpResponse('Error al generar el PDF.', status=500)

    return response


def _link_callback(uri, rel):
    """Resolve file:// URIs and static/media paths for xhtml2pdf."""
    import os

    # Handle file:// URIs (used for logo_path in templates)
    if uri.startswith('file://'):
        path = uri[7:]
        # On Windows, strip leading slash from /C:/...
        if len(path) > 2 and path[0] == '/' and path[2] == ':':
            path = path[1:]
        return path

    # Handle static files
    if uri.startswith(settings.STATIC_URL):
        path = os.path.join(
            str(settings.BASE_DIR), 'static',
            uri.replace(settings.STATIC_URL, '')
        )
        return path

    # Handle media files
    if settings.MEDIA_URL and uri.startswith(settings.MEDIA_URL):
        path = os.path.join(
            str(settings.MEDIA_ROOT),
            uri.replace(settings.MEDIA_URL, '')
        )
        return path

    return uri
