#!/usr/bin/env python
import os
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'RxBackend.settings')
django.setup()

from labs.models import LabOrder
from users.models import LabTest as UserLabTest, Doctor
from labs.models import LabProfile

def check_lab_data():
    print("=== Lab Profiles ===")
    for lp in LabProfile.objects.all():
        print(f"ID: {lp.id}, Name: {lp.name}, User: {lp.user.username}, Approved: {lp.is_approved}")
    
    print("\n=== Lab Orders ===")
    for lo in LabOrder.objects.all():
        doctor_name = lo.doctor.name if hasattr(lo.doctor, 'name') else (lo.doctor.get_full_name() if lo.doctor else "None")
        if not lo.patient:
            print(f"[WARNING] LabOrder ID {lo.id} has no patient!")
            patient_name = "None"
        else:
            patient_name = lo.patient.get_full_name()
        print(f"Order ID: {lo.id}, Lab: {lo.chosen_lab.name if lo.chosen_lab else 'None'}, Doctor: {doctor_name}, Patient: {patient_name}")
    
    print("\n=== Lab Tests (from users app) ===")
    for lt in UserLabTest.objects.all():
        if not lt.prescription:
            print(f"[WARNING] LabTest ID {lt.id} has no prescription!")
            continue
        external_lab = lt.prescription.external_lab.name if hasattr(lt.prescription, 'external_lab') and lt.prescription.external_lab else "None"
        doctor = getattr(lt.prescription, 'doctor', None)
        if doctor is None:
            doctor_name = "None"
        elif hasattr(doctor, 'name'):
            doctor_name = doctor.name
        elif hasattr(doctor, 'get_full_name'):
            doctor_name = doctor.get_full_name()
        else:
            doctor_name = str(doctor)
        print(f"Test ID: {lt.id}, External Lab: {external_lab}, Doctor: {doctor_name}")
    
    print("\n=== Doctors ===")
    for doctor in Doctor.objects.all():
        print(f"Doctor ID: {doctor.id}, Name: {doctor.name}, User: {doctor.user.username if doctor.user else 'None'}")

if __name__ == '__main__':
    check_lab_data() 