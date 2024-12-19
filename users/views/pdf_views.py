from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa
from ..models import Prescription
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect
from io import BytesIO
from ..models import Doctor
from ..models import PatientVitals
from django.conf import settings
import os

def render_to_pdf(template_src, context_dict={}):
    template = get_template(template_src)
    html = template.render(context_dict)
    result = HttpResponse(content_type='application/pdf')
    pisa_status = pisa.CreatePDF(html, dest=result)
    if pisa_status.err:
        return HttpResponse('We had some errors <pre>' + html + '</pre>')
    return result

@login_required 
def generate_prescription_pdf(request, pk):
    try:
        doctor = Doctor.objects.get(user=request.user)
        prescription = get_object_or_404(
            Prescription.objects.select_related('vitals'),
            id=pk, 
            doctor=doctor
        )
        
        # Get vitals
        vitals = PatientVitals.objects.filter(
            patient=prescription.patient,
            recorded_at__lte=prescription.created_at
        ).order_by('-recorded_at').first()
        
        # Handle logo path
        logo_path = None
        if doctor.clinic and doctor.clinic.logo:
            # Convert Windows path to forward slashes and remove drive letter
            logo_path = str(doctor.clinic.logo.path).replace('\\', '/')
            if ':' in logo_path:  # Remove drive letter if present
                logo_path = logo_path.split(':', 1)[1]
            logo_path = f"file://{logo_path}"
            print(f"Processed logo path: {logo_path}")
        
        context = {
            'prescription': prescription,
            'doctor': doctor,
            'vitals': vitals,
            'logo_path': logo_path
        }
        
        template = get_template('doctor/prescription_pdf.html')
        html = template.render(context)
        result = BytesIO()
        
        # Configure PDF options
        pdf = pisa.pisaDocument(
            BytesIO(html.encode("UTF-8")), 
            result,
            encoding='utf-8',
            link_callback=fetch_resources  # Add this line
        )
        
        if not pdf.err:
            response = HttpResponse(result.getvalue(), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="prescription_{pk}.pdf"'
            return response
        
        print(f"PDF Error: {pdf.err}")
        return HttpResponse('Error generating PDF', status=400)
        
    except Exception as e:
        print(f"Exception: {str(e)}")
        messages.error(request, str(e))
        return redirect('users:prescription_detail', pk=pk)

# Add this function to handle resource fetching
def fetch_resources(uri, rel):
    """
    Convert HTML URIs to absolute system paths so xhtml2pdf can access those resources
    """
    if uri.startswith('file:///'):
        path = uri[8:]  # Remove 'file:///'
    elif uri.startswith('file://'):
        path = uri[7:]  # Remove 'file://'
    else:
        path = uri

    # Convert path to absolute path
    if not os.path.isabs(path):
        base_dir = os.path.join(settings.MEDIA_ROOT)
        path = os.path.join(base_dir, path)

    return path