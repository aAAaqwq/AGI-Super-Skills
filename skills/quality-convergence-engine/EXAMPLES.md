# Quality Convergence Engine - Usage Examples

## Example 1: API Design Acceptance

**User Requirement:**
"Design a product inventory management API that supports real-time inventory query and deduction"

**Engine Output:**

### 1. Multi-dimensional Convergence Conclusion
The core breakthrough point lies in balancing data consistency of concurrent deductions with system availability. The maximum risk is overselling (inventory deduction becomes negative) or service unavailability under high concurrency.

### 2. Red Light Conditions (Failure Bottom Line)
1. Concurrent deductions without locking or optimistic locking, causing overselling
2. Inventory query and deduction are non-atomic operations, creating race conditions
3. No inventory lower limit protection, inventory can become negative after deduction

### 3. Green Light Acceptance Criteria (Success Standards)
1. **Concurrency Safety**: Verification steps - Use JMeter to simulate 100 concurrent users deducting 1 item from same product inventory, total inventory 100 items, final inventory should be 0 with no overselling
2. **Atomicity Guarantee**: Verification steps - Intentionally create network delay during deduction operation, verify query and deduction are in same transaction
3. **Boundary Protection**: Verification steps - Attempt to deduct more than current inventory quantity, system should reject and return clear error message

---

## Example 2: Frontend Component Acceptance

**User Requirement:**
"Develop a data table component that supports sorting, filtering, and pagination"

**Engine Output:**

### 1. Multi-dimensional Convergence Conclusion
The core breakthrough point lies in balancing performance under large data volumes with functional completeness. The maximum risk is page freezing due to excessive data volume, or memory leaks in complex filtering logic.

### 2. Red Light Conditions (Failure Bottom Line)
1. Page completely freezes or becomes unresponsive when loading 10,000 rows of data
2. Logic errors or inconsistent results when using multi-column sorting and filtering combinations
3. Pagination component state inconsistency or incorrect page numbers after data updates

### 3. Green Light Acceptance Criteria (Success Standards)
1. **Performance Baseline**: Verification steps - Load 10,000 rows of data, initial rendering time should be less than 3 seconds, scrolling frame rate maintains above 30fps
2. **Functional Correctness**: Verification steps - Generate random test data, verify all sorting and filtering combination results match expectations
3. **State Consistency**: Verification steps - Update data while in paginated state, verify current page displays correctly and page number calculations are accurate

---

## Example 3: Architecture Design Acceptance

**User Requirement:**
"Design a microservices architecture e-commerce system including user, product, order, and payment services"

**Engine Output:**

### 1. Multi-dimensional Convergence Conclusion
The core breakthrough point lies in balancing inter-service data consistency with system complexity. The maximum risk is data inconsistency due to improper distributed transaction handling, or service avalanche causing entire system unavailability.

### 2. Red Light Conditions (Failure Bottom Line)
1. Payment fails after order creation, but inventory has been deducted and cannot be rolled back
2. Single service failure triggers chain reaction, causing entire system unavailability
3. Inter-service communication lacks timeout and retry settings, posing single point of failure risk

### 3. Green Light Acceptance Criteria (Success Standards)
1. **Data Eventual Consistency**: Verification steps - Simulate payment service downtime, verify order creation process has compensation mechanism, inventory can automatically recover within set time
2. **Circuit Breaking and Degradation**: Verification steps - Intentionally make product service unavailable, verify user service can degrade to return cached data rather than complete failure
3. **Timeout Control**: Verification steps - Test inter-service calls, verify all have reasonable timeout settings (e.g., HTTP calls not exceeding 5 seconds)

---

## Example 4: Security Solution Acceptance

**User Requirement:**
"Implement a JWT authentication system supporting token refresh and permission control"

**Engine Output:**

### 1. Multi-dimensional Convergence Conclusion
The core breakthrough point lies in balancing security strength with user experience. The maximum risk is token theft leading to account hijacking, or permission control vulnerabilities causing unauthorized access.

### 2. Red Light Conditions (Failure Bottom Line)
1. JWT tokens lack reasonable expiration time or can be used permanently
2. Permission verification only relies on frontend, backend lacks secondary validation
3. Token refresh mechanism has vulnerabilities, old tokens remain usable after refresh

### 3. Green Light Acceptance Criteria (Success Standards)
1. **Token Security**: Verification steps - Attempt to access protected interfaces with expired tokens should be rejected; check if tokens contain necessary signatures and validity periods
2. **Backend Permission Verification**: Verification steps - Directly call backend API bypassing frontend, verify permission control still works
3. **Refresh Mechanism Security**: Verification steps - After token refresh, old tokens should immediately become invalid, attempting to access with old tokens should return 401 error

---

## Engine Usage Tips

1. **Clarify Requirement Boundaries**: Before starting analysis, ensure understanding of complete requirement context
2. **Focus on Actual Pain Points**: Define risks based on common implementation errors and actual operational issues
3. **Quantify Verification Standards**: All acceptance criteria must include specific, executable verification steps
4. **Balance Multiple Perspectives**: Comprehensively consider business value, technical feasibility, and implementation risks
5. **Maintain Objective Neutrality**: Avoid personal preferences influencing judgment, focus on verifiable facts