document.addEventListener('DOMContentLoaded', function() {
    // Calendar initialization
    var calendarEl = document.getElementById('calendar');
    if (!calendarEl) return; // Exit if calendar element doesn't exist
    
    var tooltipEl = document.getElementById('appointment-tooltip');
    var loadingEl = document.getElementById('calendar-loading');
    
    // Show loading indicator
    function showLoading() {
        if (loadingEl) {
            loadingEl.classList.remove('hidden');
        }
    }
    
    // Hide loading indicator
    function hideLoading() {
        if (loadingEl) {
            loadingEl.classList.add('hidden');
        }
    }
    
    // Calendar instance
    var calendar = new FullCalendar.Calendar(calendarEl, {
        initialView: 'dayGridMonth',
        headerToolbar: {
            left: 'prev,next today',
            center: 'title',
            right: ''
        },
        views: {
            timeGridWeek: {
                slotMinTime: '08:00:00',
                slotMaxTime: '20:00:00',
            },
            timeGridDay: {
                slotMinTime: '08:00:00',
                slotMaxTime: '20:00:00',
            }
        },
        dayMaxEventRows: true,
        moreLinkClick: 'day',
        slotDuration: '00:15:00',
        allDaySlot: false,
        height: 'auto',
        contentHeight: 650,
        firstDay: 1, // Start week on Monday
        nowIndicator: true,
        businessHours: {
            daysOfWeek: [1, 2, 3, 4, 5, 6], // Monday - Saturday
            startTime: '09:00',
            endTime: '18:00',
        },
        eventDisplay: 'block',
        eventTimeFormat: {
            hour: 'numeric',
            minute: '2-digit',
            meridiem: 'short'
        },
        events: function(info, successCallback, failureCallback) {
            showLoading();
            
            var doctorId = $('#doctor_filter').val();
            var url = calendarEl.dataset.calendarEventsUrl;
            if (doctorId) {
                url += '?doctor_id=' + doctorId;
            }
            
            // Add date range parameters
            if (info.startStr && info.endStr) {
                const separator = url.includes('?') ? '&' : '?';
                url += `${separator}start=${info.startStr}&end=${info.endStr}`;
            }
            
            $.ajax({
                url: url,
                type: 'GET',
                dataType: 'json',
                success: function(response) {
                    console.log('Calendar data:', response);
                    
                    // Check if response has events property (backend returns {events: [...], available_slots: [...]})
                    var eventData = response.events || response;
                    
                    if (!Array.isArray(eventData)) {
                        console.error('Invalid event data format:', eventData);
                        failureCallback('Invalid event data format');
                        hideLoading();
                        return;
                    }
                    
                    var events = eventData.map(function(event) {
                        // Check if there's patient and doctor info
                        let title = event.title || '';
                        if (event.patient && event.doctor) {
                            title = `${event.patient} - Dr. ${event.doctor}`;
                        }

                        return {
                            id: event.id,
                            title: title,
                            start: event.start,
                            end: event.end,
                            backgroundColor: getStatusColor(event.status),
                            borderColor: getStatusColor(event.status),
                            classNames: ['appointment-event'],
                            borderLeftColor: getDarkerColor(event.status),
                            extendedProps: {
                                status: event.status || 'Unknown',
                                patient: event.patient || 'Unknown Patient',
                                doctor: event.doctor || 'Unknown Doctor',
                                reason: event.reason || '',
                                token: event.token_number || ''
                            }
                        };
                    });
                    
                    // Add available slots if they exist in the response
                    if (response.available_slots && Array.isArray(response.available_slots)) {
                        var availableSlots = response.available_slots.map(function(slot) {
                            return {
                                id: slot.id,
                                title: slot.title,
                                start: slot.start,
                                end: slot.end,
                                rendering: 'background',
                                backgroundColor: '#e8f5e9',
                                classNames: ['available-slot']
                            };
                        });
                        
                        // Only show available slots in day or week view
                        var currentView = calendar.view.type;
                        if (currentView !== 'dayGridMonth') {
                            events = events.concat(availableSlots);
                        }
                    }
                    
                    successCallback(events);
                    hideLoading();
                },
                error: function(xhr, status, error) {
                    console.error('Calendar API error:', error);
                    failureCallback(error);
                    hideLoading();
                    
                    // Show error message to user
                    var errorMessage = 'Failed to load calendar data. Please try again.';
                    if (xhr.responseJSON && xhr.responseJSON.error) {
                        errorMessage = xhr.responseJSON.error;
                    }
                    
                    // Add error message to calendar
                    var errorDiv = document.createElement('div');
                    errorDiv.className = 'bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded my-4';
                    errorDiv.innerHTML = `<p>${errorMessage}</p>`;
                    
                    calendarEl.parentNode.insertBefore(errorDiv, calendarEl);
                    
                    // Remove error after 5 seconds
                    setTimeout(function() {
                        if (errorDiv.parentNode) {
                            errorDiv.parentNode.removeChild(errorDiv);
                        }
                    }, 5000);
                }
            });
        },
        eventContent: function(arg) {
            let timeText = arg.timeText;
            let titleText = arg.event.title;

            // Use patient name if available, otherwise use the title
            let patient = arg.event.extendedProps.patient || titleText;
            
            return {
                html: `
                    <div class="event-content">
                        <div class="fc-event-time">${timeText}</div>
                        <div class="fc-event-title">${patient}</div>
                    </div>
                `
            };
        },
        eventClick: function(info) {
            // Navigate to appointment detail view - handle both regular and available slots
            if (info.event.id && !info.event.id.startsWith('available_')) {
                // Use the helper function if available, otherwise fall back to direct URL construction
                if (window.getAppointmentDetailUrl) {
                    window.location.href = window.getAppointmentDetailUrl(info.event.id);
                } else {
                    // Fallback to the previous approach
                    const baseUrl = window.APPOINTMENT_BASE_URL || 
                                  calendarEl.dataset.appointmentBaseUrl || 
                                  '/staff/appointments/';
                    
                    const url = baseUrl + (baseUrl.endsWith('/') ? '' : '/') + info.event.id + '/';
                    window.location.href = url;
                }
            }
        },
        eventMouseEnter: function(info) {
            var event = info.event;
            var start = formatTime(event.start);
            var end = event.end ? formatTime(event.end) : '';

            var content = `
                <div class="tooltip-heading">${event.extendedProps.patient}</div>

                <div class="tooltip-detail">
                    <i class="fas fa-clock"></i>
                    <span>${start}${end ? ' - ' + end : ''}</span>
                </div>

                <div class="tooltip-detail">
                    <i class="fas fa-user-md"></i>
                    <span>Dr. ${event.extendedProps.doctor}</span>
                </div>

                <div class="tooltip-detail">
                    <i class="fas fa-tag"></i>
                    <span>Status: ${event.extendedProps.status}</span>
                </div>

                ${event.extendedProps.token ? `
                <div class="tooltip-detail">
                    <i class="fas fa-hashtag"></i>
                    <span>Token: #${event.extendedProps.token}</span>
                </div>` : ''}

                ${event.extendedProps.reason ? `
                <div class="tooltip-detail">
                    <i class="fas fa-comment"></i>
                    <span>Reason: ${event.extendedProps.reason}</span>
                </div>` : ''}

                <div class="tooltip-footer">
                    Click to view appointment details
                </div>
            `;

            tooltipEl.innerHTML = content;
            tooltipEl.style.display = 'block';

            var rect = info.el.getBoundingClientRect();
            tooltipEl.style.top = rect.bottom + window.scrollY + 5 + 'px';
            tooltipEl.style.left = rect.left + window.scrollX + 'px';
        },
        eventMouseLeave: function() {
            tooltipEl.style.display = 'none';
        },
        // Show loading when view changes
        loading: function(isLoading) {
            if (isLoading) {
                showLoading();
            } else {
                hideLoading();
            }
        }
    });

    calendar.render();

    // Handle doctor filter change
    $('#doctor_filter').change(function() {
        calendar.refetchEvents();
    });

    // Handle view control buttons
    document.querySelectorAll('#calendar-view-control button').forEach(button => {
        button.addEventListener('click', function() {
            // Update active class
            document.querySelectorAll('#calendar-view-control button').forEach(btn => {
                btn.classList.remove('active');
            });
            this.classList.add('active');

            // Change calendar view
            calendar.changeView(this.dataset.view);
        });
    });

    // Helper functions
    function getStatusColor(status) {
        switch (status ? status.toUpperCase() : '') {
            case 'SCHEDULED': return '#e3f2fd';
            case 'COMPLETED': return '#e0f2f1';
            case 'CANCELLED': return '#ffebee';
            case 'IN_PROGRESS': return '#fff3e0';
            case 'PENDING': return '#f3e5f5';
            default: return '#e8eaf6';
        }
    }

    function getDarkerColor(status) {
        switch (status ? status.toUpperCase() : '') {
            case 'SCHEDULED': return '#1976d2';
            case 'COMPLETED': return '#00897b';
            case 'CANCELLED': return '#e53935';
            case 'IN_PROGRESS': return '#fb8c00';
            case 'PENDING': return '#8e24aa';
            default: return '#3949ab';
        }
    }

    function formatTime(date) {
        return new Date(date).toLocaleTimeString('en-US', {
            hour: 'numeric',
            minute: '2-digit',
            hour12: true
        });
    }
});
