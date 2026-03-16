---
name: quickbooks-automation
description: "Automate QuickBooks tasks via Rube MCP (Composio): invoices, customers, payments, expenses, and reports. Always search tools first for current schemas."
requires:
  mcp: [rube]
---

# QuickBooks Automation via Rube MCP

Automate QuickBooks Online operations through Composio's QuickBooks toolkit via Rube MCP.

## Prerequisites

- Rube MCP must be connected (RUBE_SEARCH_TOOLS available)
- Active QuickBooks connection via `RUBE_MANAGE_CONNECTIONS` with toolkit `quickbooks`
- Always call `RUBE_SEARCH_TOOLS` first to get current tool schemas

## Setup

1. Verify Rube MCP is available
2. Call `RUBE_MANAGE_CONNECTIONS` with toolkit `quickbooks`
3. Complete Intuit OAuth flow
4. Confirm connection status shows ACTIVE

## Core Workflows

### 1. Invoice Management
- Create and send invoices
- List outstanding invoices
- Mark invoices as paid
- Send payment reminders

### 2. Customer Management
- Create/update customers
- Search customers
- View customer balances

### 3. Expense Tracking
- Record expenses
- Categorize transactions
- Attach receipts

### 4. Payment Processing
- Record payments received
- Apply payments to invoices
- Track payment methods

### 5. Reports
- Profit & Loss
- Balance Sheet
- Accounts Receivable Aging
- Cash Flow

## Tool Discovery

```
RUBE_SEARCH_TOOLS query="quickbooks" toolkit="quickbooks"
```

## Important Notes

- QuickBooks API has daily rate limits (500 requests/minute)
- Financial data is sensitive — always confirm before modifying
- Test in sandbox environment first if available
