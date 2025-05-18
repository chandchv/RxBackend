/**
 * Multilevel Sidebar Navigation
 * 
 * This script handles the functionality for a responsive multilevel sidebar navigation.
 * Features:
 * - Mobile toggle with backdrop
 * - Expandable/collapsible multilevel menu items
 * - Automatic highlighting of active menu items based on current URL
 * - Responsive behavior (shows/hides appropriately on mobile/desktop)
 */

document.addEventListener('DOMContentLoaded', function() {
    // Get current path once for use throughout the script
    const currentPath = window.location.pathname;
    
    // Mobile sidebar toggle
    const mobileToggle = document.getElementById('sidebar-toggle');
    const sidebar = document.getElementById('sidebar');
    const backdrop = document.getElementById('sidebar-backdrop');
    
    if (mobileToggle && sidebar && backdrop) {
        mobileToggle.addEventListener('click', function() {
            sidebar.classList.toggle('-translate-x-full');
            backdrop.classList.toggle('hidden');
            
            // Toggle between open and close icons
            const openIcon = document.getElementById('menu-open-icon');
            const closeIcon = document.getElementById('menu-close-icon');
            if (openIcon && closeIcon) {
                openIcon.classList.toggle('hidden');
                closeIcon.classList.toggle('hidden');
            }
        });
        
        backdrop.addEventListener('click', function() {
            sidebar.classList.add('-translate-x-full');
            backdrop.classList.add('hidden');
            
            // Show open icon, hide close icon
            const openIcon = document.getElementById('menu-open-icon');
            const closeIcon = document.getElementById('menu-close-icon');
            if (openIcon && closeIcon) {
                openIcon.classList.remove('hidden');
                closeIcon.classList.add('hidden');
            }
        });
    }
    
    // Submenu toggles
    const submenuToggles = document.querySelectorAll('[data-submenu-toggle]');
    
    submenuToggles.forEach(toggle => {
        toggle.addEventListener('click', function(e) {
            e.preventDefault();
            
            const submenuId = this.getAttribute('data-submenu-toggle');
            const submenu = document.getElementById(submenuId);
            const icon = this.querySelector('.submenu-icon');
            
            if (submenu && icon) {
                // Toggle submenu visibility
                submenu.classList.toggle('hidden');
                
                // Rotate icon
                icon.classList.toggle('rotate-90');
                
                // Set active state on parent
                this.parentElement.classList.toggle('bg-blue-50');
                this.classList.toggle('text-blue-600');
            }
        });
    });
    
    // Set active class based on current URL
    const navLinks = document.querySelectorAll('.nav-link');
    
    navLinks.forEach(link => {
        const href = link.getAttribute('href');
        if (href && currentPath.includes(href) && href !== '/') {
            // Add active class to the link
            link.classList.add('bg-blue-50', 'text-blue-600');
            
            // If it's in a submenu, expand the parent
            const parentSubmenu = link.closest('.submenu');
            if (parentSubmenu) {
                parentSubmenu.classList.remove('hidden');
                
                // Get the parent toggle and activate it
                const parentId = parentSubmenu.getAttribute('id');
                const parentToggle = document.querySelector(`[data-submenu-toggle="${parentId}"]`);
                if (parentToggle) {
                    parentToggle.classList.add('text-blue-600');
                    parentToggle.parentElement.classList.add('bg-blue-50');
                    const icon = parentToggle.querySelector('.submenu-icon');
                    if (icon) {
                        icon.classList.add('rotate-90');
                    }
                }
            }
        }
    });
    
    // Multilevel menu functionality
    const menuTriggers = document.querySelectorAll('.menu-trigger');
    menuTriggers.forEach(trigger => {
        trigger.addEventListener('click', function() {
            // Find the submenu within the same menu-item
            const menuItem = this.closest('.menu-item');
            const submenu = menuItem.querySelector('.submenu');
            const arrow = menuItem.querySelector('.menu-arrow');
            
            // Toggle the submenu visibility
            if (submenu.style.maxHeight === '0px' || submenu.style.maxHeight === '') {
                submenu.style.maxHeight = submenu.scrollHeight + 'px';
                arrow.classList.add('rotate-180');
                menuItem.classList.add('active');
            } else {
                submenu.style.maxHeight = '0px';
                arrow.classList.remove('rotate-180');
                menuItem.classList.remove('active');
            }
            
            // Close other submenus
            document.querySelectorAll('.menu-item.active').forEach(item => {
                if (item !== menuItem) {
                    const otherSubmenu = item.querySelector('.submenu');
                    const otherArrow = item.querySelector('.menu-arrow');
                    otherSubmenu.style.maxHeight = '0px';
                    otherArrow.classList.remove('rotate-180');
                    item.classList.remove('active');
                }
            });
        });
    });
    
    // Check URL and open appropriate submenu
    menuTriggers.forEach(trigger => {
        const menuItem = trigger.closest('.menu-item');
        const submenuLinks = menuItem.querySelectorAll('.submenu a');
        
        submenuLinks.forEach(link => {
            if (link.getAttribute('href') === currentPath || 
                currentPath.includes(link.getAttribute('href'))) {
                // Found a match - open this submenu
                const submenu = menuItem.querySelector('.submenu');
                const arrow = menuItem.querySelector('.menu-arrow');
                submenu.style.maxHeight = submenu.scrollHeight + 'px';
                arrow.classList.add('rotate-180');
                menuItem.classList.add('active');
            }
        });
    });
    
    // Highlight current page in sidebar
    const sidebarLinks = document.querySelectorAll('.nav-link');
    sidebarLinks.forEach(link => {
        if (link.getAttribute('href') === currentPath || 
            (currentPath !== '/' && currentPath.includes(link.getAttribute('href')) && link.getAttribute('href') !== '/')) {
            link.classList.add('bg-blue-50', 'text-blue-700');
            link.classList.remove('text-gray-700', 'hover:bg-gray-50', 'hover:text-blue-600');
            
            // If inside a submenu, also highlight parent
            const parentItem = link.closest('.menu-item');
            if (parentItem) {
                const parentButton = parentItem.querySelector('.menu-trigger');
                if (parentButton) {
                    parentButton.classList.add('text-blue-700');
                    parentButton.classList.remove('text-gray-700');
                }
            }
        }
    });
    
    // Handle window resize
    window.addEventListener('resize', function() {
        if (window.innerWidth >= 768) {
            // On desktop, always ensure sidebar is visible
            sidebar.classList.remove('-translate-x-full');
            backdrop.classList.add('hidden');
            
            // Reset toggle button icons
            const openIcon = document.getElementById('menu-open-icon');
            const closeIcon = document.getElementById('menu-close-icon');
            if (openIcon && closeIcon) {
                openIcon.classList.remove('hidden');
                closeIcon.classList.add('hidden');
            }
        } else {
            // On mobile, ensure sidebar is hidden by default
            sidebar.classList.add('-translate-x-full');
            backdrop.classList.add('hidden');
        }
    });
}); 