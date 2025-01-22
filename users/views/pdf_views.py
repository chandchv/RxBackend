from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa
from ..models import Clinic, Prescription
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
        
        # Get vitals - using created_at instead of recorded_at
        vitals = PatientVitals.objects.filter(
            patient=prescription.patient,
            created_at__lte=prescription.created_at
        ).order_by('-created_at').first()
        
        # Handle logo path
        logo_path = None
        if doctor.clinic and doctor.clinic.logo:
            try:
                # Get the absolute URL of the logo
                logo_path = request.build_absolute_uri(doctor.clinic.logo.url)
            except Exception as e:
                print(f"Logo path error: {str(e)}")
                logo_path = None
        
        context = {
            'prescription': prescription,
            'doctor': doctor,
            'vitals': vitals,
            'logo_path': logo_path,
            'MEDIA_URL': settings.MEDIA_URL,
            'BASE_DIR': settings.BASE_DIR,
        }
        
        print(f"Context data: vitals={vitals}, logo_path={logo_path}")  # Debug print
        
        template = get_template('doctor/prescription_pdf.html')
        html = template.render(context)
        result = BytesIO()
        
        # Configure PDF options
        pdf = pisa.pisaDocument(
            BytesIO(html.encode("UTF-8")), 
            result,
            encoding='utf-8',
            link_callback=fetch_resources
        )
        
        if not pdf.err:
            response = HttpResponse(result.getvalue(), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="prescription_{pk}.pdf"'
            return response
        
        print(f"PDF Error: {pdf.err}")
        return HttpResponse('Error generating PDF', status=400)
        
    except Exception as e:
        print(f"Exception in generate_prescription_pdf: {str(e)}")
        print(f"Prescription ID: {pk}")  # Debug print
        print(f"Doctor: {doctor}")  # Debug print
        messages.error(request, str(e))
        return redirect('users:prescription_detail', pk=pk)

def fetch_resources(uri, rel):
    """
    Convert HTML URIs to absolute system paths so xhtml2pdf can access those resources
    """
    try:
        # If the URI is a URL, leave it unchanged
        if uri.startswith('http://') or uri.startswith('https://'):
            return uri

        # Convert URI to absolute filepath
        if uri.startswith('/'):
            path = uri[1:]  # Remove leading slash
        else:
            path = uri

        # Join with MEDIA_ROOT for media files
        abs_path = os.path.join(settings.MEDIA_ROOT, path)
        
        # Ensure the file exists
        if not os.path.exists(abs_path):
            print(f"Resource not found: {abs_path}")
            return None

        return abs_path

    except Exception as e:
        print(f"Error in fetch_resources: {str(e)}")
        return None