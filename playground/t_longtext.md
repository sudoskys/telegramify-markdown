---

### 问题描述
在 0-1 背包问题中，你有一个容量为 `W` 的背包，和 `n` 个物品。 每件物品有一个重量 `w[i]` 和价值 `v[i]`。目标是在不超过背包容量的前提下，使得装入背包中的物品价值总和最大。

#### 输入
- `n`: 物品数量
- `W`: 背包容量
- `w[i]`: 第 i 个物品的重量
- `v[i]`: 第 i 个物品的价值

#### 输出
- 一个整数，表示最大价值。

---

### 方法一：递归+记忆化（自顶向下）

```python
def knapsack_recursive_memo(weights, values, capacity, n, memo):
    """
    使用递归和记忆化求解 0-1 背包问题。
    :param weights: list, 每个物品的重量
    :param values: list, 每个物品的价值
    :param capacity: int, 背包最大容量
    :param n: int, 当前考虑的物品数
    :param memo: dict, 用于存储子问题的解（记忆化）
    :return: int, 最大价值
    """
    # 基本条件：没有物品或者容量为0时，价值为0
    if n == 0 or capacity == 0:
        return 0

    # 如果子问题已经计算过，直接从 memo 中取出答案
    if (n, capacity) in memo:
        return memo[(n, capacity)]

    # 当前物品的重量
    current_weight = weights[n - 1]
    current_value = values[n - 1]

    # 如果当前物品重量超过背包容量，则不能选择当前物品
    if current_weight > capacity:
        result = knapsack_recursive_memo(weights, values, capacity, n - 1, memo)
    else:
        # 两种情况：
        # 1. 不选当前物品
        without_current = knapsack_recursive_memo(weights, values, capacity, n - 1, memo)
        # 2. 选当前物品
        with_current = current_value + knapsack_recursive_memo(weights, values, capacity - current_weight, n - 1, memo)

        # 选两者中较大的值
        result = max(without_current, with_current)

    # 保存结果到 memo 中
    memo[(n, capacity)] = result
    return result


# 测试递归+记忆化方法
weights = [1, 2, 3, 4]  # 每个物品的重量
values = [10, 20, 30, 40]  # 每个物品的价值
capacity = 5  # 背包容量
n = len(weights)
memo = {}  # 记忆化字典

# 最大价值
max_value = knapsack_recursive_memo(weights, values, capacity, n, memo)
print(f"最大价值（递归 + 记忆化）: {max_value}")
```

**代码解释**

1. **终止条件**:
    - 如果没有物品（`n == 0`）或背包已满（`capacity == 0`），返回 `0`。
2. **记忆化优化**:
    - 子问题 `(n, capacity)` 的答案计算完成后存储在 `memo` 中，避免重复计算。
3. **递归选择**:
    - 如果当前物品重量超出剩余容量，只能跳过当前物品；
    - 否则在「选与不选当前物品」中选择价值最大的方案。
4. 时间复杂度为 `O(n * W)`，空间复杂度为 `O(n * W)`（用于存储 `memo`）。

---

### 方法二：动态规划（自底向上）

```python
def knapsack_dp(weights, values, capacity):
    """
    使用动态规划求解 0-1 背包问题。
    :param weights: list, 每个物品的重量
    :param values: list, 每个物品的价值
    :param capacity: int, 背包容量
    :return: int, 最大价值
    """
    n = len(weights)

    # 创建 dp 数组，dp[i][j] 表示考虑前 i 个物品，容量为 j 的最大价值
    dp = [[0] * (capacity + 1) for _ in range(n + 1)]

    # 填表
    for i in range(1, n + 1):
        for j in range(1, capacity + 1):
            if weights[i - 1] > j:  # 当前物品的重量超过容量，不能选
                dp[i][j] = dp[i - 1][j]
            else:
                # 两种选择：
                # 1. 不选当前物品，价值和前 i-1 个物品相同
                without_current = dp[i - 1][j]
                # 2. 选当前物品，价值为当前物品价值 + 剩余容量的最大价值
                with_current = values[i - 1] + dp[i - 1][j - weights[i - 1]]

                dp[i][j] = max(without_current, with_current)

    return dp[n][capacity]


# 测试动态规划方法
weights = [1, 2, 3, 4]
values = [10, 20, 30, 40]
capacity = 5

# 最大价值
max_value = knapsack_dp(weights, values, capacity)
print(f"最大价值（动态规划）: {max_value}")
```

**代码解释**

1. **DP 状态定义**:
    - `dp[i][j]`: 表示前 `i` 件物品，在容量为 `j` 时的最大价值。
2. **递推公式**:
    - 如果当前物品重量超过容量，则 `dp[i][j] = dp[i-1][j]`；
    - 否则 `dp[i][j] = max(dp[i-1][j], dp[i-1][j - weights[i-1]] + values[i-1])`，表示选与不选当前物品中取最大值。
3. **初始化**:
    - `dp[0][j] = 0` 和 `dp[i][0] = 0`，即任何物品为空或容量为零时的价值为 `0`。
4. 最终答案在 `dp[n][capacity]` 中。
5. 时间复杂度为 `O(n * W)`，空间复杂度为 `O(n * W)`。

---

### 优化：动态规划的空间压缩

通过观察状态转移公式，`dp[i][j]` 只依赖于上一行 `dp[i-1][...]`。因此可以优化成一维数组。

```python
def knapsack_dp_optimized(weights, values, capacity):
    """
    使用动态规划（空间优化）求解 0-1 背包问题。
    :param weights: list, 每个物品的重量
    :param values: list, 每个物品的价值
    :param capacity: int, 背包容量
    :return: int, 最大价值
    """
    n = len(weights)

    # 只使用一维数组 dp，dp[j] 表示容量为 j 的最大价值
    dp = [0] * (capacity + 1)

    # 填表
    for i in range(n):
        for j in range(capacity, weights[i] - 1, -1):  # 倒序遍历容量
            dp[j] = max(dp[j], dp[j - weights[i]] + values[i])

    return dp[capacity]


# 测试优化版动态规划方法
weights = [1, 2, 3, 4]
values = [10, 20, 30, 40]
capacity = 5

# 最大价值
max_value = knapsack_dp_optimized(weights, values, capacity)
print(f"最大价值（动态规划 + 空间优化）: {max_value}")
```

**优化解释**

1. 只维护一个一维数组 `dp`，从后往前更新，避免值被覆盖。
2. 时间复杂度仍为 `O(n * W)`，空间复杂度降为 `O(W)`。

---

### 小结

三种方法总结如下：

| 方法        | 时间复杂度    | 空间复杂度    | 优点       |
|-----------|----------|----------|----------|
| 递归 + 记忆化  | O(n * W) | O(n * W) | 思路直观，易理解 |
| 动态规划（2D表） | O(n * W) | O(n * W) | 实现简洁清晰   |
| 动态规划（优化）  | O(n * W) | O(W)     | 节省空间     |

### React 代码示例

以下代码使用 React 构建了一个 UI 应用，允许用户动态输入数据并计算最大背包价值：

```jsx
import React, {useState} from "react";

const KnapsackProblem = () => {
  const [capacity, setCapacity] = useState("");
  const [weights, setWeights] = useState("");
  const [values, setValues] = useState("");
  const [result, setResult] = useState(null);

  // 动态规划解决 0-1 背包问题
  const solveKnapsack = (weights, values, capacity) => {
    const n = weights.length;

    // 初始化 dp 表
    const dp = Array.from({ length: n + 1 }, () =>
      Array(capacity + 1).fill(0)
    );

    // 填表
    for (let i = 1; i <= n; i++) {
      for (let j = 1; j <= capacity; j++) {
        if (weights[i - 1] > j) {
          dp[i][j] = dp[i - 1][j]; // 当前物品不能选择
        } else {
          dp[i][j] = Math.max(
            dp[i - 1][j], // 不选择当前物品
            dp[i - 1][j - weights[i - 1]] + values[i - 1] // 选择当前物品
          );
        }
      }
    }

    // dp[n][capacity] 中存储最大价值
    return dp[n][capacity];
  };

  // 处理计算时的逻辑
  const handleCalculate = () => {
    if (!capacity || !weights || !values) {
      alert("请输入容量、重量和价值！");
      return;
    }

    const capacityValue = parseInt(capacity, 10);
    const weightsArray = weights.split(",").map((w) => parseInt(w.trim(), 10));
    const valuesArray = values.split(",").map((v) => parseInt(v.trim(), 10));

    if (
      isNaN(capacityValue) ||
      weightsArray.some((w) => isNaN(w)) ||
      valuesArray.some((v) => isNaN(v))
    ) {
      alert("请输入有效的数字！");
      return;
    }

    if (weightsArray.length !== valuesArray.length) {
      alert("重量和价值数组长度必须相同！");
      return;
    }

    const maxValue = solveKnapsack(weightsArray, valuesArray, capacityValue);
    setResult(maxValue);
  };

  return (
    <div style={{ padding: "20px", fontFamily: "Arial, sans-serif" }}>
      <h1>0-1 背包问题</h1>

      <div style={{ marginBottom: "10px" }}>
        <label>
          背包容量（整数）:
          <input
            type="number"
            value={capacity}
            onChange={(e) => setCapacity(e.target.value)}
            style={{ marginLeft: "10px", padding: "5px" }}
          />
        </label>
      </div>

      <div style={{ marginBottom: "10px" }}>
        <label>
          物品重量（用逗号分隔）:
          <input
            type="text"
            value={weights}
            onChange={(e) => setWeights(e.target.value)}
            placeholder="如：1, 2, 3"
            style={{ marginLeft: "10px", padding: "5px", width: "300px" }}
          />
        </label>
      </div>

      <div style={{ marginBottom: "10px" }}>
        <label>
          物品价值（用逗号分隔）:
          <input
            type="text"
            value={values}
            onChange={(e) => setValues(e.target.value)}
            placeholder="如：10, 20, 30"
            style={{ marginLeft: "10px", padding: "5px", width: "300px" }}
          />
        </label>
      </div>

      <button
        onClick={handleCalculate}
        style={{
          padding: "10px 20px",
          backgroundColor: "#007BFF",
          color: "white",
          border: "none",
          borderRadius: "5px",
          cursor: "pointer",
        }}
      >
        计算最大价值
      </button>
       <button
        onClick={handleCalculate}
        style={{
          padding: "10px 20px",
          backgroundColor: "#007BFF",
          color: "white",
          border: "none",
          borderRadius: "5px",
          cursor: "pointer",
        }}
      >
        计算最大价值
      </button>
       <button
        onClick={handleCalculate}
        style={{
          padding: "10px 20px",
          backgroundColor: "#007BFF",
          color: "white",
          border: "none",
          borderRadius: "5px",
          cursor: "pointer",
        }}
      >
        计算最大价值
      </button>
       <button
        onClick={handleCalculate}
        style={{
          padding: "10px 20px",
          backgroundColor: "#007BFF",
          color: "white",
          border: "none",
          borderRadius: "5px",
          cursor: "pointer",
        }}
      >
        计算最大价值
      </button>
       <button
        onClick={handleCalculate}
        style={{
          padding: "10px 20px",
          backgroundColor: "#007BFF",
          color: "white",
          border: "none",
          borderRadius: "5px",
          cursor: "pointer",
        }}
      >
        计算最大价值
      </button>

      {result !== null && (
        <div style={{ marginTop: "20px" }}>
          <h2>结果</h2>
          <p>最大价值: {result}</p>
        </div>
      )}
    </div>
  );
};

export default KnapsackProblem;
```
