import h_modules

@h_modules.timer
def test():
    for i in range(10000):
        print(i)

test()


@h_modules.memoize
def factorial(n):
    """Returns the factorial of n"""
    if n == 0 or n == 1:
        return 1
    else:
        return n * factorial(n - 1)
    
@h_modules.memoize
def fibonacci(n):
    """Returns the nth Fibonacci number"""
    if n == 0 or n == 1:
        return n
    else:
        return fibonacci(n - 1) + fibonacci(n - 2)
print(factorial(10))
print(fibonacci(10))
