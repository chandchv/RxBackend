document.addEventListener('DOMContentLoaded', function() {
    // Initialize calendar if it exists on the page
    if (document.getElementById('calendar')) {
        initializeCalendar();
    }
    
    // Initialize calendar view control
    const viewControl = document.getElementById('calendar-view-control');
    if (viewControl) {
        const viewButtons = viewControl.querySelectorAll('button');
        viewButtons.forEach(button => {
            button.addEventListener('click', function() {
                // Remove active class from all buttons
                viewButtons.forEach(btn => btn.classList.remove('active'));
                // Add active class to clicked button
                this.classList.add('active');
                // Change calendar view
                const view = this.getAttribute('data-view');
                calendar.changeView(view);
            });
        });
    }
});

let calendar;
let appointmentTooltip;

function initializeCalendar() {
    const calendarEl = document.getElementById('calendar');
    const loadingEl = document.getElementById('calendar-loading');
    appointmentTooltip = document.getElementById('appointment-tooltip');
    
    if (!calendarEl) return;
    
    // Show loading indicator
    if (loadingEl) {
        loadingEl.classList.remove('hidden');
    }
    
    // Get calendar events URL from data attribute
    const eventsUrl = calendarEl.getAttribute('data-calendar-events-url');
    
    // Check if a selected date is available from the window object
    let initialDate = null;
    if (window.SELECTED_DATE) {
        initialDate = window.SELECTED_DATE;
    }
    
    // Initialize FullCalendar
    calendar = new FullCalendar.Calendar(calendarEl, {
        initialView: 'dayGridMonth',
        initialDate: initialDate,
        headerToolbar: {
            left: 'prev,next today',
            center: 'title',
            right: 'dayGridMonth,timeGridWeek,timeGridDay'
        },
        themeSystem: 'standard',
        allDaySlot: false,
        slotMinTime: '08:00:00',
        slotMaxTime: '20:00:00',
        height: 'auto',
        handleWindowResize: true,
        events: function(info, successCallback, failureCallback) {
            // Show loading indicator
            if (loadingEl) {
                loadingEl.classList.remove('hidden');
            }
            
            // Fetch events for the date range
            fetch(`${eventsUrl}?start=${info.startStr}&end=${info.endStr}`)
                .then(response => {
                    if (!response.ok) {
                        throw new Error('Network response was not ok');
                    }
                    return response.json();
                })
                .then(data => {
                    // Process events for display
                    const processedEvents = data.events.map(event => {
                        if (event.eventType === 'appointment') {
                            // Process regular appointment events
                            const bgColor = getStatusColor(event.status);
                            return {
                                ...event,
                                backgroundColor: bgColor,
                                borderColor: bgColor,
                                textColor: getTextColor(event.status),
                                classNames: ['appointment-event']
                            };
                        } else if (event.eventType === 'availabilitySummary') {
                            // Process availability summary events
                            return {
                                ...event,
                                classNames: ['availability-summary-event'],
                                display: 'background'
                            };
                        }
                        return event;
                    });
                    
                    // Hide loading indicator
                    if (loadingEl) {
                        loadingEl.classList.add('hidden');
                    }
                    
                    // Return all events
                    successCallback(processedEvents);
                })
                .catch(error => {
                    console.error('Error loading events:', error);
                    failureCallback(error);
                    
                    // Hide loading indicator
                    if (loadingEl) {
                        loadingEl.classList.add('hidden');
                    }
                });
        },
        eventMouseEnter: function(mouseEnterInfo) {
            const event = mouseEnterInfo.event;
            const eventEl = mouseEnterInfo.el;
            
            if (event.extendedProps.eventType === 'appointment') {
                // Show appointment tooltip
                showAppointmentTooltip(event, eventEl);
            } else if (event.extendedProps.eventType === 'availabilitySummary') {
                // Show availability summary tooltip
                showAvailabilityTooltip(event, eventEl);
            }
        },
        eventMouseLeave: function() {
            hideAppointmentTooltip();
        },
        eventClick: function(clickInfo) {
            const event = clickInfo.event;
            
            if (event.extendedProps.eventType === 'appointment') {
                // Navigate to appointment detail
                window.location.href = getAppointmentDetailUrl(event.id);
            } else if (event.extendedProps.eventType === 'availabilitySummary') {
                // Show day view for the selected date
                calendar.changeView('timeGridDay', event.start);
            }
        }
    });
    
    calendar.render();
}

function getStatusColor(status) {
    switch (status) {
        case 'SCHEDULED':
        case 'CONFIRMED':
            return '#3b82f6'; // blue-500
        case 'COMPLETED':
            return '#10b981'; // green-500
        case 'CANCELLED':
            return '#ef4444'; // red-500
        case 'PENDING':
            return '#f59e0b'; // amber-500
        case 'NO_SHOW':
            return '#6b7280'; // gray-500
        case 'RESCHEDULED':
            return '#8b5cf6'; // purple-500
        default:
            return '#3b82f6'; // blue-500
    }
}

function getTextColor(status) {
    // Most status colors are dark enough to use white text
    return '#ffffff';
}

function showAppointmentTooltip(event, eventEl) {
    if (!appointmentTooltip) return;
    
    // Get event data
    const title = event.title;
    const status = event.extendedProps.status;
    const patient = event.extendedProps.patient;
    const reason = event.extendedProps.reason;
    const doctor = event.extendedProps.doctor;
    const tokenNumber = event.extendedProps.token_number;
    
    // Format time
    const startTime = event.start ? new Date(event.start).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) : '';
    const endTime = event.end ? new Date(event.end).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) : '';
    const timeDisplay = startTime + (endTime ? ' - ' + endTime : '');
    
    // Build tooltip HTML
    const tooltipHtml = `
        <div class="tooltip-heading">${patient}</div>
        <div class="tooltip-detail"><i class="fas fa-clock"></i> ${timeDisplay}</div>
        <div class="tooltip-detail"><i class="fas fa-user-md"></i> ${doctor}</div>
        ${reason ? `<div class="tooltip-detail"><i class="fas fa-comment-medical"></i> ${reason}</div>` : ''}
        ${tokenNumber ? `<div class="tooltip-detail"><i class="fas fa-hashtag"></i> Token #${tokenNumber}</div>` : ''}
        <div class="tooltip-detail">
            <i class="fas fa-circle" style="color: ${getStatusColor(status)}"></i>
            ${status}
        </div>
        <div class="tooltip-footer">Click for details</div>
    `;
    
    // Update tooltip content
    appointmentTooltip.innerHTML = tooltipHtml;
    
    // Position the tooltip
    positionTooltip(eventEl);
}

function showAvailabilityTooltip(event, eventEl) {
    if (!appointmentTooltip) return;
    
    // Get event data
    const availableCount = event.extendedProps.available_count;
    const startTime = event.extendedProps.start_time;
    const endTime = event.extendedProps.end_time;
    const date = event.start ? new Date(event.start).toLocaleDateString([], {weekday: 'long', month: 'long', day: 'numeric'}) : '';
    
    // Build tooltip HTML
    const tooltipHtml = `
        <div class="tooltip-heading">${date}</div>
        <div class="tooltip-detail"><i class="fas fa-calendar-check"></i> ${availableCount} slots available</div>
        <div class="tooltip-detail"><i class="fas fa-clock"></i> ${startTime} - ${endTime}</div>
        <div class="tooltip-footer">Click to view day schedule</div>
    `;
    
    // Update tooltip content
    appointmentTooltip.innerHTML = tooltipHtml;
    
    // Position the tooltip
    positionTooltip(eventEl);
}

function positionTooltip(eventEl) {
    // Position the tooltip
    const rect = eventEl.getBoundingClientRect();
    const calendarRect = document.getElementById('calendar').getBoundingClientRect();
    
    // Set tooltip position
    appointmentTooltip.style.left = rect.right + 10 + 'px';
    appointmentTooltip.style.top = rect.top + window.scrollY + 'px';
    
    // Make sure tooltip doesn't go off the right edge
    const tooltipRect = appointmentTooltip.getBoundingClientRect();
    if (tooltipRect.right > calendarRect.right) {
        appointmentTooltip.style.left = rect.left - tooltipRect.width - 10 + 'px';
    }
    
    // Show tooltip
    appointmentTooltip.style.display = 'block';
}

function hideAppointmentTooltip() {
    if (appointmentTooltip) {
        appointmentTooltip.style.display = 'none';
    }
} 