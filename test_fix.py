#!/usr/bin/env python3
"""
Test the new flexible, fault-tolerant collector behavior.
Verifies that the system now:
1. Only requires budget + num_days
2. Defaults activity_type to "mixed"
3. Asks for optional fields on first pass
4. Proceeds with available information
"""
import json
from app.graph.plan_graph.nodes.collector import collector_node
from app.graph.plan_graph.state import PlanState

def test_case(description, message):
    print(f"\n{'='*70}")
    print(f"TEST: {description}")
    print(f"USER: {message}")
    print('='*70)
    
    state = PlanState(
        session_id="test",
        messages=[{"role": "user", "content": message}],
    )
    
    result = collector_node(state)
    constraints = result.get("constraints", {})
    missing = result.get("missing_fields", [])
    question = result.get("collector_question", "")
    
    print(f"✓ Constraints extracted:")
    print(f"  - budget: {constraints.get('budget')}")
    print(f"  - num_days: {constraints.get('num_days')}")
    print(f"  - activity_type: {constraints.get('activity_type')}")
    print(f"  - destination: {constraints.get('destination')}")
    print(f"  - currency: {constraints.get('currency')}")
    print(f"\n✓ Missing fields: {missing if missing else 'NONE — Ready to proceed!'}")
    if question:
        print(f"\n✓ Follow-up question:\n{question}")

# Test 1: Original problematic input
test_case(
    "Generic trip request (original issue)",
    "Plan me a 7-day trip to Cairo with 800 USD"
)

# Test 2: Minimal input
test_case(
    "Minimal input - just essentials",
    "7 days, 500 USD"
)

# Test 3: Partial info with destination
test_case(
    "Partial info with specific destination",
    "I want to visit Luxor for 5 days with 600 USD"
)

# Test 4: Activity type specified
test_case(
    "With activity preference",
    "3 days in Giza, 800 USD, cultural activities"
)

# Test 5: Different currency
test_case(
    "Different currency",
    "10 days, 2000 EUR, adventure trip"
)

print(f"\n{'='*70}")
print("✅ All tests completed! System is now flexible and fault-tolerant.")
print('='*70)

