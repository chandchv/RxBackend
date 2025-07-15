from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.db.models import Q
import json

from ..models import Doctor, Patient, Prescription, PrescriptionTemplate
from labs.models import LabProfile, TestDefinition
from users.models import Lab

@login_required
def diagnosis_suggestions(request):
    """HTMX endpoint for diagnosis suggestions"""
    query = request.POST.get('chief_complaints', '').strip()
    
    if len(query) < 3:
        return HttpResponse('')
    
    # Get common diagnoses based on complaints
    suggestions = [
        'Hypertension',
        'Diabetes Mellitus',
        'Upper Respiratory Tract Infection',
        'Gastroenteritis',
        'Migraine',
        'Anxiety Disorder',
        'Depression',
        'Osteoarthritis',
        'Bronchial Asthma',
        'Urinary Tract Infection'
    ]
    
    # Filter suggestions based on query
    filtered_suggestions = [s for s in suggestions if query.lower() in s.lower()][:5]
    
    html = ''
    for suggestion in filtered_suggestions:
        html += f'''
        <div class="suggestion-item p-2 rounded hover:bg-gray-100 text-sm" 
             onclick="selectDiagnosis('{suggestion}')">
            {suggestion}
        </div>
        '''
    
    return HttpResponse(html)

@login_required
def medicine_suggestions(request):
    """HTMX endpoint for medicine suggestions based on diagnosis"""
    diagnosis = request.POST.get('diagnosis', '').strip()
    
    if len(diagnosis) < 3:
        return HttpResponse('')
    
    # Import the drug suggestions from drug_views
    from .drugs_views import drug_suggestions
    
    # Get medicine suggestions based on diagnosis
    # Common medicine mappings (in real app, this would come from ML model or database)
    medicine_mappings = {
        'hypertension': ['Amlodipine', 'Losartan', 'Metoprolol', 'Hydrochlorothiazide'],
        'diabetes': ['Metformin', 'Glimepiride', 'Insulin', 'Sitagliptin'],
        'infection': ['Amoxicillin', 'Azithromycin', 'Ciprofloxacin', 'Doxycycline'],
        'pain': ['Paracetamol', 'Ibuprofen', 'Diclofenac', 'Tramadol'],
        'fever': ['Paracetamol', 'Ibuprofen', 'Aspirin'],
        'cough': ['Dextromethorphan', 'Guaifenesin', 'Codeine'],
        'headache': ['Paracetamol', 'Ibuprofen', 'Sumatriptan'],
        'anxiety': ['Alprazolam', 'Diazepam', 'Buspirone'],
        'depression': ['Sertraline', 'Fluoxetine', 'Escitalopram'],
        'asthma': ['Salbutamol', 'Budesonide', 'Montelukast']
    }
    
    suggestions = []
    diagnosis_lower = diagnosis.lower()
    
    for key, medicines in medicine_mappings.items():
        if key in diagnosis_lower:
            suggestions.extend(medicines)
    
    # Remove duplicates and limit
    suggestions = list(set(suggestions))[:8]
    
    html = ''
    for medicine in suggestions:
        html += f'''
        <div class="suggestion-item p-2 rounded hover:bg-gray-100 text-sm cursor-pointer" 
             onclick="addMedicineFromSuggestion('{medicine}')">
            <strong>{medicine}</strong>
            <div class="text-xs text-gray-500">Click to add</div>
        </div>
        '''
    
    return HttpResponse(html)

@login_required
def medicine_details(request):
    """HTMX endpoint for medicine details and dosage suggestions"""
    medicine_name = request.POST.get('name', '').strip()
    
    if len(medicine_name) < 2:
        return HttpResponse('')
    
    # Common dosage patterns (in real app, this would come from drug database)
    dosage_patterns = {
        'paracetamol': {'dosage': '500mg', 'frequency': 'Every 6 hours', 'duration': '5 days'},
        'amoxicillin': {'dosage': '500mg', 'frequency': 'Three times daily', 'duration': '7 days'},
        'metformin': {'dosage': '500mg', 'frequency': 'Twice daily', 'duration': 'Lifetime'},
        'amlodipine': {'dosage': '5mg', 'frequency': 'Once daily', 'duration': 'Lifetime'},
        'omeprazole': {'dosage': '20mg', 'frequency': 'Once daily', 'duration': '4 weeks'},
        'vitamin d': {'dosage': '1000 IU', 'frequency': 'Once daily', 'duration': '3 months'},
        'calcium': {'dosage': '500mg', 'frequency': 'Twice daily', 'duration': '3 months'},
        'iron': {'dosage': '100mg', 'frequency': 'Once daily', 'duration': '3 months'}
    }
    
    medicine_lower = medicine_name.lower()
    details = None
    
    for key, pattern in dosage_patterns.items():
        if key in medicine_lower:
            details = pattern
            break
    
    if details:
        html = f'''
        <div class="mt-1 p-2 bg-blue-50 rounded text-xs">
            <div><strong>Suggested:</strong> {details['dosage']} {details['frequency']}</div>
            <div><strong>Duration:</strong> {details['duration']}</div>
        </div>
        '''
    else:
        html = f'''
        <div class="mt-1 p-2 bg-gray-50 rounded text-xs">
            <div>No standard dosage found for {medicine_name}</div>
        </div>
        '''
    
    return HttpResponse(html)

@login_required
def quick_add_content(request):
    """HTMX endpoint for quick add panel content"""
    content_type = request.GET.get('type', '')
    
    if content_type == 'diagnosis':
        return render(request, 'doctor/partials/quick_diagnosis.html')
    elif content_type == 'medicine':
        return render(request, 'doctor/partials/quick_medicine.html')
    elif content_type == 'template':
        return render(request, 'doctor/partials/quick_template.html')
    
    return HttpResponse('Invalid content type')

@login_required
def lab_test_panel(request):
    """HTMX endpoint for lab test selection panel"""
    doctor = Doctor.objects.get(user=request.user)
    
    # Get available labs
    internal_labs = Lab.objects.filter(clinic=doctor.clinic)
    external_labs = LabProfile.objects.filter(is_approved=True)
    
    # Common test panels
    test_panels = {
        'CBC': ['Hemoglobin', 'WBC Count', 'Platelet Count', 'RBC Count'],
        'LFT': ['ALT', 'AST', 'Alkaline Phosphatase', 'Bilirubin'],
        'KFT': ['Creatinine', 'Urea', 'Uric Acid', 'Electrolytes'],
        'Lipid Profile': ['Total Cholesterol', 'HDL', 'LDL', 'Triglycerides'],
        'Diabetes': ['Fasting Blood Sugar', 'HbA1c', 'Post Prandial Sugar'],
        'Thyroid': ['TSH', 'T3', 'T4', 'Free T4']
    }
    
    context = {
        'internal_labs': internal_labs,
        'external_labs': external_labs,
        'test_panels': test_panels
    }
    
    return render(request, 'doctor/partials/lab_test_panel.html', context)

@login_required
def recent_templates(request):
    """HTMX endpoint for recent prescription templates"""
    doctor = Doctor.objects.get(user=request.user)
    templates = PrescriptionTemplate.objects.filter(doctor=doctor).order_by('-created_at')[:5]
    
    return render(request, 'doctor/partials/recent_templates.html', {'templates': templates})

@login_required
def save_template(request):
    """HTMX endpoint for saving prescription template (supports JSON and form POST)"""
    doctor = Doctor.objects.get(user=request.user)
    if request.method == 'POST':
        # Support both JSON and form POST
        if request.content_type == 'application/json':
            try:
                data = json.loads(request.body.decode('utf-8'))
            except Exception as e:
                return JsonResponse({'success': False, 'error': 'Invalid JSON'})
            template_name = data.get('name')
            if not template_name:
                return JsonResponse({'success': False, 'error': 'Template name is required'})
            # Save template
            template, created = PrescriptionTemplate.objects.get_or_create(
                doctor=doctor, name=template_name,
                defaults={'data': data}
            )
            if not created:
                template.data = data
                template.save(update_fields=['data', 'updated_at'])
            return JsonResponse({'success': True, 'id': template.id})
        else:
            template_name = request.POST.get('template_name')
            if not template_name:
                return JsonResponse({'success': False, 'error': 'Template name is required'})
            # Extract form data and save as template
            template_data = {
                'chief_complaints': request.POST.get('chief_complaints', ''),
                'clinical_findings': request.POST.get('clinical_findings', ''),
                'diagnosis': request.POST.get('diagnosis', ''),
                'advice': request.POST.get('advice', ''),
                'medicines': request.POST.getlist('medicines[]'),
                'lab_tests': request.POST.getlist('lab_tests[]'),
            }
            template, created = PrescriptionTemplate.objects.get_or_create(
                doctor=doctor, name=template_name,
                defaults={'data': template_data}
            )
            if not created:
                template.data = template_data
                template.save(update_fields=['data', 'updated_at'])
            return JsonResponse({'success': True, 'id': template.id})
    return JsonResponse({'success': False, 'error': 'Invalid request'})

@login_required
def load_template(request, template_id):
    """HTMX endpoint to load a prescription template as JSON"""
    doctor = Doctor.objects.get(user=request.user)
    try:
        template = PrescriptionTemplate.objects.get(id=template_id, doctor=doctor)
        return JsonResponse({'success': True, 'data': template.data, 'name': template.name})
    except PrescriptionTemplate.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Template not found'})

@login_required
def save_prescription_draft(request):
    """HTMX endpoint for auto-saving prescription draft"""
    if request.method == 'POST':
        # Save draft to session or temporary storage
        request.session['prescription_draft'] = request.POST.dict()
        return JsonResponse({'success': True})
    
    return JsonResponse({'success': False})

@login_required
def search_medicines(request):
    """HTMX endpoint for medicine search using the drug database"""
    query = request.GET.get('query', '').strip()
    
    if len(query) < 2:
        return HttpResponse('')
    
    try:
        from ..models import Drug
        
        # Search in drug database
        suggestions = Drug.objects.filter(
            Q(product_name__icontains=query) |
            Q(salt_composition__icontains=query)
        ).values('product_name', 'salt_composition', 'product_manufactured').distinct()[:10]
        
        html = ''
        for drug in suggestions:
            product_name = drug['product_name']
            salt_composition = drug['salt_composition'] or ''
            manufacturer = drug['product_manufactured'] or ''
            
            html += f'''
            <div class="suggestion-item p-3 rounded hover:bg-gray-100 text-sm cursor-pointer border-b border-gray-200" 
                 onclick="addMedicineFromSuggestion('{product_name}')">
                <div class="font-medium text-gray-900">{product_name}</div>
                {f'<div class="text-xs text-gray-600 mt-1">{salt_composition}</div>' if salt_composition else ''}
                {f'<div class="text-xs text-gray-500 mt-1">Mfr: {manufacturer}</div>' if manufacturer else ''}
            </div>
            '''
        
        if not suggestions:
            html = f'''
            <div class="p-3 text-sm text-gray-500">
                No medicines found for "{query}"
                <div class="mt-2">
                    <button onclick="addMedicineFromSuggestion('{query}')" 
                            class="text-blue-600 hover:text-blue-800 underline">
                        Add "{query}" as custom medicine
                    </button>
                </div>
            </div>
            '''
        
        return HttpResponse(html)
        
    except Exception as e:
        print(f"Error in medicine search: {str(e)}")
        return HttpResponse(f'<div class="p-3 text-sm text-red-500">Error searching medicines: {str(e)}</div>')

@login_required
def patient_history(request, patient_id):
    """HTMX endpoint for patient history sidebar"""
    try:
        patient = Patient.objects.get(id=patient_id)
        prescriptions = Prescription.objects.filter(patient=patient).order_by('-created_at')[:5]
        
        context = {
            'patient': patient,
            'recent_prescriptions': prescriptions
        }
        
        return render(request, 'doctor/partials/patient_history.html', context)
    except Patient.DoesNotExist:
        return HttpResponse('Patient not found')

@login_required
def update_vitals_modal(request, patient_id):
    """HTMX endpoint for vitals update modal"""
    try:
        patient = Patient.objects.get(id=patient_id)
        latest_vitals = patient.vitals.order_by('-created_at').first()
        
        context = {
            'patient': patient,
            'latest_vitals': latest_vitals
        }
        
        return render(request, 'doctor/partials/vitals_modal.html', context)
    except Patient.DoesNotExist:
        return HttpResponse('Patient not found') 