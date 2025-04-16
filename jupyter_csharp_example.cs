// C# Example for Jupyter Notebook
// Note: When using this in a notebook, make sure .NET Interactive kernel is selected

// Basic output example
Console.WriteLine("Hello from C#!");

// Calculate Fibonacci numbers
static int Fibonacci(int n)
{
    if (n <= 1)
        return n;
        
    int a = 0, b = 1;
    for (int i = 2; i <= n; i++)
    {
        int temp = a + b;
        a = b;
        b = temp;
    }
    return b;
}

// Display Fibonacci numbers
for (int i = 0; i < 10; i++)
{
    Console.WriteLine($"Fibonacci({i}) = {Fibonacci(i)}");
}

// LINQ example with collections
using System.Linq;

var numbers = new List<int> { 1, 2, 3, 4, 5, 6, 7, 8, 9, 10 };
var evenNumbers = numbers.Where(n => n % 2 == 0).ToList();

Console.WriteLine("\nEven numbers from 1-10:");
foreach (var num in evenNumbers)
{
    Console.WriteLine(num);
} 