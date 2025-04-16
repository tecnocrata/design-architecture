# Python Example
print("Hello from Python!")

# Calculate Fibonacci numbers
def fibonacci(n):
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a

# Display the first 10 Fibonacci numbers
for i in range(10):
    print(f"Fibonacci({i}) = {fibonacci(i)}")

# Uncomment to run data visualization example
# import matplotlib.pyplot as plt
# import numpy as np
# 
# x = np.linspace(0, 10, 100)
# y = np.sin(x)
# 
# plt.figure(figsize=(10, 6))
# plt.plot(x, y)
# plt.title('Sine Wave')
# plt.xlabel('x')
# plt.ylabel('sin(x)')
# plt.grid(True)
# plt.show() 