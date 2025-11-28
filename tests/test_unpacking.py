import pytest
from antflow import Pipeline, Stage

async def add(a, b):
    return a + b

async def multiply(a, b):
    return a * b

async def greet(name, greeting="Hello"):
    return f"{greeting}, {name}!"

async def identity(x):
    return x

@pytest.mark.asyncio
async def test_unpack_args_tuple():
    stage = Stage(
        name="Add",
        workers=1,
        tasks=[add],
        unpack_args=True
    )
    pipeline = Pipeline(stages=[stage])
    
    # Input is a list of tuples
    inputs = [(1, 2), (3, 4), (5, 6)]
    results = await pipeline.run(inputs)
    
    assert len(results) == 3
    assert results[0].value == 3
    assert results[1].value == 7
    assert results[2].value == 11

@pytest.mark.asyncio
async def test_unpack_args_dict():
    stage = Stage(
        name="Greet",
        workers=1,
        tasks=[greet],
        unpack_args=True
    )
    pipeline = Pipeline(stages=[stage])
    
    # Input is a list of dicts
    inputs = [
        {"name": "Alice"},
        {"name": "Bob", "greeting": "Hi"}
    ]
    results = await pipeline.run(inputs)
    
    assert len(results) == 2
    assert results[0].value == "Hello, Alice!"
    assert results[1].value == "Hi, Bob!"

@pytest.mark.asyncio
async def test_unpack_args_mixed_pipeline():
    # Stage 1: Add (returns int)
    stage1 = Stage(
        name="Add",
        workers=1,
        tasks=[add],
        unpack_args=True
    )
    
    # Stage 2: Prepare for multiply (returns tuple)
    async def prepare_multiply(x):
        return (x, 2)
        
    stage2 = Stage(
        name="Prepare",
        workers=1,
        tasks=[prepare_multiply]
    )
    
    # Stage 3: Multiply (unpacks tuple)
    stage3 = Stage(
        name="Multiply",
        workers=1,
        tasks=[multiply],
        unpack_args=True
    )
    
    pipeline = Pipeline(stages=[stage1, stage2, stage3])
    
    inputs = [(1, 1), (2, 2)]
    results = await pipeline.run(inputs)
    
    # (1+1)*2 = 4
    # (2+2)*2 = 8
    assert results[0].value == 4
    assert results[1].value == 8

@pytest.mark.asyncio
async def test_unpack_args_scalar_input():
    """Test that unpack_args=True handles scalar inputs gracefully."""
    stage = Stage(
        name="Identity",
        workers=1,
        tasks=[identity],
        unpack_args=True
    )
    pipeline = Pipeline(stages=[stage])
    
    # Input is scalar values, not tuples/dicts
    inputs = [1, "test", 3.14]
    results = await pipeline.run(inputs)
    
    assert len(results) == 3
    assert results[0].value == 1
    assert results[1].value == "test"
    assert results[2].value == 3.14
