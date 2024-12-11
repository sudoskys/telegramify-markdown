---
title: 0-1 Knapsack Problem
description: Implementations of the 0-1 Knapsack Problem using recursion with memoization, dynamic programming, and space-efficient dynamic programming in Python. Includes a React UI example.
---

# TEST1

\(TEST
\\(TEST
\\\(TEST
\\\\(TEST
\\\\\(TEST
'\_', '\*', '\[', '\]', '\(', '\)', '\~', '\`', '\>', '\#', '\+', '\-', '\=', '\|', '\{', '\}', '\.', '\!'
_ , * , [ , ] , ( , ) , ~ , ` , > , # , + , - , = , | , { , } , . , !

## TEST2

**Latex Math**
Function Change:
\(\Delta y = f(x_2) - f(x_1)\) can represent the change in the value of a function.
Average Rate of Change:
\(\frac{\Delta y}{\Delta x} = \frac{f(x_2) - f(x_1)}{x_2 - x_1}\) is used to denote the average rate of change of a
function over the interval \([x_1, x_2]\).

- Slope:
  \[
  F = G\frac{{m_1m_2}}{{r^2}}
  \]
- Inline: \(F = G\frac{{m_1m_2}}{{r^4}}\)

Invalid Latex Math:
There \frac{1}{2} not in the latex block.

### Problem Description

The **0-1 Knapsack Problem** involves finding the optimal way to fill a knapsack of capacity `W` using `n` items, each
with a weight `w[i]` and value `v[i]`. The goal is to maximize the total value of items in the knapsack without
exceeding its capacity.

#### Input

- **`n`**: Number of items.
- **`W`**: Knapsack capacity.
- **`w[i]`**: Weight of the i-th item.
- **`v[i]`**: Value of the i-th item.

#### TODO

- [ ] Implement the recursive + memoization solution.
- [x] Implement the dynamic programming solution.

- An integer representing the maximum achievable value in the knapsack.
    - For example, given `weights = [1, 2, 3, 4]`, `values = [10, 20, 30, 40]`, and `capacity = 5`, the maximum value
      that can be achieved is `60`.
    - The items with weights `[1, 2]` and values `[10, 20]` can be selected to achieve the maximum value.

### Method 1: Recursive + Memoization (Top-Down)

```python
def knapsack_recursive_memo(weights, values, capacity, n, memo):
    """
    Solves the 0-1 knapsack problem using recursion with memoization.
    :param weights: list, weights of the items.
    :param values: list, values of the items.
    :param capacity: int, maximum capacity of the knapsack.
    :param n: int, number of items being considered.
    :param memo: dict, memoization of subproblems.
    :return: int, maximum achievable value.
    """
    # Base case: no items or no capacity
    if n == 0 or capacity == 0:
        return 0

    # Return the result if the subproblem is already solved
    if (n, capacity) in memo:
        return memo[(n, capacity)]

    # Weight and value of the current item
    current_weight = weights[n - 1]
    current_value = values[n - 1]

    # If the item is too heavy, exclude it and move to the next
    if current_weight > capacity:
        result = knapsack_recursive_memo(weights, values, capacity, n - 1, memo)
    else:
        # Option 1: Exclude the current item
        without_current = knapsack_recursive_memo(weights, values, capacity, n - 1, memo)
        # Option 2: Include the current item
        with_current = current_value + knapsack_recursive_memo(weights, values, capacity - current_weight, n - 1, memo)
        # Take the maximum of both options
        result = max(without_current, with_current)

    # Store the result in the memo dictionary
    memo[(n, capacity)] = result
    return result


# Testing the recursive + memoization method
weights = [1, 2, 3, 4]  # Item weights
values = [10, 20, 30, 40]  # Item values
capacity = 5  # Knapsack capacity
n = len(weights)
memo = {}  # Memo dictionary

max_value = knapsack_recursive_memo(weights, values, capacity, n, memo)
print(f"Maximum Value (Recursive + Memoization): {max_value}")
```

**Key Points:**

1. **Base Condition**:
    - If no items are left (`n == 0`) or capacity is zero (`capacity == 0`), the value is `0`.
2. **Memoization**:
    - Results of subproblems `(n, capacity)` are stored in the `memo` dictionary to avoid redundant calculations.
3. **Recursive Decisions**:
    - If an item is too heavy, it is skipped.
    - Otherwise, choose from two options:
        - Exclude the current item.
        - Include the current item and add its value.
4. **Time Complexity**: `O(n * W)`, where `n` is the number of items and `W` is the capacity.
5. **Space Complexity**: `O(n * W)` for memo storage.

---

### Method 2: Dynamic Programming (Bottom-Up)

```python
def knapsack_dp(weights, values, capacity):
    """
    Solves the 0-1 knapsack problem using dynamic programming.
    :param weights: list, weights of the items.
    :param values: list, values of the items.
    :param capacity: int, maximum capacity of the knapsack.
    :return: int, maximum achievable value.
    """
    n = len(weights)

    # Create a DP table: dp[i][j] stores the max value achievable with i items and capacity j
    dp = [[0] * (capacity + 1) for _ in range(n + 1)]

    # Fill the DP table
    for i in range(1, n + 1):
        for j in range(1, capacity + 1):
            if weights[i - 1] > j:  # Item is too heavy
                dp[i][j] = dp[i - 1][j]
            else:
                # Choose the better of excluding or including the item
                dp[i][j] = max(dp[i - 1][j], dp[i - 1][j - weights[i - 1]] + values[i - 1])

    return dp[n][capacity]


# Testing the dynamic programming method
weights = [1, 2, 3, 4]
values = [10, 20, 30, 40]
capacity = 5

max_value = knapsack_dp(weights, values, capacity)
print(f"Maximum Value (Dynamic Programming): {max_value}")
```

**Key Points:**

1. **State Definition**:
    - `dp[i][j]` denotes the maximum value attained with the first `i` items and a backpack capacity of `j`.
2. **Transition Formula**:
    - If the item is too heavy, `dp[i][j] = dp[i-1][j]`.
    - Otherwise, calculate `dp[i][j] = max(dp[i-1][j], dp[i-1][j - weights[i-1]] + values[i-1])`.
3. **Initialization**:
    - `dp[i][0] = 0` and `dp[0][j] = 0`, meaning no items or zero capacity yields zero value.
4. Complexity:
    - **Time**: `O(n * W)`.
    - **Space**: `O(n * W)`.

---

### Optimization: Space-Efficient Dynamic Programming

The `dp[i][j]` in the previous method depends only on the previous row, so we can compress the state to use a 1D array.

```python
def knapsack_dp_optimized(weights, values, capacity):
    """
    Solves the 0-1 knapsack problem using space-efficient dynamic programming.
    :param weights: list, weights of the items.
    :param values: list, values of the items.
    :param capacity: int, maximum capacity of the knapsack.
    :return: int, maximum achievable value.
    """
    n = len(weights)
    dp = [0] * (capacity + 1)

    # Fill the DP array
    for i in range(n):
        for j in range(capacity, weights[i] - 1, -1):  # Iterate backward
            dp[j] = max(dp[j], dp[j - weights[i]] + values[i])

    return dp[capacity]


# Testing the space-efficient method
weights = [1, 2, 3, 4]
values = [10, 20, 30, 40]
capacity = 5

max_value = knapsack_dp_optimized(weights, values, capacity)
print(f"Maximum Value (Optimized Dynamic Programming): {max_value}")
```

**Advantages**:

- **Time Complexity**: `O(n * W)`.
- **Space Complexity**: Reduced to `O(W)`.

---

### Summary

| Method                   | Time Complexity | Space Complexity | Comment                            |
|--------------------------|-----------------|------------------|------------------------------------|
| Recursion + Memoization  | `O(n * W)`      | `O(n * W)`       | Conceptually simple and intuitive. |
| DP (Bottom-Up, 2D Table) | `O(n * W)`      | `O(n * W)`       | Easy to implement and understand.  |
| DP (Space-Optimized)     | `O(n * W)`      | `O(W)`           | Efficient in space usage.          |

---

### React UI Example for 0-1 Knapsack

Here is a React component that accepts user input for weights, values, and capacity, then computes the maximum
achievable value in the knapsack:

```jsx
// KnapsackProblem.js
import React, {useState} from "react";

const KnapsackProblem = () => {
    const [weights, setWeights] = useState("");
    const [values, setValues] = useState("");
    const [capacity, setCapacity] = useState("");
    const [result, setResult] = useState(null);

    const solveKnapsack = (weights, values, capacity) => {
        const n = weights.length;
        const dp = Array.from({length: n + 1}, () =>
            Array(capacity + 1).fill(0)
        );

        for (let i = 1; i <= n; i++) {
            for (let j = 1; j <= capacity; j++) {
                if (weights[i - 1] > j) {
                    dp[i][j] = dp[i - 1][j];
                } else {
                    dp[i][j] = Math.max(
                        dp[i - 1][j],
                        dp[i - 1][j - weights[i - 1]] + values[i - 1]
                    );
                }
            }
        }

        return dp[n][capacity];
    };

    const handleCalculate = () => {
        const weightArray = weights
            .split(",")
            .map((w) => parseInt(w.trim(), 10));
        const valueArray = values
            .split(",")
            .map((v) => parseInt(v.trim(), 10));
        const maxCapacity = parseInt(capacity, 10);

        if (weightArray.length !== valueArray.length || isNaN(maxCapacity)) {
            alert("Invalid inputs!");
            return;
        }

        const maxValue = solveKnapsack(weightArray, valueArray, maxCapacity);
        setResult(maxValue);
    };

    return (
        <div>
            <h1>0-1 Knapsack Problem</h1>
            <div> UUID: 0-1-knapsack-problem-1 00000000000000000000000000000000000000000000000000000000</div>
            <div> UUID: 0-1-knapsack-problem-1 00000000000000000000000000000000000000000000000000000000</div>
            <div> UUID: 0-1-knapsack-problem-1 00000000000000000000000000000000000000000000000000000000</div>
            <div> UUID: 0-1-knapsack-problem-1 00000000000000000000000000000000000000000000000000000000</div>
            <div> UUID: 0-1-knapsack-problem-1 00000000000000000000000000000000000000000000000000000000</div>
            <div> UUID: 0-1-knapsack-problem-1 00000000000000000000000000000000000000000000000000000000</div>
            <div> UUID: 0-1-knapsack-problem-1 00000000000000000000000000000000000000000000000000000000</div>
            <div> UUID: 0-1-knapsack-problem-1 00000000000000000000000000000000000000000000000000000000</div>
            <div> UUID: 0-1-knapsack-problem-1 00000000000000000000000000000000000000000000000000000000</div>
            <div> UUID: 0-1-knapsack-problem-1 00000000000000000000000000000000000000000000000000000000</div>
            <div> UUID: 0-1-knapsack-problem-1 00000000000000000000000000000000000000000000000000000000</div>
            <div> UUID: 0-1-knapsack-problem-1 00000000000000000000000000000000000000000000000000000000</div>
            <div> UUID: 0-1-knapsack-problem-1 00000000000000000000000000000000000000000000000000000000</div>
            <div> UUID: 0-1-knapsack-problem-1 00000000000000000000000000000000000000000000000000000000</div>
            <div> UUID: 0-1-knapsack-problem-1 00000000000000000000000000000000000000000000000000000000</div>
            <div> UUID: 0-1-knapsack-problem-1 00000000000000000000000000000000000000000000000000000000</div>
            <div> UUID: 0-1-knapsack-problem-1 00000000000000000000000000000000000000000000000000000000</div>
            <div> UUID: 0-1-knapsack-problem-1 00000000000000000000000000000000000000000000000000000000</div>
            <div> UUID: 0-1-knapsack-problem-1 00000000000000000000000000000000000000000000000000000000</div>
            <div> UUID: 0-1-knapsack-problem-1 00000000000000000000000000000000000000000000000000000000</div>
            <p>Enter weights, values, and capacity to calculate the maximum value:</p>
            <div>
                <label>
                    Capacity:
                    <input
                        type="number"
                        value={capacity}
                        onChange={(e) => setCapacity(e.target.value)}
                    />
                </label>
            </div>
            <div>
                <label>
                    Weights (comma-separated):
                    <input
                        type="text"
                        value={weights}
                        onChange={(e) => setWeights(e.target.value)}
                    />
                </label>
            </div>
            <div>
                <label>
                    Values (comma-separated):
                    <input
                        type="text"
                        value={values}
                        onChange={(e) => setValues(e.target.value)}
                    />
                </label>
            </div>
            <button onClick={handleCalculate}>Calculate Maximum Value</button>
            {result !== null && <p>Maximum Value: {result}</p>}
        </div>
    );
};

export default KnapsackProblem;
```

This React code provides a simple user interface to input weights, values, and capacity, calculates the result using a
DP function, and renders the maximum value.
