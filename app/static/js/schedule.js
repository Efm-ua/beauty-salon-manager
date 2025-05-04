document.addEventListener('DOMContentLoaded', function() {
    // Get the selected date from the datepicker
    const datepicker = document.getElementById('datepicker');
    
    // Handle toggle icon clicks to expand/collapse sub-slots
    document.querySelector('tbody').addEventListener('click', function(event) {
        // Check if the clicked element is a toggle icon
        if (event.target.classList.contains('toggle-icon')) {
            // Get the parent row's data-interval attribute
            const mainTime = event.target.closest('tr').dataset.interval;
            
            // Find all sub-slot rows related to this main slot
            const subSlotRows = document.querySelectorAll(`tr.sub-slot-row[data-parent="${mainTime.replace(':', '')}"]`);
            
            // Toggle visibility of sub-slot rows
            subSlotRows.forEach(row => {
                row.classList.toggle('expanded');
            });
            
            // Toggle the icon (▸ or ▾)
            if (event.target.textContent.trim() === '▸') {
                event.target.textContent = '▾';
            } else {
                event.target.textContent = '▸';
            }
        }
    });
    
    // Handle clicks on empty sub-slot cells to redirect to appointment creation
    document.querySelector('tbody').addEventListener('click', function(event) {
        // Check if the clicked element is inside a sub-slot cell but not on an existing appointment
        const cell = event.target.closest('td.sub-slot-cell');
        
        if (cell && !event.target.closest('.schedule-appointment')) {
            // Get the time from the cell's data-time attribute
            const time = cell.dataset.time;
            
            // Get the master ID from the cell's position (index in the row)
            const row = cell.closest('tr');
            const cellIndex = Array.from(row.cells).indexOf(cell);
            
            // The masterIndex is cellIndex - 1 (to account for the time column)
            const masterIndex = cellIndex - 1;
            
            // Get master ID from the corresponding header
            const masterHeader = document.querySelector('thead tr').cells[masterIndex + 1];
            const masterId = masterHeader.dataset.masterId;
            
            // Get the selected date from the datepicker
            const date = datepicker.value;
            
            // Redirect to appointment creation page with parameters
            window.location.href = `/appointments/create?date=${date}&time=${time}&master_id=${masterId}&from_schedule=1`;
        }
    });
}); 