from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa
from ..models import Clinic, LabTestPrescription, Prescription
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect
from io import BytesIO
from ..models import Doctor
from ..models import PatientVitals
from django.conf import settings
import os
from ..models import LabTest
from datetime import date
from django.templatetags.static import static
from django.contrib.staticfiles import finders

def calculate_age(birth_date):
    today = date.today()
    try:
        age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
        return age
    except (TypeError, AttributeError):
        return ''

def fetch_resources(uri, rel):
    """
    Convert HTML URIs to absolute system paths so xhtml2pdf can access those resources
    """
    try:
        # Handle static files
        if uri.startswith(settings.STATIC_URL):
            path = uri.replace(settings.STATIC_URL, '')
            result = finders.find(path)
            if result:
                return os.path.abspath(result)

        # Handle media files
        if uri.startswith(settings.MEDIA_URL):
            path = uri.replace(settings.MEDIA_URL, '')
            media_path = os.path.join(settings.MEDIA_ROOT, path)
            if os.path.exists(media_path):
                return os.path.abspath(media_path)

        # If the URI is a URL, leave it unchanged
        if uri.startswith('http://') or uri.startswith('https://'):
            return uri

        # Convert URI to absolute filepath
        if uri.startswith('/'):
            path = uri[1:]
        else:
            path = uri

        # Try both STATIC_ROOT and MEDIA_ROOT
        for root in [settings.STATIC_ROOT, settings.MEDIA_ROOT]:
            abs_path = os.path.join(root, path)
            if os.path.exists(abs_path):
                return abs_path

        print(f"Resource not found: {uri}")
        return None

    except Exception as e:
        print(f"Error in fetch_resources: {str(e)}")
        return None

def render_to_pdf(template_src, context_dict={}):
    template = get_template(template_src)
    html = template.render(context_dict)
    result = BytesIO()
    
    # Add custom options for PDF generation
    pdf_options = {
        'page-size': 'A4',
        'margin-top': '0.75in',
        'margin-right': '0.75in',
        'margin-bottom': '0.75in',
        'margin-left': '0.75in',
        'encoding': 'UTF-8',
        'no-outline': None,
    }
    
    pisa_status = pisa.CreatePDF(
        html, 
        dest=result,
        link_callback=fetch_resources,
        show_error_as_pdf=True
    )
    
    if not pisa_status.err:
        return HttpResponse(result.getvalue(), content_type='application/pdf')
    return None

@login_required
def generate_prescription_pdf(request, pk, format_type='digital'):
    try:
        prescription = get_object_or_404(
            Prescription.objects.select_related(
                'doctor',
                'doctor__clinic',
                'patient'
            ).prefetch_related('items'),
            id=pk
        )

        # Get patient vitals
        vitals = PatientVitals.objects.filter(
            patient=prescription.patient
        ).order_by('-created_at').first()

        # First get lab prescriptions for this patient on the same date
        lab_prescriptions = LabTestPrescription.objects.filter(
            patient=prescription.patient,
            doctor__id=prescription.doctor.user.id,  # Use the doctor's user ID
            prescription_date__date=prescription.date  # Match on the prescription date
        )
        
        # Then gather all lab tests from these prescriptions
        lab_tests = []
        for lab_prescription in lab_prescriptions:
            # This correctly uses the ForeignKey relationship from LabTest to LabTestPrescription
            tests = LabTest.objects.filter(prescription=lab_prescription)
            lab_tests.extend(tests)

        # Calculate patient age
        patient_age = calculate_age(prescription.patient.date_of_birth)

        # Get clinic logo URL if it exists
        clinic = prescription.doctor.clinic
        logo_url = clinic.logo.url if clinic.logo else None

        # Prepare the context for the template
        context = {
            'prescription': prescription,
            'vitals': vitals,
            'lab_tests': lab_tests,
            'clinic': clinic,
            'logo_url': logo_url,
            'patient_age': patient_age,
            'format_type': format_type,  # 'digital' or 'letterhead'
            'STATIC_URL': settings.STATIC_URL,
            'MEDIA_URL': settings.MEDIA_URL,
        }

        # Choose template based on format type
        template_name = 'doctor/prescription_pdf_letterhead.html' if format_type == 'letterhead' else 'doctor/prescription_pdf.html'
        
        # Get the template
        template = get_template(template_name)
        html = template.render(context)

        # Create PDF
        result = BytesIO()
        pdf = pisa.pisaDocument(
            BytesIO(html.encode("UTF-8")), 
            result,
            link_callback=fetch_resources,
            show_error_as_pdf=True
        )
        
        if not pdf.err:
            response = HttpResponse(result.getvalue(), content_type='application/pdf')
            filename = f"prescription_{pk}_{'letterhead' if format_type == 'letterhead' else 'digital'}.pdf"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response

        return HttpResponse('Error generating PDF', status=500)

    except Exception as e:
        print(f"Error generating prescription PDF: {str(e)}")
        messages.error(request, f'Error generating PDF: {str(e)}')
        return redirect('users:prescription_detail', pk=pk)