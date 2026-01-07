import asyncio
import logging
from typing import Dict, List, Any

from ai_interface import (
    MediaCategory,
    ClassificationResult,
    MediaMetadata,
    TagSuggestion
)
from ai_adapter import (
    RuleBasedClassifier,
    RuleBasedEnhancer,
    AIServiceAdapter
)


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def example_classify_media():
    classifier = RuleBasedClassifier()
    
    test_cases = [
        ("Inception (2010) 1080p BluRay", None),
        ("Breaking Bad S01E01", "Pilot Episode.mkv"),
        ("Planet Earth II Documentary", None),
        ("Attack on Titan Season 1", "Anime Series"),
        ("Greatest Hits Album", "music.mp3"),
        ("Random File", "unknown.txt")
    ]
    
    print("\n=== 媒体分类示例 ===")
    for title, filename in test_cases:
        result: ClassificationResult = await classifier.classify_media(
            title=title,
            filename=filename
        )
        print(f"\n标题: {title}")
        print(f"文件名: {filename or 'N/A'}")
        print(f"分类: {result.category}")
        print(f"置信度: {result.confidence:.2f}")
        print(f"元数据: {result.metadata}")


async def example_extract_metadata():
    classifier = RuleBasedClassifier()
    
    test_cases = [
        "The Dark Knight (2008) Action Thriller 1080p",
        "Stranger Things Season 1 Complete Series",
        "BBC Planet Earth Documentary 4K"
    ]
    
    print("\n=== 元数据提取示例 ===")
    for title in test_cases:
        metadata: MediaMetadata = await classifier.extract_metadata(title=title)
        print(f"\n标题: {title}")
        print(f"年份: {metadata.year}")
        print(f"类型: {metadata.genre}")
        print(f"语言: {metadata.language}")
        print(f"标签: {metadata.tags}")


async def example_suggest_tags():
    classifier = RuleBasedClassifier()
    
    title = "The Matrix (1999) 1080p BluRay with Subtitles"
    description = "A sci-fi action movie about a computer hacker who learns about the true nature of reality."
    
    tags: List[TagSuggestion] = await classifier.suggest_tags(
        title=title,
        description=description,
        limit=10
    )
    
    print("\n=== 标签建议示例 ===")
    print(f"标题: {title}")
    print(f"描述: {description}")
    print("建议标签:")
    for tag in tags:
        print(f"  - {tag.tag} (置信度: {tag.confidence:.2f})")


async def example_enhance_description():
    enhancer = RuleBasedEnhancer()
    
    test_cases = [
        {
            "title": "Interstellar",
            "original_description": None,
            "metadata": MediaMetadata(
                title="Interstellar",
                year=2014,
                genre=["Sci-Fi", "Adventure", "Drama"]
            )
        },
        {
            "title": "The Godfather",
            "original_description": "A crime family saga",
            "metadata": None
        }
    ]
    
    print("\n=== 描述增强示例 ===")
    for case in test_cases:
        enhanced = await enhancer.enhance_description(
            title=case["title"],
            original_description=case["original_description"],
            metadata=case["metadata"]
        )
        print(f"\n标题: {case['title']}")
        print(f"原始描述: {case['original_description'] or 'N/A'}")
        print(f"增强后描述: {enhanced}")


async def example_generate_summary():
    enhancer = RuleBasedEnhancer()
    
    metadata = MediaMetadata(
        title="Inception",
        year=2010,
        genre=["Action", "Sci-Fi", "Thriller"],
        tags=["Mind-bending", "Dream", "Heist"],
        rating=8.8
    )
    
    summary = await enhancer.generate_summary(
        title="Inception",
        metadata=metadata
    )
    
    print("\n=== 摘要生成示例 ===")
    print(summary)


async def example_detect_duplicates():
    enhancer = RuleBasedEnhancer()
    
    title = "The Dark Knight"
    existing_titles = [
        "The Dark Knight",
        "Dark Knight Rises",
        "Batman: The Dark Knight",
        "The Dark Knight Returns",
        "The Dark Knight (2008)"
    ]
    
    duplicates = await enhancer.detect_duplicate(
        title=title,
        existing_titles=existing_titles,
        threshold=0.7
    )
    
    print("\n=== 重复检测示例 ===")
    print(f"查询标题: {title}")
    print(f"相似度阈值: 0.7")
    print("\n可能的重复项:")
    for dup in duplicates:
        print(f"  - {dup['title']} (相似度: {dup['similarity']:.2f})")


async def example_ai_service():
    ai_service = AIServiceAdapter()
    
    print("\n=== AI服务示例 ===")
    
    await ai_service.initialize()
    print(f"服务初始化: {'成功' if await ai_service.health_check() else '失败'}")
    
    classifier = ai_service.classifier
    enhancer = ai_service.enhancer
    
    result = await classifier.classify_media("Avatar (2009) 1080p")
    print(f"\n分类结果: {result.category}")
    
    summary = await enhancer.generate_summary("Avatar", None)
    print(f"摘要: {summary}")
    
    await ai_service.shutdown()
    print("\n服务已关闭")


async def example_complete_workflow():
    ai_service = AIServiceAdapter()
    await ai_service.initialize()
    
    print("\n=== 完整工作流示例 ===")
    
    title = "The Shawshank Redemption (1994) Drama 1080p BluRay"
    
    print(f"\n处理媒体: {title}")
    
    classifier = ai_service.classifier
    enhancer = ai_service.enhancer
    
    classification = await classifier.classify_media(title)
    print(f"1. 分类: {classification.category} (置信度: {classification.confidence:.2f})")
    
    metadata = await classifier.extract_metadata(title)
    print(f"2. 元数据:")
    print(f"   - 年份: {metadata.year}")
    print(f"   - 类型: {metadata.genre}")
    print(f"   - 语言: {metadata.language}")
    
    tags = await classifier.suggest_tags(title, limit=5)
    print(f"3. 标签: {', '.join([t.tag for t in tags])}")
    
    description = await enhancer.enhance_description(title, metadata=metadata)
    print(f"4. 描述: {description}")
    
    summary = await enhancer.generate_summary(title, metadata)
    print(f"5. 摘要:\n{summary}")
    
    await ai_service.shutdown()


async def main():
    await example_classify_media()
    await example_extract_metadata()
    await example_suggest_tags()
    await example_enhance_description()
    await example_generate_summary()
    await example_detect_duplicates()
    await example_ai_service()
    await example_complete_workflow()


if __name__ == "__main__":
    asyncio.run(main())
