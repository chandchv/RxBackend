import os
import sys
import django
from datetime import datetime, timedelta
import traceback

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "RxBackend.settings")
django.setup()

# Import the needed models and functions
from django.contrib.auth.models import User
from users.models import Doctor, DoctorAvailability, AppointmentSlot
from django.utils import timezone

def test_generate_slots():
    """Test function to diagnose slot generation issues"""
    try:
        print("Starting slot generation test...")
        
        # Get a doctor to test with
        doctor = Doctor.objects.first()
        if not doctor:
            print("No doctors found in the database.")
            return
            
        # Print doctor info
        print(f"Testing with doctor: {doctor.name} (ID: {doctor.id})")
        
        # Get availability records
        availabilities = DoctorAvailability.objects.filter(doctor=doctor, is_available=True)
        if not availabilities.exists():
            print("No availability records found for this doctor.")
            return
            
        print(f"Found {availabilities.count()} availability records:")
        
        # Print all availability records
        for idx, avail in enumerate(availabilities):
            print(f"{idx+1}. Day: {avail.get_day_of_week_display()}, " 
                  f"Start: {avail.start_time}, End: {avail.end_time}, "
                  f"Is Available: {avail.is_available}")
        
        # Generate slots for a test date
        today = timezone.now().date()
        test_date = today + timedelta(days=2)
        
        # Check if there are multiple availability records for the same day
        day_of_week = test_date.weekday()
        day_availabilities = availabilities.filter(day_of_week=day_of_week)
        
        if day_availabilities.count() > 1:
            print(f"WARNING: Found {day_availabilities.count()} availability records for {test_date.strftime('%A')}:")
            for idx, avail in enumerate(day_availabilities):
                print(f"  {idx+1}. {avail.start_time} - {avail.end_time}")
            
            print("\nTesting slot generation with first availability record:")
        elif day_availabilities.count() == 0:
            print(f"No availability found for {test_date.strftime('%A')}. Trying another day.")
            # Try to find a day with availability
            for days_ahead in range(2, 8):
                alt_date = today + timedelta(days=days_ahead)
                alt_day = alt_date.weekday()
                alt_availabilities = availabilities.filter(day_of_week=alt_day)
                if alt_availabilities.exists():
                    print(f"Found availability for {alt_date.strftime('%A')} ({alt_date})")
                    test_date = alt_date
                    day_availabilities = alt_availabilities
                    break
        
        if not day_availabilities.exists():
            print("Could not find any day with availability.")
            return
            
        # Use the first availability record for the test date
        test_availability = day_availabilities.first()
        print(f"\nGenerating slots for {test_date} using availability: "
              f"{test_availability.start_time} - {test_availability.end_time}")
        
        # Generate slots
        slots = test_availability.generate_slots(test_date)
        
        # Print results
        print(f"\nGenerated {len(slots)} slots:")
        for idx, slot in enumerate(slots[:10]):  # Print first 10 slots
            print(f"  {idx+1}. {slot.strftime('%H:%M')}")
        
        if len(slots) > 10:
            print(f"  ... and {len(slots) - 10} more slots")
            
        # Try to create actual AppointmentSlot records
        print("\nCreating AppointmentSlot records for test...")
        
        # Delete any existing slots for this test
        existing = AppointmentSlot.objects.filter(doctor=doctor, date=test_date)
        if existing.exists():
            print(f"Deleting {existing.count()} existing slots for {test_date}")
            existing.delete()
        
        created_count = 0
        for slot_time in slots:
            try:
                slot = AppointmentSlot.objects.create(
                    doctor=doctor,
                    date=test_date,
                    start_time=slot_time.time(),
                    end_time=(slot_time + timedelta(minutes=10)).time(),
                    is_booked=False
                )
                created_count += 1
            except Exception as e:
                print(f"Error creating slot at {slot_time.time()}: {str(e)}")
                
        print(f"\nSuccessfully created {created_count} appointment slots for {test_date}")
        
        # Finally, test the API endpoint
        from users.views.doctor_views import get_available_slots_api
        from django.http import QueryDict
        from rest_framework.test import APIRequestFactory
        
        factory = APIRequestFactory()
        date_str = test_date.strftime('%Y-%m-%d')
        print(f"\nTesting API for date: {date_str}")
        
        # Create request with query parameters
        request = factory.get(f'/api/slots/available/?doctor_id={doctor.id}&date={date_str}')
        request.user = User.objects.filter(is_staff=True).first()  # Authenticate with a staff user
        
        # Call the API function directly
        response = get_available_slots_api(request)
        
        # Print the response
        print(f"API Response Status: {response.status_code}")
        if hasattr(response, 'data'):
            import json
            data = json.loads(json.dumps(response.data))
            if 'slots' in data:
                print(f"Available slots from API: {len(data['slots'])}")
                if data['slots']:
                    print("Sample slots:")
                    for slot in data['slots'][:5]:  # Show first 5 slots
                        print(f"  - {slot['time']}")
            else:
                print(f"No slots data in response: {data}")
        
        print("\nTest completed successfully!")
                
    except Exception as e:
        print(f"Error in test: {str(e)}")
        traceback.print_exc()

if __name__ == "__main__":
    test_generate_slots() 