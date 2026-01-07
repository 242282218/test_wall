#!/usr/bin/env python3
"""
测试脚本：验证夸克云盘转存功能，特别是token验证错误（41020）的修复
"""

import asyncio
import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.append(str(Path(__file__).parent.parent.parent))

from services.workers.quark_client import QuarkClient

async def test_get_stoken():
    """测试get_stoken方法"""
    print("=== 测试get_stoken方法 ===")
    
    # 从环境变量获取QUARK_COOKIE
    cookie = os.getenv("QUARK_COOKIE")
    if not cookie:
        print("❌ QUARK_COOKIE环境变量未设置")
        return False
    
    # 创建QuarkClient实例
    client = QuarkClient(cookie)
    
    # 测试用的分享链接
    test_share_url = "https://pan.quark.cn/s/710a4d0564c4"
    
    try:
        stoken = await client.get_stoken(test_share_url)
        print(f"✅ 获取stoken成功: {stoken[:20]}...")
        return True, stoken
    except Exception as e:
        print(f"❌ 获取stoken失败: {e}")
        return False, None

async def test_extract_share_info():
    """测试_extract_share_info方法"""
    print("\n=== 测试_extract_share_info方法 ===")
    
    # 从环境变量获取QUARK_COOKIE
    cookie = os.getenv("QUARK_COOKIE")
    if not cookie:
        print("❌ QUARK_COOKIE环境变量未设置")
        return False
    
    # 创建QuarkClient实例
    client = QuarkClient(cookie)
    
    # 测试用的分享链接
    test_share_url = "https://pan.quark.cn/s/710a4d0564c4"
    
    try:
        share_code, passcode = client._extract_share_info(test_share_url)
        print(f"✅ 解析分享信息成功: share_code={share_code}, passcode={passcode}")
        return True, share_code, passcode
    except Exception as e:
        print(f"❌ 解析分享信息失败: {e}")
        return False, None, None

async def main():
    """主测试函数"""
    print("开始测试夸克云盘转存功能...")
    
    # 测试get_stoken方法
    stoken_result, stoken = await test_get_stoken()
    
    # 测试_extract_share_info方法
    extract_result, share_code, passcode = await test_extract_share_info()
    
    print("\n=== 测试总结 ===")
    if stoken_result and extract_result:
        print("✅ 所有测试通过！")
        print(f"\n测试结果:")
        print(f"- stoken: {stoken[:20]}...")
        print(f"- share_code: {share_code}")
        print(f"- passcode: {passcode}")
        return 0
    else:
        print("❌ 部分或全部测试失败！")
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
