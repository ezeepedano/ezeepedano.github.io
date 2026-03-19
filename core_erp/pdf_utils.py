"""
Centralized PDF rendering utility using WeasyPrint.

All PDF generation across the ERP should use this module's
``render_to_pdf`` function so there is a single, consistent
entry-point for HTML → PDF conversion.
"""
import logging

from django.conf import settings
from django.http import HttpResponse
from django.template.loader import get_template

logger = logging.getLogger(__name__)


def render_to_pdf(template_path, context, filename='report.pdf'):
    """Render a Django HTML template to a PDF HttpResponse.

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
        from weasyprint import HTML
        pdf_bytes = HTML(
            string=html_string,
            base_url=str(settings.BASE_DIR),
        ).write_pdf()
        response.write(pdf_bytes)
    except Exception:
        logger.exception("Error generating PDF with WeasyPrint")
        return HttpResponse('Error al generar el PDF.', status=500)

    return response
