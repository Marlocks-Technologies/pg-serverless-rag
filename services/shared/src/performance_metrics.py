"""
Performance Metrics - Custom CloudWatch metrics for Phase 5 optimization tracking.

Tracks cache performance, retrieval latency, context sizes, and cost metrics.
"""

import time
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import boto3
from shared.logger import get_logger

logger = get_logger(__name__)


class PerformanceMetrics:
    """Tracks and publishes performance metrics to CloudWatch."""

    def __init__(
        self,
        namespace: str = "RAG/Platform",
        region: str = "us-east-1"
    ):
        """
        Initialize performance metrics.

        Args:
            namespace: CloudWatch namespace
            region: AWS region
        """
        self.namespace = namespace
        self.region = region
        self.cloudwatch = boto3.client('cloudwatch', region_name=region)

    def record_cache_hit(
        self,
        cache_type: str,
        hit: bool,
        dimensions: Optional[Dict[str, str]] = None
    ):
        """
        Record cache hit/miss.

        Args:
            cache_type: Type of cache (embedding, answer, retrieval)
            hit: True if cache hit, False if miss
            dimensions: Additional dimensions
        """
        metric_data = [{
            'MetricName': 'CacheHitRate',
            'Value': 1.0 if hit else 0.0,
            'Unit': 'None',
            'Timestamp': datetime.now(timezone.utc),
            'Dimensions': self._build_dimensions({
                'CacheType': cache_type,
                **(dimensions or {})
            })
        }]

        try:
            self.cloudwatch.put_metric_data(
                Namespace=self.namespace,
                MetricData=metric_data
            )
        except Exception as e:
            logger.warning("metric_publish_failed", error=str(e))

    def record_retrieval_latency(
        self,
        latency_ms: float,
        vector_count: int,
        parallel: bool = False
    ):
        """
        Record vector retrieval latency.

        Args:
            latency_ms: Latency in milliseconds
            vector_count: Number of vectors retrieved
            parallel: Whether parallel retrieval was used
        """
        metric_data = [
            {
                'MetricName': 'RetrievalLatency',
                'Value': latency_ms,
                'Unit': 'Milliseconds',
                'Timestamp': datetime.now(timezone.utc),
                'Dimensions': self._build_dimensions({
                    'RetrievalType': 'Parallel' if parallel else 'Sequential'
                })
            },
            {
                'MetricName': 'VectorCount',
                'Value': float(vector_count),
                'Unit': 'Count',
                'Timestamp': datetime.now(timezone.utc),
                'Dimensions': self._build_dimensions({})
            }
        ]

        try:
            self.cloudwatch.put_metric_data(
                Namespace=self.namespace,
                MetricData=metric_data
            )
        except Exception as e:
            logger.warning("metric_publish_failed", error=str(e))

    def record_context_size(
        self,
        token_count: int,
        compressed: bool = False
    ):
        """
        Record context window size.

        Args:
            token_count: Number of tokens in context
            compressed: Whether context was compressed
        """
        metric_data = [{
            'MetricName': 'ContextSize',
            'Value': float(token_count),
            'Unit': 'Count',
            'Timestamp': datetime.now(timezone.utc),
            'Dimensions': self._build_dimensions({
                'Compressed': 'True' if compressed else 'False'
            })
        }]

        try:
            self.cloudwatch.put_metric_data(
                Namespace=self.namespace,
                MetricData=metric_data
            )
        except Exception as e:
            logger.warning("metric_publish_failed", error=str(e))

    def record_cost_metric(
        self,
        operation: str,
        cost_usd: float,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Record cost metric.

        Args:
            operation: Operation type (embedding, generation, retrieval)
            cost_usd: Cost in USD
            details: Optional cost breakdown
        """
        metric_data = [{
            'MetricName': 'OperationCost',
            'Value': cost_usd,
            'Unit': 'None',  # Cost in USD
            'Timestamp': datetime.now(timezone.utc),
            'Dimensions': self._build_dimensions({
                'Operation': operation
            })
        }]

        try:
            self.cloudwatch.put_metric_data(
                Namespace=self.namespace,
                MetricData=metric_data
            )

            # Log detailed cost info
            logger.info(
                "cost_tracked",
                operation=operation,
                cost_usd=cost_usd,
                details=details
            )

        except Exception as e:
            logger.warning("metric_publish_failed", error=str(e))

    def record_query_latency(
        self,
        total_ms: float,
        breakdown: Optional[Dict[str, float]] = None
    ):
        """
        Record end-to-end query latency.

        Args:
            total_ms: Total latency in milliseconds
            breakdown: Optional latency breakdown by component
        """
        metric_data = [{
            'MetricName': 'QueryLatency',
            'Value': total_ms,
            'Unit': 'Milliseconds',
            'Timestamp': datetime.now(timezone.utc),
            'Dimensions': self._build_dimensions({})
        }]

        # Add breakdown metrics if provided
        if breakdown:
            for component, latency in breakdown.items():
                metric_data.append({
                    'MetricName': 'ComponentLatency',
                    'Value': latency,
                    'Unit': 'Milliseconds',
                    'Timestamp': datetime.now(timezone.utc),
                    'Dimensions': self._build_dimensions({
                        'Component': component
                    })
                })

        try:
            self.cloudwatch.put_metric_data(
                Namespace=self.namespace,
                MetricData=metric_data
            )
        except Exception as e:
            logger.warning("metric_publish_failed", error=str(e))

    def record_optimization_savings(
        self,
        optimization_type: str,
        tokens_saved: int,
        cost_saved_usd: float
    ):
        """
        Record optimization savings.

        Args:
            optimization_type: Type of optimization (cache, compression, etc.)
            tokens_saved: Number of tokens saved
            cost_saved_usd: Cost saved in USD
        """
        metric_data = [
            {
                'MetricName': 'TokensSaved',
                'Value': float(tokens_saved),
                'Unit': 'Count',
                'Timestamp': datetime.now(timezone.utc),
                'Dimensions': self._build_dimensions({
                    'OptimizationType': optimization_type
                })
            },
            {
                'MetricName': 'CostSaved',
                'Value': cost_saved_usd,
                'Unit': 'None',
                'Timestamp': datetime.now(timezone.utc),
                'Dimensions': self._build_dimensions({
                    'OptimizationType': optimization_type
                })
            }
        ]

        try:
            self.cloudwatch.put_metric_data(
                Namespace=self.namespace,
                MetricData=metric_data
            )

            logger.info(
                "optimization_savings_tracked",
                type=optimization_type,
                tokens=tokens_saved,
                cost_usd=cost_saved_usd
            )

        except Exception as e:
            logger.warning("metric_publish_failed", error=str(e))

    def _build_dimensions(self, dims: Dict[str, str]) -> list:
        """Build CloudWatch dimensions list."""
        return [
            {'Name': key, 'Value': value}
            for key, value in dims.items()
        ]


class LatencyTracker:
    """Context manager for tracking operation latency."""

    def __init__(
        self,
        metrics: PerformanceMetrics,
        operation_name: str
    ):
        """
        Initialize latency tracker.

        Args:
            metrics: PerformanceMetrics instance
            operation_name: Name of operation being tracked
        """
        self.metrics = metrics
        self.operation_name = operation_name
        self.start_time = None
        self.breakdown = {}

    def __enter__(self):
        """Start tracking."""
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop tracking and record metric."""
        if self.start_time:
            elapsed_ms = (time.time() - self.start_time) * 1000

            if self.operation_name == 'query':
                self.metrics.record_query_latency(elapsed_ms, self.breakdown)
            elif self.operation_name == 'retrieval':
                self.metrics.record_retrieval_latency(
                    elapsed_ms,
                    self.breakdown.get('vector_count', 0),
                    self.breakdown.get('parallel', False)
                )

    def add_breakdown(self, component: str, latency_ms: float):
        """Add component latency to breakdown."""
        self.breakdown[component] = latency_ms


class CostTracker:
    """Tracks and calculates operation costs."""

    # Pricing (as of 2024, approximate)
    PRICING = {
        'titan_embed_input': 0.0001 / 1000,    # per token
        'haiku_input': 0.00025 / 1000,          # per token
        'haiku_output': 0.00125 / 1000,         # per token
        'sonnet_input': 0.003 / 1000,           # per token
        'sonnet_output': 0.015 / 1000,          # per token
        'dynamodb_read': 0.00000025,            # per read unit
        'dynamodb_write': 0.00000125,           # per write unit
        's3_get': 0.0000004,                    # per GET request
        's3_put': 0.000005,                     # per PUT request
    }

    def __init__(self, metrics: PerformanceMetrics):
        """
        Initialize cost tracker.

        Args:
            metrics: PerformanceMetrics instance
        """
        self.metrics = metrics

    def calculate_embedding_cost(self, input_tokens: int) -> float:
        """Calculate cost for embedding generation."""
        return input_tokens * self.PRICING['titan_embed_input']

    def calculate_generation_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int
    ) -> float:
        """Calculate cost for text generation."""
        if 'haiku' in model.lower():
            input_cost = input_tokens * self.PRICING['haiku_input']
            output_cost = output_tokens * self.PRICING['haiku_output']
        else:  # sonnet
            input_cost = input_tokens * self.PRICING['sonnet_input']
            output_cost = output_tokens * self.PRICING['sonnet_output']

        return input_cost + output_cost

    def calculate_dynamodb_cost(
        self,
        reads: int = 0,
        writes: int = 0
    ) -> float:
        """Calculate DynamoDB operation cost."""
        read_cost = reads * self.PRICING['dynamodb_read']
        write_cost = writes * self.PRICING['dynamodb_write']
        return read_cost + write_cost

    def calculate_s3_cost(
        self,
        gets: int = 0,
        puts: int = 0
    ) -> float:
        """Calculate S3 operation cost."""
        get_cost = gets * self.PRICING['s3_get']
        put_cost = puts * self.PRICING['s3_put']
        return get_cost + put_cost

    def track_query_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        model: str,
        cached: bool = False
    ):
        """Track cost for a query."""
        if cached:
            # Only DynamoDB read cost
            cost = self.calculate_dynamodb_cost(reads=1)
            saved = self.calculate_generation_cost(model, input_tokens, output_tokens)

            self.metrics.record_optimization_savings(
                'answer_cache',
                tokens_saved=input_tokens + output_tokens,
                cost_saved_usd=saved
            )
        else:
            cost = self.calculate_generation_cost(model, input_tokens, output_tokens)

        self.metrics.record_cost_metric(
            'generation',
            cost,
            {'model': model, 'cached': cached}
        )
