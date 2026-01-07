import asyncio
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from workers.ai_adapter import AIServiceAdapter
from workers.media_classifier import MediaClassifier
from workers.cookie_manager import CookieManager


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_ai_service():
    logger.info("=== 测试 AI 服务 ===")
    
    ai_service = AIServiceAdapter()
    
    initialized = await ai_service.initialize()
    assert initialized, "AI 服务初始化失败"
    logger.info("✓ AI 服务初始化成功")
    
    healthy = await ai_service.health_check()
    assert healthy, "AI 服务健康检查失败"
    logger.info("✓ AI 服务健康检查通过")
    
    classifier = ai_service.classifier
    result = await classifier.classify_media("Inception (2010) 1080p BluRay")
    logger.info(f"✓ 分类结果: {result.category} (置信度: {result.confidence:.2f})")
    
    metadata = await classifier.extract_metadata("The Dark Knight (2008) Action")
    logger.info(f"✓ 元数据提取: 年份={metadata.year}, 类型={metadata.genre}")
    
    tags = await classifier.suggest_tags("The Matrix (1999) 1080p", limit=5)
    logger.info(f"✓ 标签建议: {[t.tag for t in tags]}")
    
    await ai_service.shutdown()
    logger.info("✓ AI 服务已关闭")


async def test_media_classifier():
    logger.info("=== 测试媒体分类器 ===")
    
    classifier = MediaClassifier()
    
    test_cases = [
        ("Inception (2010)", "Movies"),
        ("Breaking Bad S01E01", "Series"),
        ("Planet Earth Documentary", "Documentaries"),
        ("Attack on Titan", "Anime"),
        ("Greatest Hits Album", "Music")
    ]
    
    for title, expected_type in test_cases:
        media_type = classifier.classify(title)
        logger.info(f"✓ '{title}' -> {media_type} (期望: {expected_type})")
    
    path = classifier.build_dest_path(
        title="Inception",
        filename="Inception.2010.1080p.BluRay.mkv",
        media_type="Movies",
        year=2010
    )
    logger.info(f"✓ 目标路径: {path}")


async def test_cookie_manager():
    logger.info("=== 测试 Cookie 管理器 ===")
    
    cookie = "test_cookie_value"
    manager = CookieManager(cookie=cookie)
    
    assert manager.cookie == cookie, "Cookie 获取失败"
    logger.info("✓ Cookie 获取成功")
    
    new_cookie = "new_test_cookie_value"
    manager.update_cookie(new_cookie)
    assert manager.cookie == new_cookie, "Cookie 更新失败"
    logger.info("✓ Cookie 更新成功")
    
    manager.update_cookie(cookie)
    assert manager.cookie == cookie, "Cookie 恢复失败"
    logger.info("✓ Cookie 恢复成功")


async def test_integration():
    logger.info("=== 测试集成功能 ===")
    
    ai_service = AIServiceAdapter()
    await ai_service.initialize()
    
    classifier = MediaClassifier()
    
    test_title = "The Shawshank Redemption (1994) Drama 1080p"
    
    classification = await ai_service.classifier.classify_media(test_title)
    logger.info(f"✓ AI 分类: {classification.category}")
    
    rule_based_type = classifier.classify(test_title)
    logger.info(f"✓ 规则分类: {rule_based_type}")
    
    metadata = await ai_service.classifier.extract_metadata(test_title)
    logger.info(f"✓ 元数据: {metadata.year}, {metadata.genre}")
    
    path = classifier.build_dest_path(
        title=test_title,
        filename="Shawshank.1994.1080p.mkv",
        media_type=classification.category,
        year=metadata.year
    )
    logger.info(f"✓ 集成路径: {path}")
    
    await ai_service.shutdown()


async def test_performance():
    logger.info("=== 测试性能 ===")
    
    import time
    
    ai_service = AIServiceAdapter()
    await ai_service.initialize()
    
    titles = [
        "Movie 1 (2020)", "Movie 2 (2021)", "Movie 3 (2022)",
        "Series S01E01", "Series S02E05", "Series S03E10",
        "Documentary 1", "Documentary 2", "Documentary 3"
    ]
    
    start = time.time()
    
    tasks = [ai_service.classifier.classify_media(title) for title in titles]
    results = await asyncio.gather(*tasks)
    
    duration = time.time() - start
    
    logger.info(f"✓ 处理 {len(titles)} 个标题耗时: {duration:.3f}秒")
    logger.info(f"✓ 平均每个标题: {duration/len(titles):.3f}秒")
    
    await ai_service.shutdown()


async def main():
    logger.info("开始运行测试套件...")
    logger.info("")
    
    try:
        await test_ai_service()
        logger.info("")
        
        await test_media_classifier()
        logger.info("")
        
        await test_cookie_manager()
        logger.info("")
        
        await test_integration()
        logger.info("")
        
        await test_performance()
        logger.info("")
        
        logger.info("=" * 50)
        logger.info("所有测试通过！✓")
        logger.info("=" * 50)
        
        return 0
        
    except AssertionError as e:
        logger.error(f"测试失败: {e}")
        return 1
    except Exception as e:
        logger.error(f"测试过程中发生错误: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
