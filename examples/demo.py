"""Demo showing TokenSaverClient features."""

from token_saver import TokenSaverClient

MODEL = "claude-sonnet-4-6"


def main():
    client = TokenSaverClient()

    messages = [{"role": "user", "content": "What is the capital of France?"}]

    # 1. Count tokens before sending
    tc = client.count_tokens(model=MODEL, messages=messages)
    print(tc.format())
    print()

    # 2. Estimate cost (with expected output size)
    est = client.estimate_cost(model=MODEL, messages=messages, estimated_output_tokens=200)
    print(est.format())
    print()

    # 3. Run prescriptive analysis
    report = client.analyze(model=MODEL, messages=messages)
    print(report.format())
    print()

    # 4. Send the request (tracked automatically)
    response = client.create(model=MODEL, max_tokens=1024, messages=messages)
    print(f"Response: {response.content[0].text[:100]}...")
    print()

    # 5. Build up a longer conversation and compress it
    long_conversation = [
        {"role": "user", "content": "Tell me about Python programming. I want a comprehensive overview of the language, its history, design philosophy, and main use cases in modern software development."},
        {"role": "assistant", "content": "Python is a high-level, interpreted programming language known for its readability and versatility. It was created by Guido van Rossum and first released in 1991. Python's design philosophy emphasizes code readability with its notable use of significant whitespace. It supports multiple programming paradigms, including structured, object-oriented, and functional programming. Python is widely used in web development, data science, artificial intelligence, scientific computing, automation, and scripting. The language has a large standard library and an active community that contributes thousands of third-party packages through PyPI."},
        {"role": "user", "content": "What about its type system? How has it evolved over the years and what tools exist for static type checking?"},
        {"role": "assistant", "content": "Python uses dynamic typing with optional type hints introduced in PEP 484 (Python 3.5). Variables don't need type declarations, but you can add annotations for documentation and static analysis. The typing module provides generic types like List[int], Dict[str, Any], Optional[str], and Union types. Python 3.10 added the X | Y syntax as an alternative to Union. Tools like mypy, pyright, and pytype perform static type checking. Type hints don't affect runtime behavior but improve IDE support, catch bugs early, and serve as documentation. Recent versions introduced TypeGuard, ParamSpec, TypeVarTuple, and the Self type for more expressive annotations."},
        {"role": "user", "content": "How does async programming work in Python? What are the key concepts and common patterns?"},
        {"role": "assistant", "content": "Python's asyncio module provides infrastructure for writing single-threaded concurrent code using coroutines. You define async functions with 'async def' and use 'await' to pause execution until a result is ready. Key concepts include the event loop (manages and distributes tasks), coroutines (async def functions), tasks (scheduled coroutines), and futures (placeholders for results). Common patterns include asyncio.gather() for running multiple coroutines concurrently, async context managers (async with), async iterators (async for), and semaphores for limiting concurrency. Libraries like aiohttp, httpx, and asyncpg provide async versions of common I/O operations. Python 3.11 introduced TaskGroups for structured concurrency."},
        {"role": "user", "content": "What are decorators and how do they work internally? Can you explain the mechanism behind them?"},
        {"role": "assistant", "content": "Decorators are a design pattern that allows you to modify the behavior of a function or class. They use the @decorator syntax and are essentially functions that take another function as an argument and return a modified version. Internally, @my_decorator above a function definition is syntactic sugar for func = my_decorator(func). Decorators can add logging, authentication, caching, rate limiting, or any cross-cutting concern. The functools.wraps decorator preserves the original function's metadata. Class decorators work similarly but receive and return a class. Decorators can be stacked, parameterized (using a decorator factory pattern with nested functions), and can work with both sync and async functions. Common built-in decorators include @property, @staticmethod, @classmethod, and @functools.lru_cache."},
        {"role": "user", "content": "Explain Python's memory management and garbage collection in detail."},
        {"role": "assistant", "content": "Python uses automatic memory management with reference counting as its primary mechanism. Every object has a reference count that tracks how many variables point to it. When the count drops to zero, the memory is immediately freed. However, reference counting alone cannot handle circular references (e.g., two objects referencing each other). Python's garbage collector (gc module) uses a generational algorithm to detect and collect circular references. Objects are divided into three generations (0, 1, 2) with younger objects collected more frequently. The gc module allows manual control: gc.collect() forces collection, gc.disable() turns it off, and gc.get_threshold() shows collection thresholds. CPython also uses a memory allocator called pymalloc for small objects (< 512 bytes), which uses memory pools to reduce system call overhead."},
        {"role": "user", "content": "What about metaclasses and descriptors? These are advanced topics I want to understand."},
        {"role": "assistant", "content": "Metaclasses are classes of classes. While a regular class defines behavior of instances, a metaclass defines behavior of classes themselves. The default metaclass is 'type'. You create a custom metaclass by subclassing type and overriding __new__ or __init__. Use cases include automatic registration, validation of class attributes, adding methods dynamically, and implementing ORMs. The __init_subclass__ hook (Python 3.6+) covers many metaclass use cases more simply. Descriptors are objects that define __get__, __set__, or __delete__ methods. They control attribute access on other objects. Properties are the most common descriptor. Data descriptors (with __set__ or __delete__) take precedence over instance __dict__, while non-data descriptors don't. This mechanism underlies properties, methods, static methods, class methods, and slots."},
        {"role": "user", "content": "Now explain list comprehensions in detail."},
    ]

    result = client.compress(
        model=MODEL,
        messages=long_conversation,
        target_reduction=0.5,
        query="list comprehensions",
        keep_last_n=2,
    )
    print(result.format())
    print()

    # 6. Monthly projection
    client.create(model=MODEL, max_tokens=256, messages=messages)
    proj = client.monthly_projection(requests_per_day=100)
    print(proj.format())
    print()

    # 7. Final usage summary
    print(client.usage_summary())


if __name__ == "__main__":
    main()
