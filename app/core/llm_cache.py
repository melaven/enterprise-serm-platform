"""
Legacy LLM Semantic Cache with pgvector.

Caching is disabled by default because review text may contain personal data.

Key Features:
- pgvector integration for cosine similarity search
- 95% similarity threshold for cache hits
- Automatic embedding generation
- Multi-level cache strategy (memory + database)
- Distributed cache invalidation
- Cache warming strategies
"""

import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class LLMCacheEntry:
    """Cache entry model for LLM responses"""

    def __init__(
        self,
        text_hash: str,
        text: str,
        embedding: list[float],
        sentiment: str,
        sentiment_score: float,
        tags: list[str],
        suggested_response: str | None,
        metadata: dict[str, Any],
        ttl_seconds: int = 86400,  # 24 hours default
    ):
        self.text_hash = text_hash
        self.text = text
        self.embedding = embedding
        self.sentiment = sentiment
        self.sentiment_score = sentiment_score
        self.tags = tags
        self.suggested_response = suggested_response
        self.metadata = metadata
        self.ttl_seconds = ttl_seconds
        self.created_at = datetime.utcnow()
        self.expires_at = self.created_at + timedelta(seconds=ttl_seconds)


class LLMCache:
    """
    Semantic LLM Cache with pgvector

    Architecture:
    1. Text Hashing - SHA256 for exact duplicate detection
    2. Embedding Generation - OpenAI text-embedding-3-small (1536 dims)
    3. Vector Search - pgvector cosine similarity >= 0.95
    4. Multi-level Cache - Memory LRU + PostgreSQL pgvector
    5. Cache Warming - Pre-populate with common patterns
    """

    # Cache configuration
    SIMILARITY_THRESHOLD = 0.95  # 95% similarity for cache hit
    EMBEDDING_MODEL = "text-embedding-3-small"
    EMBEDDING_DIMENSIONS = 1536
    MAX_MEMORY_CACHE_SIZE = 1000  # LRU cache size
    CACHE_TTL_SECONDS = 86400  # 24 hours

    def __init__(
        self,
        openai_api_key: str | None = None,
        enable_memory_cache: bool = False,
        enable_pgvector_cache: bool = False,
    ):
        """
        Initialize LLM Cache

        Args:
            openai_api_key: OpenAI API key for embedding generation
            enable_memory_cache: Enable in-memory LRU cache
            enable_pgvector_cache: Enable PostgreSQL pgvector cache
        """
        self.openai_api_key = openai_api_key
        self.enable_memory_cache = enable_memory_cache
        self.enable_pgvector_cache = enable_pgvector_cache

        # Memory cache (LRU)
        self._memory_cache: dict[str, LLMCacheEntry] = {}
        self._memory_cache_order: list[str] = []

        self.openai_client = None

        logger.info(
            "LLM Cache initialized: memory_cache=%s pgvector_cache=%s "
            "similarity_threshold=%s",
            enable_memory_cache,
            enable_pgvector_cache,
            self.SIMILARITY_THRESHOLD,
        )

    def _generate_text_hash(self, text: str) -> str:
        """
        Generate SHA256 hash for exact duplicate detection

        Fast path for exact duplicates before expensive vector search
        """
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    async def _generate_embedding(self, text: str) -> list[float] | None:
        """
        Generate text embedding using OpenAI API

        Args:
            text: Input text to embed

        Returns:
            List of floats representing the embedding vector
        """
        raise RuntimeError(
            "External review-text embeddings are disabled by the local-only policy"
        )

        if not self.openai_client:
            logger.warning("OpenAI client not available, cannot generate embedding")
            return None

        try:
            response = await self.openai_client.embeddings.create(
                model=self.EMBEDDING_MODEL, input=text, encoding_format="float"
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            return None

    def _cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """
        Calculate cosine similarity between two vectors

        Used for fallback when pgvector is not available
        """
        import math

        dot_product = sum(a * b for a, b in zip(vec1, vec2, strict=False))
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(b * b for b in vec2))

        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        return dot_product / (magnitude1 * magnitude2)

    def _add_to_memory_cache(self, text_hash: str, entry: LLMCacheEntry) -> None:
        """
        Add entry to memory LRU cache

        Evicts oldest entry if cache is full
        """
        if not self.enable_memory_cache:
            return

        # Evict oldest if full
        if len(self._memory_cache) >= self.MAX_MEMORY_CACHE_SIZE:
            oldest_hash = self._memory_cache_order.pop(0)
            del self._memory_cache[oldest_hash]

        # Add new entry
        self._memory_cache[text_hash] = entry
        self._memory_cache_order.append(text_hash)

    def _get_from_memory_cache(self, text_hash: str) -> LLMCacheEntry | None:
        """
        Get entry from memory cache with LRU update
        """
        if not self.enable_memory_cache:
            return None

        entry = self._memory_cache.get(text_hash)
        if entry:
            # Update LRU order
            self._memory_cache_order.remove(text_hash)
            self._memory_cache_order.append(text_hash)
            return entry

        return None

    async def _search_pgvector(
        self, session: AsyncSession, embedding: list[float], limit: int = 5
    ) -> list[dict[str, Any]]:
        """
        Search pgvector for similar embeddings

        Uses cosine similarity with threshold filtering

        Args:
            session: Database session
            embedding: Query embedding vector
            limit: Maximum number of results

        Returns:
            List of cache entries with similarity scores
        """
        if not self.enable_pgvector_cache:
            return []

        try:
            # pgvector cosine similarity search
            query = text("""
                SELECT
                    text_hash,
                    text,
                    sentiment,
                    sentiment_score,
                    tags,
                    suggested_response,
                    metadata,
                    1 - (embedding <=> :embedding) as similarity
                FROM llm_cache
                WHERE
                    1 - (embedding <=> :embedding) >= :threshold
                    AND expires_at > NOW()
                ORDER BY similarity DESC
                LIMIT :limit
            """)

            result = await session.execute(
                query,
                {
                    "embedding": str(embedding),
                    "threshold": self.SIMILARITY_THRESHOLD,
                    "limit": limit,
                },
            )

            rows = result.fetchall()
            return [
                {
                    "text_hash": row.text_hash,
                    "text": row.text,
                    "sentiment": row.sentiment,
                    "sentiment_score": row.sentiment_score,
                    "tags": row.tags,
                    "suggested_response": row.suggested_response,
                    "metadata": json.loads(row.metadata) if row.metadata else {},
                    "similarity": row.similarity,
                }
                for row in rows
            ]

        except Exception as e:
            logger.error(f"pgvector search failed: {e}")
            return []

    async def _store_pgvector(
        self, session: AsyncSession, entry: LLMCacheEntry
    ) -> bool:
        """
        Store cache entry in pgvector

        Args:
            session: Database session
            entry: Cache entry to store

        Returns:
            True if successful, False otherwise
        """
        raise RuntimeError(
            "Review-text cache storage is disabled by the local-only policy"
        )

        if not self.enable_pgvector_cache:
            return False

        try:
            query = text("""
                INSERT INTO llm_cache (
                    text_hash,
                    text,
                    embedding,
                    sentiment,
                    sentiment_score,
                    tags,
                    suggested_response,
                    metadata,
                    created_at,
                    expires_at
                ) VALUES (
                    :text_hash,
                    :text,
                    :embedding,
                    :sentiment,
                    :sentiment_score,
                    :tags,
                    :suggested_response,
                    :metadata,
                    :created_at,
                    :expires_at
                )
                ON CONFLICT (text_hash) DO UPDATE SET
                    embedding = EXCLUDED.embedding,
                    sentiment = EXCLUDED.sentiment,
                    sentiment_score = EXCLUDED.sentiment_score,
                    tags = EXCLUDED.tags,
                    suggested_response = EXCLUDED.suggested_response,
                    metadata = EXCLUDED.metadata,
                    expires_at = EXCLUDED.expires_at
            """)

            await session.execute(
                query,
                {
                    "text_hash": entry.text_hash,
                    "text": entry.text,
                    "embedding": str(entry.embedding),
                    "sentiment": entry.sentiment,
                    "sentiment_score": entry.sentiment_score,
                    "tags": entry.tags,
                    "suggested_response": entry.suggested_response,
                    "metadata": json.dumps(entry.metadata),
                    "created_at": entry.created_at,
                    "expires_at": entry.expires_at,
                },
            )

            await session.commit()
            logger.debug(f"Stored cache entry in pgvector: {entry.text_hash}")
            return True

        except Exception as e:
            logger.error(f"Failed to store in pgvector: {e}")
            await session.rollback()
            return False

    async def get(
        self, session: AsyncSession, text: str, generate_embedding: bool = True
    ) -> dict[str, Any] | None:
        """
        Get cached LLM response for text

        Multi-level cache lookup:
        1. Exact hash match (memory cache)
        2. Semantic similarity (pgvector)

        Args:
            session: Database session
            text: Input text to search for
            generate_embedding: Generate embedding if not in memory cache

        Returns:
            Cached response data or None if not found
        """
        raise RuntimeError(
            "Review-text cache lookup is disabled by the local-only policy"
        )

        text_hash = self._generate_text_hash(text)

        # Level 1: Memory cache (exact hash match)
        memory_entry = self._get_from_memory_cache(text_hash)
        if memory_entry:
            logger.debug(f"Cache hit (memory): {text_hash}")
            return {
                "sentiment": memory_entry.sentiment,
                "sentiment_score": memory_entry.sentiment_score,
                "tags": memory_entry.tags,
                "suggested_response": memory_entry.suggested_response,
                "metadata": memory_entry.metadata,
                "source": "memory_cache",
                "similarity": 1.0,
            }

        # Level 2: pgvector semantic search
        if generate_embedding:
            embedding = await self._generate_embedding(text)
            if embedding:
                similar_entries = await self._search_pgvector(session, embedding)

                if similar_entries:
                    best_match = similar_entries[0]
                    logger.info(
                        f"Cache hit (pgvector): {text_hash}",
                        similarity=best_match["similarity"],
                    )

                    # Store in memory cache for faster future access
                    self._add_to_memory_cache(
                        text_hash,
                        LLMCacheEntry(
                            text_hash=text_hash,
                            text=text,
                            embedding=embedding,
                            sentiment=best_match["sentiment"],
                            sentiment_score=best_match["sentiment_score"],
                            tags=best_match["tags"],
                            suggested_response=best_match["suggested_response"],
                            metadata=best_match["metadata"],
                        ),
                    )

                    return {
                        "sentiment": best_match["sentiment"],
                        "sentiment_score": best_match["sentiment_score"],
                        "tags": best_match["tags"],
                        "suggested_response": best_match["suggested_response"],
                        "metadata": best_match["metadata"],
                        "source": "pgvector_cache",
                        "similarity": best_match["similarity"],
                    }

        return None

    async def set(
        self,
        session: AsyncSession,
        text: str,
        sentiment: str,
        sentiment_score: float,
        tags: list[str],
        suggested_response: str | None = None,
        metadata: dict[str, Any] | None = None,
        ttl_seconds: int | None = None,
    ) -> bool:
        """
        Store LLM response in cache

        Args:
            session: Database session
            text: Input text
            sentiment: Sentiment classification
            sentiment_score: Sentiment confidence score
            tags: Extracted tags
            suggested_response: Generated response
            metadata: Additional metadata
            ttl_seconds: Time to live in seconds

        Returns:
            True if successful, False otherwise
        """
        raise RuntimeError(
            "Review-text cache storage is disabled by the local-only policy"
        )

        text_hash = self._generate_text_hash(text)
        ttl_seconds = ttl_seconds or self.CACHE_TTL_SECONDS

        # Generate embedding
        embedding = await self._generate_embedding(text)
        if not embedding:
            logger.warning("Failed to generate embedding, cannot cache")
            return False

        # Create cache entry
        entry = LLMCacheEntry(
            text_hash=text_hash,
            text=text,
            embedding=embedding,
            sentiment=sentiment,
            sentiment_score=sentiment_score,
            tags=tags,
            suggested_response=suggested_response,
            metadata=metadata or {},
            ttl_seconds=ttl_seconds,
        )

        # Store in memory cache
        self._add_to_memory_cache(text_hash, entry)

        # Store in pgvector
        success = await self._store_pgvector(session, entry)

        if success:
            logger.info(f"Cache stored: {text_hash}", ttl=ttl_seconds)

        return success

    async def invalidate(
        self,
        session: AsyncSession,
        text_hash: str | None = None,
        before_date: datetime | None = None,
    ) -> int:
        """
        Invalidate cache entries

        Args:
            session: Database session
            text_hash: Specific hash to invalidate (optional)
            before_date: Invalidate all entries before this date (optional)

        Returns:
            Number of invalidated entries
        """
        if not self.enable_pgvector_cache:
            return 0

        try:
            if text_hash:
                query = text("""
                    DELETE FROM llm_cache
                    WHERE text_hash = :text_hash
                """)
                params: dict[str, Any] = {"text_hash": text_hash}
            elif before_date:
                query = text("""
                    DELETE FROM llm_cache
                    WHERE created_at < :before_date
                """)
                params = {"before_date": before_date}
            else:
                logger.warning("No invalidation criteria provided")
                return 0

            result = await session.execute(query, params)
            await session.commit()

            count = getattr(result, "rowcount", 0)
            logger.info(f"Invalidated {count} cache entries")

            # Clear memory cache
            if text_hash:
                self._memory_cache.pop(text_hash, None)
                if text_hash in self._memory_cache_order:
                    self._memory_cache_order.remove(text_hash)
            else:
                self._memory_cache.clear()
                self._memory_cache_order.clear()

            return count

        except Exception as e:
            logger.error(f"Cache invalidation failed: {e}")
            await session.rollback()
            return 0

    async def get_cache_stats(self, session: AsyncSession) -> dict[str, Any]:
        """
        Get cache statistics

        Args:
            session: Database session

        Returns:
            Dictionary with cache statistics
        """
        stats: dict[str, Any] = {
            "memory_cache_size": len(self._memory_cache),
            "memory_cache_max_size": self.MAX_MEMORY_CACHE_SIZE,
            "pgvector_enabled": self.enable_pgvector_cache,
            "similarity_threshold": self.SIMILARITY_THRESHOLD,
        }

        if self.enable_pgvector_cache:
            try:
                # Total entries
                total_query = text("SELECT COUNT(*) FROM llm_cache")
                total_result = await session.execute(total_query)
                stats["pgvector_total_entries"] = total_result.scalar()

                # Expired entries
                expired_query = text("""
                    SELECT COUNT(*) FROM llm_cache
                    WHERE expires_at < NOW()
                """)
                expired_result = await session.execute(expired_query)
                stats["pgvector_expired_entries"] = expired_result.scalar()

                # Cache hit rate (would need tracking)
                stats["cache_hit_rate"] = "not_implemented"

            except Exception as e:
                logger.error(f"Failed to get pgvector stats: {e}")

        return stats

    async def warm_cache(self, session: AsyncSession, common_phrases: list[str]) -> int:
        """
        Warm cache with common phrases

        Pre-populates cache with frequently seen phrases
        to improve hit rate during production load

        Args:
            session: Database session
            common_phrases: List of common phrases to cache

        Returns:
            Number of phrases cached
        """
        logger.info(f"Warming cache with {len(common_phrases)} phrases")

        cached_count = 0
        for phrase in common_phrases:
            # Check if already cached
            cached = await self.get(session, phrase, generate_embedding=False)
            if cached:
                continue

            # Generate embedding and cache with default values
            embedding = await self._generate_embedding(phrase)
            if embedding:
                entry = LLMCacheEntry(
                    text_hash=self._generate_text_hash(phrase),
                    text=phrase,
                    embedding=embedding,
                    sentiment="neutral",  # Default
                    sentiment_score=0.5,
                    tags=[],
                    suggested_response=None,
                    metadata={"cache_warming": True},
                )

                if await self._store_pgvector(session, entry):
                    cached_count += 1

        logger.info(f"Cache warming complete: {cached_count} phrases cached")
        return cached_count


# Global cache instance
_llm_cache: LLMCache | None = None


def get_llm_cache(
    openai_api_key: str | None = None,
    enable_memory_cache: bool = True,
    enable_pgvector_cache: bool = True,
) -> LLMCache:
    """
    Get global LLM cache instance

    Singleton pattern for consistent cache across application
    """
    global _llm_cache

    if _llm_cache is None:
        _llm_cache = LLMCache(
            openai_api_key=openai_api_key,
            enable_memory_cache=enable_memory_cache,
            enable_pgvector_cache=enable_pgvector_cache,
        )

    return _llm_cache
