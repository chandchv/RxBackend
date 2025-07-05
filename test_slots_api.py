import os
import sys
import django
import json
from datetime import datetime, timedelta

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "RxBackend.settings")
django.setup()

# Import the needed models and functions
from django.contrib.auth.models import User
from users.models import Doctor, DoctorAvailability, AppointmentSlot
from django.utils import timezone

def test_slots():
    """Test function to check slot generation and API access"""
    try:
        # Get a doctor to test with
        doctor = Doctor.objects.first()
        if not doctor:
            print("No doctors found in the database.")
            return
            
        # Print doctor info
        print(f"Testing with doctor: {doctor.name} (ID: {doctor.id})")
            
        # Check if doctor has availability set
        availability = DoctorAvailability.objects.filter(doctor=doctor, is_available=True)
        if not availability.exists():
            print("Doctor has no availability set.")
            days_with_availability = []
        else:
            days_with_availability = [a.day_of_week for a in availability]
            print(f"Doctor has availability on days: {days_with_availability}")
            
        # Check existing slots
        today = timezone.now().date()
        future_date = today + timedelta(days=30)
        slots = AppointmentSlot.objects.filter(doctor=doctor, date__gte=today, date__lte=future_date)
        print(f"Found {slots.count()} slots between {today} and {future_date}")
        
        # Count slots by date
        slot_dates = {}
        for slot in slots:
            date_str = slot.date.strftime('%Y-%m-%d')
            if date_str in slot_dates:
                slot_dates[date_str] += 1
            else:
                slot_dates[date_str] = 1
                
        print("\nSlots by date:")
        for date_str, count in slot_dates.items():
            weekday = datetime.strptime(date_str, '%Y-%m-%d').date().weekday()
            print(f"  {date_str} ({['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][weekday]}): {count} slots")
                
        # Generate a list of dates to test
        test_dates = []
        for i in range(7):  # Try next 7 days
            date = today + timedelta(days=i)
            if date.weekday() in days_with_availability:
                test_dates.append(date)
                
        if not test_dates:
            print("No valid test dates found. Please set up doctor availability.")
            return
                
        # Try to access the API directly
        from users.views.doctor_views import get_available_slots_api
        from django.http import QueryDict
        from rest_framework.test import APIRequestFactory
        
        factory = APIRequestFactory()
        
        # Test for each date
        for test_date in test_dates[:3]:  # Test only first 3 dates
            date_str = test_date.strftime('%Y-%m-%d')
            print(f"\nTesting API for date: {date_str}")
            
            # Create request with query parameters
            request = factory.get(f'/api/slots/available/?doctor_id={doctor.id}&date={date_str}')
            request.user = User.objects.filter(is_staff=True).first()  # Authenticate with a staff user
            
            # Call the API function directly
            response = get_available_slots_api(request)
            
            # Print the response
            print(f"API Response Status: {response.status_code}")
            data = json.loads(json.dumps(response.data))
            if 'slots' in data:
                print(f"Available slots: {len(data['slots'])}")
                if data['slots']:
                    print("Sample slots:")
                    for slot in data['slots'][:5]:  # Show first 5 slots
                        print(f"  - {slot['time']}")
            else:
                print(f"No slots data in response: {data}")
                
    except Exception as e:
        print(f"Error in test: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_slots()
    print("Test completed.") 