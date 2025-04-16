// JavaScript Example

// Basic output
console.log("Hello from JavaScript!");

// Fibonacci function implementation
function fibonacci(n) {
  if (n <= 1) return n;

  let a = 0,
    b = 1;
  for (let i = 2; i <= n; i++) {
    const temp = a + b;
    a = b;
    b = temp;
  }
  return b;
}

// Calculate and display Fibonacci numbers
console.log("Fibonacci Numbers:");
for (let i = 0; i < 10; i++) {
  console.log(`Fibonacci(${i}) = ${fibonacci(i)}`);
}

// Array operations with modern JavaScript
const numbers = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
const evenNumbers = numbers.filter((num) => num % 2 === 0);

console.log("\nEven numbers from 1-10:");
evenNumbers.forEach((num) => console.log(num));

// Promise example
console.log("\nPromise example:");
function delayedMessage(message, delay) {
  return new Promise((resolve) => {
    setTimeout(() => {
      resolve(message);
    }, delay);
  });
}

// This would work in a browser or Node.js environment
// Uncomment to test in an appropriate environment
/*
delayedMessage("This message appears after 1 second!", 1000)
    .then(message => console.log(message))
    .catch(error => console.error(error));
*/
