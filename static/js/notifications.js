function markAllAsRead() {
    fetch('/notifications/mark-all-read/', {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
            'Content-Type': 'application/json',
        },
        credentials: 'same-origin'
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        return response.json();
    })
    .then(data => {
        if (data.status === 'success') {
            // Update UI to reflect changes
            const notificationElements = document.querySelectorAll('.unread-notification');
            notificationElements.forEach(el => el.classList.remove('bg-blue-50', 'unread-notification'));
            
            // Update notification count
            const countElement = document.querySelector('.notification-count');
            if (countElement) {
                countElement.remove();
            }

            // Refresh the page to ensure everything is in sync
            window.location.reload();
        } else {
            throw new Error(data.message || 'Failed to mark notifications as read');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        // Show error message to user
        alert('Failed to mark notifications as read. Please try again.');
    });
}

// Helper function to get CSRF token from cookies
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
} 