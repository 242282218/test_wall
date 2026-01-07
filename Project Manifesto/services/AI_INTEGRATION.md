# AI功能集成指南

## 概述

本系统提供了AI功能的接口定义和适配层，支持智能媒体分类、元数据提取、标签建议等功能。当前实现基于规则引擎，未来可轻松替换为机器学习模型。

## 架构设计

### 核心组件

1. **AI接口层** (`ai_interface.py`)
   - `AIClassifier`: 媒体分类接口
   - `AIEnhancer`: 内容增强接口
   - `AIService`: AI服务管理接口

2. **适配层** (`ai_adapter.py`)
   - `RuleBasedClassifier`: 基于规则的分类器
   - `RuleBasedEnhancer`: 基于规则的增强器
   - `AIServiceAdapter`: AI服务适配器

3. **示例代码** (`ai_example.py`)
   - 完整的使用示例和测试用例

## 功能特性

### 1. 智能媒体分类

自动识别媒体类型：
- Movies (电影)
- Series (剧集)
- Documentaries (纪录片)
- Anime (动漫)
- Music (音乐)
- Others (其他)

**示例：**
```python
from ai_adapter import RuleBasedClassifier

classifier = RuleBasedClassifier()
result = await classifier.classify_media(
    title="Inception (2010) 1080p BluRay"
)
print(result.category)  # MediaCategory.MOVIES
print(result.confidence)  # 0.95
```

### 2. 元数据提取

从标题和文件名中提取结构化信息：
- 年份
- 类型
- 语言
- 标签

**示例：**
```python
metadata = await classifier.extract_metadata(
    title="The Dark Knight (2008) Action Thriller"
)
print(metadata.year)  # 2008
print(metadata.genre)  # ["Action", "Thriller"]
```

### 3. 标签建议

基于内容自动生成标签建议：
```python
tags = await classifier.suggest_tags(
    title="The Matrix (1999) 1080p",
    limit=10
)
for tag in tags:
    print(f"{tag.tag} ({tag.confidence:.2f})")
```

### 4. 描述增强

自动生成或增强媒体描述：
```python
from ai_adapter import RuleBasedEnhancer

enhancer = RuleBasedEnhancer()
description = await enhancer.enhance_description(
    title="Interstellar",
    metadata=metadata
)
```

### 5. 摘要生成

生成媒体摘要信息：
```python
summary = await enhancer.generate_summary(
    title="Inception",
    metadata=metadata
)
```

### 6. 重复检测

检测相似或重复的媒体项：
```python
duplicates = await enhancer.detect_duplicate(
    title="The Dark Knight",
    existing_titles=existing_titles,
    threshold=0.85
)
```

## 集成到现有系统

### 1. 在Transfer Worker中使用

修改 `transfer_worker.py` 集成AI分类：

```python
from ai_adapter import AIServiceAdapter

async def main():
    ai_service = AIServiceAdapter()
    await ai_service.initialize()
    
    classifier = ai_service.classifier
    
    while True:
        task = await redis_client.blpop(TRANSFER_QUEUE_KEY)
        payload = json.loads(task[1])
        
        classification = await classifier.classify_media(
            title=payload.get("title", ""),
            filename=payload.get("filename")
        )
        
        dest_path = classifier.build_dest_path(
            title=payload["title"],
            media_type=classification.category
        )
        
        await process_transfer(dest_path, payload)
    
    await ai_service.shutdown()
```

### 2. 在API中使用

添加AI增强的API端点：

```python
from ai_adapter import AIServiceAdapter

ai_service = AIServiceAdapter()

@app.on_event("startup")
async def startup():
    await ai_service.initialize()

@app.post("/api/media/enhance")
async def enhance_media(media_id: str):
    media = await get_media(media_id)
    
    metadata = await ai_service.classifier.extract_metadata(
        title=media.title
    )
    
    description = await ai_service.enhancer.enhance_description(
        title=media.title,
        metadata=metadata
    )
    
    return {
        "metadata": metadata,
        "description": description
    }
```

### 3. 环境变量配置

在 `.env` 中添加AI配置：

```env
AI_ENABLED=true
AI_CLASSIFIER_TYPE=rule_based
AI_ENHANCER_TYPE=rule_based
AI_CACHE_TTL=3600
```

## 扩展到机器学习模型

### 替换为OpenAI API

```python
import openai
from ai_interface import AIClassifier

class OpenAIClassifier(AIClassifier):
    def __init__(self, api_key: str):
        openai.api_key = api_key
    
    async def classify_media(self, title: str, filename: str = None) -> ClassificationResult:
        response = await openai.ChatCompletion.acreate(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": "Classify the following media into Movies, Series, Documentaries, Anime, Music, or Others."
                },
                {
                    "role": "user",
                    "content": f"Title: {title}\nFilename: {filename or 'N/A'}"
                }
            ]
        )
        
        category = response.choices[0].message.content
        return ClassificationResult(
            category=MediaCategory(category),
            confidence=0.95
        )
```

### 替换为本地模型

```python
from transformers import pipeline

class TransformerClassifier(AIClassifier):
    def __init__(self):
        self.classifier = pipeline("text-classification", model="your-model")
    
    async def classify_media(self, title: str, filename: str = None) -> ClassificationResult:
        text = f"{title} {filename or ''}"
        result = self.classifier(text)
        
        return ClassificationResult(
            category=MediaCategory(result[0]["label"]),
            confidence=result[0]["score"]
        )
```

## 性能优化

### 1. 缓存分类结果

```python
from functools import lru_cache

class CachedClassifier(AIClassifier):
    def __init__(self, classifier: AIClassifier):
        self._classifier = classifier
    
    @lru_cache(maxsize=1000)
    async def classify_media(self, title: str, filename: str = None) -> ClassificationResult:
        return await self._classifier.classify_media(title, filename)
```

### 2. 批量处理

```python
async def batch_classify(titles: List[str]) -> List[ClassificationResult]:
    tasks = [classifier.classify_media(title) for title in titles]
    return await asyncio.gather(*tasks)
```

### 3. 异步处理

```python
async def process_with_ai(media: VirtualMedia):
    metadata = await ai_service.classifier.extract_metadata(media.title)
    
    media.year = metadata.year
    media.genre = metadata.genre
    media.tags = metadata.tags
    
    await save_media(media)
```

## 测试

运行示例代码：

```bash
cd services/workers
python ai_example.py
```

测试输出应包含：
- 媒体分类结果
- 元数据提取结果
- 标签建议
- 描述增强
- 摘要生成
- 重复检测
- 完整工作流

## 监控和日志

### 日志配置

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger("ai_service")
```

### 性能指标

```python
import time

async def classify_with_metrics(title: str):
    start = time.time()
    result = await classifier.classify_media(title)
    duration = time.time() - start
    
    logger.info(f"Classification took {duration:.3f}s")
    logger.info(f"Category: {result.category}, Confidence: {result.confidence}")
    
    return result
```

## 故障处理

### 降级策略

```python
class FallbackClassifier(AIClassifier):
    def __init__(self, primary: AIClassifier, fallback: AIClassifier):
        self._primary = primary
        self._fallback = fallback
    
    async def classify_media(self, title: str, filename: str = None) -> ClassificationResult:
        try:
            return await self._primary.classify_media(title, filename)
        except Exception as e:
            logger.error(f"Primary classifier failed: {e}, using fallback")
            return await self._fallback.classify_media(title, filename)
```

## 最佳实践

1. **缓存常用分类结果**以减少重复计算
2. **批量处理**以提高吞吐量
3. **异步操作**以避免阻塞
4. **降级策略**确保服务可用性
5. **监控性能**及时发现瓶颈
6. **定期更新模型**保持准确性

## 未来扩展

- [ ] 集成OpenAI GPT-4进行智能分类
- [ ] 使用BERT等模型进行语义理解
- [ ] 添加图像识别功能
- [ ] 实现推荐系统
- [ ] 支持多语言处理
- [ ] 添加情感分析
