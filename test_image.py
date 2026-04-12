#!/usr/bin/env python3
"""Test script to verify image extraction and sending"""

import asyncio
import sys
import os
sys.path.insert(0, '/Users/tiankuo.zhou/github/cc-claw')

from client.config import ClientConfig
from client.claude import ClaudeExecutor

async def test():
    config = ClientConfig.load()
    claude = ClaudeExecutor(config)

    # Test 1: Extract file paths from text
    test_text = "截图已保存到桌面：`screenshot.png`"
    paths = claude._extract_file_paths(test_text)
    print(f"Test 1 - Extract from text: {test_text}")
    print(f"  Result: {paths}")

    # Test 2: Check if file exists
    test_file = "/Users/tiankuo.zhou/Desktop/screenshot.png"
    print(f"\nTest 2 - File exists: {test_file}")
    print(f"  Exists: {os.path.isfile(test_file)}")

    # Test 3: Full execute (just list files)
    print(f"\nTest 3 - Execute claude with simple prompt")
    result, images = await claude.execute("列出当前目录")
    print(f"  Result: {result[:100]}...")
    print(f"  Images: {images}")

asyncio.run(test())
