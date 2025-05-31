/**
 * Sales form JavaScript functionality
 * Handles dynamic addition/removal of sale items and total calculations
 */

document.addEventListener('DOMContentLoaded', function() {
    let itemIndex = 1; // Track next item index
    const container = document.getElementById('sale-items-container');
    const addButton = document.getElementById('add-item');
    
    // Product prices cache for calculations
    let productPrices = window.productPrices || {};
    
    // Initialize form
    initializeForm();
    
    function initializeForm() {
        // Get initial item count
        const existingItems = container.querySelectorAll('.sale-item');
        itemIndex = existingItems.length;
        
        // Set up event listeners for existing items
        existingItems.forEach(item => {
            setupItemEventListeners(item);
        });
        
        // Update totals
        updateTotals();
        
        // Add button event listener
        addButton.addEventListener('click', addNewItem);
    }
    
    function addNewItem() {
        const newItem = createNewItemHTML(itemIndex);
        container.insertAdjacentHTML('beforeend', newItem);
        
        const newItemElement = container.lastElementChild;
        setupItemEventListeners(newItemElement);
        
        itemIndex++;
        updateItemNumbers();
        updateTotals();
    }
    
    function createNewItemHTML(index) {
        // Get first select to copy options
        const firstSelect = container.querySelector('select[id$="product_id"]');
        let optionsHTML = '<option value="">Оберіть товар</option>';
        
        if (firstSelect) {
            // Copy all options except the first empty one
            const firstSelectOptions = firstSelect.querySelectorAll('option');
            firstSelectOptions.forEach(option => {
                if (option.value) { // Skip empty option
                    optionsHTML += `<option value="${option.value}" data-price="${option.dataset.price}">${option.textContent}</option>`;
                }
            });
        }
        
        return `
            <div class="sale-item border rounded p-3 mb-2" data-item-index="${index}">
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <h6 class="mb-0">Товар ${index + 1}</h6>
                    <button type="button" class="btn btn-sm btn-outline-danger remove-item">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
                <div class="row">
                    <div class="col-md-8">
                        <label for="sale_items-${index}-product_id" class="form-label">Товар</label>
                        <select class="form-select product-select" 
                                id="sale_items-${index}-product_id" 
                                name="sale_items-${index}-product_id"
                                onchange="updateItemTotal(this)">
                            ${optionsHTML}
                        </select>
                    </div>
                    <div class="col-md-4">
                        <label for="sale_items-${index}-quantity" class="form-label">Кількість</label>
                        <input class="form-control quantity-input" 
                               id="sale_items-${index}-quantity" 
                               name="sale_items-${index}-quantity" 
                               type="number" 
                               min="1" 
                               value="1"
                               onchange="updateItemTotal(this.closest('.sale-item'))">
                    </div>
                </div>
                <div class="mt-2">
                    <small class="text-muted item-total">Сума: <span class="fw-bold">0.00 грн</span></small>
                </div>
            </div>
        `;
    }
    
    function setupItemEventListeners(item) {
        // Remove button
        const removeBtn = item.querySelector('.remove-item');
        if (removeBtn) {
            removeBtn.addEventListener('click', function() {
                removeItem(item);
            });
        }
        
        // Product select
        const productSelect = item.querySelector('.product-select');
        if (productSelect) {
            productSelect.addEventListener('change', function() {
                updateItemTotal(item);
            });
        }
        
        // Quantity input
        const quantityInput = item.querySelector('.quantity-input');
        if (quantityInput) {
            quantityInput.addEventListener('change', function() {
                updateItemTotal(item);
            });
            quantityInput.addEventListener('input', function() {
                updateItemTotal(item);
            });
        }
    }
    
    function removeItem(item) {
        if (container.querySelectorAll('.sale-item').length > 1) {
            item.remove();
            updateItemNumbers();
            updateTotals();
        } else {
            alert('Продаж повинен містити принаймні один товар.');
        }
    }
    
    function updateItemNumbers() {
        const items = container.querySelectorAll('.sale-item');
        items.forEach((item, index) => {
            const header = item.querySelector('h6');
            if (header) {
                header.textContent = `Товар ${index + 1}`;
            }
            
            // Update form field names to maintain proper indexing
            const productSelect = item.querySelector('select');
            const quantityInput = item.querySelector('input');
            
            if (productSelect) {
                const oldId = productSelect.id;
                const newId = `sale_items-${index}-product_id`;
                productSelect.id = newId;
                productSelect.name = newId;
                
                const label = item.querySelector(`label[for="${oldId}"]`);
                if (label) {
                    label.setAttribute('for', newId);
                }
            }
            
            if (quantityInput) {
                const oldId = quantityInput.id;
                const newId = `sale_items-${index}-quantity`;
                quantityInput.id = newId;
                quantityInput.name = newId;
                
                const label = item.querySelector(`label[for="${oldId}"]`);
                if (label) {
                    label.setAttribute('for', newId);
                }
            }
            
            item.setAttribute('data-item-index', index);
        });
    }
    
    window.updateItemTotal = function(item) {
        if (typeof item === 'string' || item.tagName === 'SELECT') {
            // Called from onchange - get the item container
            item = item.closest ? item.closest('.sale-item') : 
                   document.querySelector(`[data-item-index="${item}"]`);
        }
        
        const productSelect = item.querySelector('.product-select');
        const quantityInput = item.querySelector('.quantity-input');
        const totalSpan = item.querySelector('.item-total span');
        
        if (!productSelect || !quantityInput || !totalSpan) return;
        
        const productId = productSelect.value;
        const quantity = parseInt(quantityInput.value) || 0;
        
        if (productId && quantity > 0) {
            // Get price from productPrices object or data attribute
            let price = 0;
            
            if (productPrices[productId]) {
                price = parseFloat(productPrices[productId]);
            } else {
                // Fallback: extract from option data attribute
                const selectedOption = productSelect.selectedOptions[0];
                if (selectedOption && selectedOption.dataset.price) {
                    price = parseFloat(selectedOption.dataset.price);
                }
            }
            
            const total = price * quantity;
            totalSpan.textContent = `${total.toFixed(2)} грн`;
        } else {
            totalSpan.textContent = '0.00 грн';
        }
        
        updateTotals();
    };
    
    function updateTotals() {
        const items = container.querySelectorAll('.sale-item');
        let totalItems = items.length;
        let totalQuantity = 0;
        let totalAmount = 0;
        
        items.forEach(item => {
            const quantityInput = item.querySelector('.quantity-input');
            const quantity = parseInt(quantityInput.value) || 0;
            totalQuantity += quantity;
            
            // Extract amount from item total
            const totalText = item.querySelector('.item-total span').textContent;
            const amount = parseFloat(totalText.replace(' грн', '')) || 0;
            totalAmount += amount;
        });
        
        // Update summary
        document.getElementById('total-items').textContent = totalItems;
        document.getElementById('total-quantity').textContent = totalQuantity;
        document.getElementById('total-amount').textContent = `${totalAmount.toFixed(2)} грн`;
    }
    
    // Form validation
    document.getElementById('sale-form').addEventListener('submit', function(e) {
        const items = container.querySelectorAll('.sale-item');
        let hasValidItems = false;
        
        items.forEach(item => {
            const productSelect = item.querySelector('.product-select');
            const quantityInput = item.querySelector('.quantity-input');
            
            if (productSelect.value && parseInt(quantityInput.value) > 0) {
                hasValidItems = true;
            }
        });
        
        if (!hasValidItems) {
            e.preventDefault();
            alert('Додайте принаймні один товар з вказаною кількістю.');
            return false;
        }
    });
}); 