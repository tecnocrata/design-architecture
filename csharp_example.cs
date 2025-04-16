using System;
using System.Collections.Generic;

namespace CSharpExample
{
    class Program
    {
        static void Main(string[] args)
        {
            Console.WriteLine("Hello from C#!");
            
            // Calculate and display Fibonacci numbers
            Console.WriteLine("Fibonacci Numbers:");
            for (int i = 0; i < 10; i++)
            {
                Console.WriteLine($"Fibonacci({i}) = {Fibonacci(i)}");
            }
            
            // Demonstrate LINQ
            var numbers = new List<int> { 1, 2, 3, 4, 5, 6, 7, 8, 9, 10 };
            var evenNumbers = numbers.FindAll(n => n % 2 == 0);
            
            Console.WriteLine("\nEven numbers from 1-10:");
            foreach (var num in evenNumbers)
            {
                Console.WriteLine(num);
            }
        }
        
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
    }
} 