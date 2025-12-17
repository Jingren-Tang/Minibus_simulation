```markdown
# Greedy Insertion Algorithm Example

## 🚐 Scenario

**Vehicle M1 Current State:**

- Current route: `A → B` (going to station B to pick up a pre-booked passenger)
- Passengers onboard: 0
- Capacity: 4 people

**New Passenger Request:**

- P1 needs to go from station C to station D

---

## 🔢 Three Insertion Options

Since the original route has only 2 stations (A and B), after inserting C and D, there are only **3 reasonable options**:

---

### **Option 1: Insert Both at the Front**
```

Original route: A → B
New route: C(pickup P1) → D(dropoff P1) → A → B

````

**Cost Calculation:**
```python
C → D: 360 seconds
D → A: 900 seconds
A → B: 300 seconds

Total cost = 360 + 900 + 300 = 1560 seconds
````

**Capacity Check:**

```
Station C: pickup P1 → 1 person onboard ✅
Station D: dropoff P1 → 0 people onboard ✅
Rest of route: empty ✅
```

✅ **Feasible, cost = 1560 seconds**

---

### **Option 2: Insert in the Middle**

```
Original route: A → B
New route:      A → C(pickup P1) → D(dropoff P1) → B
```

**Cost Calculation:**

```python
A → C: 600 seconds
C → D: 360 seconds
D → B: 720 seconds

Total cost = 600 + 360 + 720 = 1680 seconds
```

**Capacity Check:**

```
Station A: no action → 0 people onboard ✅
Station C: pickup P1 → 1 person onboard ✅
Station D: dropoff P1 → 0 people onboard ✅
Station B: no action → 0 people onboard ✅
```

✅ **Feasible, cost = 1680 seconds**

---

### **Option 3: Insert Both at the End**

```
Original route: A → B
New route:      A → B → C(pickup P1) → D(dropoff P1)
```

**Cost Calculation:**

```python
A → B: 300 seconds
B → C: 420 seconds
C → D: 360 seconds

Total cost = 300 + 420 + 360 = 1080 seconds ✨
```

**Capacity Check:**

```
Station A: no action → 0 people onboard ✅
Station B: no action → 0 people onboard ✅
Station C: pickup P1 → 1 person onboard ✅
Station D: dropoff P1 → 0 people onboard ✅
```

✅ **Feasible, cost = 1080 seconds** ← **Best!**

---

## 📊 Comparison Summary

| Option | Route       | Total Cost   | Result             |
| ------ | ----------- | ------------ | ------------------ |
| 1      | **C→D**→A→B | 1560 sec     | ❌ Too much detour |
| 2      | A→**C→D**→B | 1680 sec     | ❌ Still detouring |
| 3      | A→B→**C→D** | **1080 sec** | ✅ **Optimal**     |

---

## 🎯 Algorithm Decision

```python
best_cost = infinity
best_route = None

# Option 1
cost1 = 1560
if cost1 < best_cost:
    best_cost = cost1
    best_route = "C→D→A→B"

# Option 2
cost2 = 1680
if cost2 < best_cost:  # 1680 > 1560, no update
    pass

# Option 3
cost3 = 1080
if cost3 < best_cost:  # 1080 < 1560 ✓
    best_cost = 1080
    best_route = "A→B→C→D"  # Final choice

return best_route  # Returns: A→B→C→D
```

---

## 💡 Core Logic

1. **Enumerate**: Try all insertion position combinations
2. **Calculate**: Sum up travel time for each segment
3. **Check**: Ensure capacity constraint is satisfied
4. **Compare**: Choose the option with minimum cost

That's it! 🎉

```

```
