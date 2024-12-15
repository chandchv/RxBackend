from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa
from ..models import Prescription
from django.shortcuts import get_object_or_404

def render_to_pdf(template_src, context_dict={}):
    template = get_template(template_src)
    html = template.render(context_dict)
    result = HttpResponse(content_type='application/pdf')
    pisa_status = pisa.CreatePDF(html, dest=result)
    if pisa_status.err:
        return HttpResponse('We had some errors <pre>' + html + '</pre>')
    return result

def generate_prescription_pdf(request, prescription_id):
    prescription = get_object_or_404(Prescription, id=prescription_id)
    pdf = render_to_pdf('prescription_template.html', {'prescription': prescription})
    return pdf 