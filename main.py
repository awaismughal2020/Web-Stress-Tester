#!/usr/bin/env python3
"""
Advanced Stress Test Script with Performance Analysis
Target: Configurable web application testing with detailed insights
"""

import asyncio
import aiohttp
import time
import statistics
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import json
import random
import sys
from datetime import datetime
import threading


@dataclass
class TestResult:
    """Store results of individual test requests"""
    status_code: int
    response_time: float
    content_length: int
    timestamp: float
    thread_id: int = 0
    error: str = ""
    ttfb: float = 0  # Time to first byte


@dataclass
class TestReport:
    """Store comprehensive test results with performance insights"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    response_times: List[float] = field(default_factory=list)
    status_codes: Dict[int, int] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)
    end_time: float = 0
    requests_per_second: float = 0
    results: List[TestResult] = field(default_factory=list)
    peak_rps: float = 0
    slowest_requests: List[TestResult] = field(default_factory=list)


class PerformanceAnalyzer:
    """Analyze performance data and provide insights"""

    @staticmethod
    def calculate_performance_grade(avg_response_time: float, success_rate: float, rps: float) -> str:
        """Calculate overall performance grade"""
        score = 0

        # Response time scoring (40% weight)
        if avg_response_time < 0.2:
            score += 40
        elif avg_response_time < 0.5:
            score += 35
        elif avg_response_time < 1.0:
            score += 25
        elif avg_response_time < 2.0:
            score += 15
        else:
            score += 5

        # Success rate scoring (40% weight)
        if success_rate >= 99.5:
            score += 40
        elif success_rate >= 95:
            score += 35
        elif success_rate >= 90:
            score += 25
        elif success_rate >= 75:
            score += 15
        else:
            score += 5

        # Throughput scoring (20% weight)
        if rps >= 50:
            score += 20
        elif rps >= 20:
            score += 18
        elif rps >= 10:
            score += 15
        elif rps >= 5:
            score += 10
        else:
            score += 5

        if score >= 90:
            return "A+ (Excellent)"
        elif score >= 80:
            return "A (Very Good)"
        elif score >= 70:
            return "B (Good)"
        elif score >= 60:
            return "C (Fair)"
        elif score >= 50:
            return "D (Poor)"
        else:
            return "F (Critical)"

    @staticmethod
    def analyze_performance_trends(results: List[TestResult]) -> Dict[str, Any]:
        """Analyze performance trends over time"""
        if not results:
            return {}

        # Sort by timestamp
        sorted_results = sorted(results, key=lambda x: x.timestamp)

        # Split into time windows
        start_time = sorted_results[0].timestamp
        end_time = sorted_results[-1].timestamp
        duration = end_time - start_time

        if duration < 1:
            return {"trend": "insufficient_data"}

        # Create time buckets
        num_buckets = min(10, int(duration))
        bucket_size = duration / num_buckets
        buckets = [[] for _ in range(num_buckets)]

        for result in sorted_results:
            bucket_idx = min(int((result.timestamp - start_time) / bucket_size), num_buckets - 1)
            buckets[bucket_idx].append(result)

        # Calculate metrics per bucket
        bucket_metrics = []
        for bucket in buckets:
            if bucket:
                avg_response_time = statistics.mean([r.response_time for r in bucket])
                success_rate = sum(1 for r in bucket if r.status_code == 200) / len(bucket) * 100
                bucket_metrics.append({
                    'avg_response_time': avg_response_time,
                    'success_rate': success_rate,
                    'count': len(bucket)
                })

        if len(bucket_metrics) < 2:
            return {"trend": "insufficient_data"}

        # Analyze trends
        response_times = [b['avg_response_time'] for b in bucket_metrics]
        success_rates = [b['success_rate'] for b in bucket_metrics]

        # Simple trend analysis
        rt_trend = "stable"
        if response_times[-1] > response_times[0] * 1.5:
            rt_trend = "degrading"
        elif response_times[-1] < response_times[0] * 0.8:
            rt_trend = "improving"

        sr_trend = "stable"
        if success_rates[-1] < success_rates[0] - 10:
            sr_trend = "degrading"
        elif success_rates[-1] > success_rates[0] + 10:
            sr_trend = "improving"

        return {
            'response_time_trend': rt_trend,
            'success_rate_trend': sr_trend,
            'bucket_metrics': bucket_metrics,
            'performance_degradation': response_times[-1] > response_times[0] * 2
        }

    @staticmethod
    def identify_bottlenecks(report: TestReport) -> List[str]:
        """Identify potential performance bottlenecks"""
        bottlenecks = []

        if not report.response_times:
            return ["No response data available"]

        avg_response_time = statistics.mean(report.response_times)
        success_rate = (report.successful_requests / report.total_requests) * 100

        # Response time analysis
        if avg_response_time > 2.0:
            bottlenecks.append("HIGH_RESPONSE_TIME: Server is very slow (>2s average)")
        elif avg_response_time > 1.0:
            bottlenecks.append("MODERATE_RESPONSE_TIME: Server response time is concerning (>1s average)")

        # Success rate analysis
        if success_rate < 90:
            bottlenecks.append("LOW_SUCCESS_RATE: High failure rate indicates server overload")
        elif success_rate < 95:
            bottlenecks.append("MODERATE_FAILURES: Some requests failing under load")

        # Throughput analysis
        if report.requests_per_second < 5:
            bottlenecks.append("LOW_THROUGHPUT: Server can't handle concurrent requests efficiently")

        # Variability analysis
        if len(report.response_times) > 1:
            std_dev = statistics.stdev(report.response_times)
            if std_dev > avg_response_time * 0.5:
                bottlenecks.append("HIGH_VARIABILITY: Response times are inconsistent")

        # Error analysis
        error_types = {}
        for error in report.errors:
            error_types[error] = error_types.get(error, 0) + 1

        if "Connection" in str(error_types):
            bottlenecks.append("CONNECTION_ISSUES: Server rejecting connections")

        if not bottlenecks:
            bottlenecks.append("NO_MAJOR_BOTTLENECKS: System performing within acceptable limits")

        return bottlenecks

    @staticmethod
    def capacity_recommendations(report: TestReport, test_type: str) -> Dict[str, Any]:
        """Provide capacity and optimization recommendations"""
        if not report.response_times:
            return {"error": "No data available"}

        avg_response_time = statistics.mean(report.response_times)
        success_rate = (report.successful_requests / report.total_requests) * 100

        recommendations = {
            'current_capacity': {},
            'scaling_recommendations': [],
            'optimization_suggestions': []
        }

        # Current capacity assessment
        if test_type == "concurrent":
            concurrent_users = report.total_requests  # Simplified assumption
            if success_rate >= 95 and avg_response_time < 1.0:
                recommendations['current_capacity'][
                    'concurrent_users'] = f"Can handle {concurrent_users} concurrent users well"
                recommendations['current_capacity'][
                    'estimated_max'] = f"Likely can handle {concurrent_users * 2}-{concurrent_users * 3} users"
            elif success_rate >= 90:
                recommendations['current_capacity'][
                    'concurrent_users'] = f"Struggling with {concurrent_users} concurrent users"
                recommendations['current_capacity'][
                    'estimated_max'] = f"Maximum capacity around {concurrent_users} users"
            else:
                recommendations['current_capacity'][
                    'concurrent_users'] = f"Overloaded with {concurrent_users} concurrent users"
                recommendations['current_capacity'][
                    'estimated_max'] = f"Maximum capacity below {concurrent_users} users"

        # Scaling recommendations
        if avg_response_time > 1.0:
            recommendations['scaling_recommendations'].append("Consider horizontal scaling (more servers)")
            recommendations['scaling_recommendations'].append("Implement load balancing")

        if success_rate < 95:
            recommendations['scaling_recommendations'].append("Increase server resources (CPU/Memory)")
            recommendations['scaling_recommendations'].append("Optimize database connections")

        # Optimization suggestions
        if avg_response_time > 0.5:
            recommendations['optimization_suggestions'].append("Profile application code for slow functions")
            recommendations['optimization_suggestions'].append("Implement caching (Redis/Memcached)")
            recommendations['optimization_suggestions'].append("Optimize database queries")

        if report.requests_per_second < 20:
            recommendations['optimization_suggestions'].append("Consider asynchronous processing")
            recommendations['optimization_suggestions'].append("Implement connection pooling")

        return recommendations


class StressTester:
    def __init__(self, base_url: str = "https://google.com"):
        self.base_url = base_url.rstrip('/')
        self.session = None
        self.analyzer = PerformanceAnalyzer()

    def setup_session(self, timeout: int = 30):
        """Setup requests session with appropriate settings"""
        self.session = requests.Session()
        self.session.timeout = timeout
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        })

    def make_request(self, endpoint: str = "/") -> TestResult:
        """Make a single HTTP request and return results"""
        url = f"{self.base_url}{endpoint}"
        start_time = time.time()
        thread_id = threading.current_thread().ident

        try:
            response = self.session.get(url)
            response_time = time.time() - start_time

            return TestResult(
                status_code=response.status_code,
                response_time=response_time,
                content_length=len(response.content),
                timestamp=start_time,
                thread_id=thread_id,
                ttfb=response_time  # Simplified TTFB
            )
        except Exception as e:
            response_time = time.time() - start_time
            return TestResult(
                status_code=0,
                response_time=response_time,
                content_length=0,
                error=str(e),
                timestamp=start_time,
                thread_id=thread_id
            )

    def sequential_test(self, num_requests: int = 100, delay: float = 0.1) -> TestReport:
        """Run sequential requests test"""
        print(f"🔄 Running sequential test with {num_requests} requests...")

        self.setup_session()
        report = TestReport()
        report.start_time = time.time()

        for i in range(num_requests):
            if i % 10 == 0:
                print(f"   Progress: {i}/{num_requests} requests completed")

            result = self.make_request()
            self._update_report(report, result)

            if delay > 0:
                time.sleep(delay)

        report.end_time = time.time()
        self._finalize_report(report)
        return report

    def concurrent_test(self, num_requests: int = 100, max_workers: int = 10) -> TestReport:
        """Run concurrent requests test using ThreadPoolExecutor"""
        print(f"🚀 Running concurrent test with {num_requests} requests and {max_workers} workers...")

        self.setup_session()
        report = TestReport()
        report.start_time = time.time()

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(self.make_request) for _ in range(num_requests)]

            for i, future in enumerate(as_completed(futures)):
                if i % 10 == 0:
                    print(f"   Progress: {i}/{num_requests} requests completed")

                result = future.result()
                self._update_report(report, result)

        report.end_time = time.time()
        self._finalize_report(report)
        return report

    def ramp_up_test(self, max_users: int = 50, ramp_duration: int = 30,
                     test_duration: int = 60) -> TestReport:
        """Gradually ramp up the number of concurrent users"""
        print(f"📈 Running ramp-up test: 0 to {max_users} users over {ramp_duration}s, then {test_duration}s at peak")

        self.setup_session()
        report = TestReport()
        report.start_time = time.time()

        # Phase 1: Ramp up
        ramp_step = max_users / ramp_duration
        for second in range(ramp_duration):
            current_users = max(1, int(ramp_step * (second + 1)))  # Fix: ensure at least 1 user
            print(f"   Ramp-up: {current_users} concurrent users")

            with ThreadPoolExecutor(max_workers=current_users) as executor:
                futures = [executor.submit(self.make_request) for _ in range(current_users)]

                for future in as_completed(futures):
                    result = future.result()
                    self._update_report(report, result)

            time.sleep(1)

        # Phase 2: Sustained load
        print(f"   Sustained load: {max_users} users for {test_duration} seconds")
        for second in range(test_duration):
            with ThreadPoolExecutor(max_workers=max_users) as executor:
                futures = [executor.submit(self.make_request) for _ in range(max_users)]

                for future in as_completed(futures):
                    result = future.result()
                    self._update_report(report, result)

            if second % 10 == 0:
                print(f"   Sustained phase: {second}/{test_duration} seconds")
            time.sleep(1)

        report.end_time = time.time()
        self._finalize_report(report)
        return report

    def _update_report(self, report: TestReport, result: TestResult):
        """Update report with individual test result"""
        report.total_requests += 1
        report.response_times.append(result.response_time)
        report.results.append(result)

        if result.status_code == 0:
            report.failed_requests += 1
            report.errors.append(result.error)
        else:
            report.successful_requests += 1

        if result.status_code in report.status_codes:
            report.status_codes[result.status_code] += 1
        else:
            report.status_codes[result.status_code] = 1

    def _finalize_report(self, report: TestReport):
        """Calculate final statistics for the report"""
        total_time = report.end_time - report.start_time
        report.requests_per_second = report.total_requests / total_time if total_time > 0 else 0

        # Find slowest requests
        sorted_results = sorted(report.results, key=lambda x: x.response_time, reverse=True)
        report.slowest_requests = sorted_results[:5]

    def print_enhanced_report(self, report: TestReport, test_name: str):
        """Print enhanced test report with insights"""
        print(f"\n{'=' * 80}")
        print(f"🎯 PERFORMANCE ANALYSIS - {test_name.upper()}")
        print(f"{'=' * 80}")

        total_time = report.end_time - report.start_time
        success_rate = (report.successful_requests / report.total_requests) * 100
        avg_response_time = statistics.mean(report.response_times) if report.response_times else 0

        # Performance Grade
        grade = self.analyzer.calculate_performance_grade(avg_response_time, success_rate, report.requests_per_second)
        print(f"📊 PERFORMANCE GRADE: {grade}")

        # Basic Metrics
        print(f"\n📈 BASIC METRICS:")
        print(f"   Test Duration: {total_time:.2f} seconds")
        print(f"   Total Requests: {report.total_requests:,}")
        print(f"   Successful: {report.successful_requests:,} ({success_rate:.1f}%)")
        print(f"   Failed: {report.failed_requests:,} ({100 - success_rate:.1f}%)")
        print(f"   Throughput: {report.requests_per_second:.1f} requests/second")

        # Response Time Analysis
        if report.response_times:
            print(f"\n⏱️  RESPONSE TIME ANALYSIS:")
            sorted_times = sorted(report.response_times)

            print(f"   Average: {avg_response_time:.3f}s")
            print(f"   Median: {statistics.median(report.response_times):.3f}s")
            print(f"   Fastest: {min(report.response_times):.3f}s")
            print(f"   Slowest: {max(report.response_times):.3f}s")

            if len(report.response_times) > 1:
                std_dev = statistics.stdev(report.response_times)
                print(f"   Std Deviation: {std_dev:.3f}s")
                print(f"   Variability: {'HIGH' if std_dev > avg_response_time * 0.5 else 'LOW'}")

            # Percentiles
            p90_idx = int(len(sorted_times) * 0.90)
            p95_idx = int(len(sorted_times) * 0.95)
            p99_idx = int(len(sorted_times) * 0.99)

            print(f"   90th percentile: {sorted_times[p90_idx]:.3f}s")
            print(f"   95th percentile: {sorted_times[p95_idx]:.3f}s")
            print(f"   99th percentile: {sorted_times[p99_idx]:.3f}s")

        # Performance Interpretation
        print(f"\n💡 PERFORMANCE INTERPRETATION:")
        if avg_response_time < 0.2:
            print("   ✅ EXCELLENT: Very fast response times")
        elif avg_response_time < 0.5:
            print("   ✅ GOOD: Fast response times")
        elif avg_response_time < 1.0:
            print("   ⚠️  ACCEPTABLE: Moderate response times")
        elif avg_response_time < 2.0:
            print("   ⚠️  SLOW: Response times are concerning")
        else:
            print("   ❌ CRITICAL: Very slow response times")

        if success_rate >= 99:
            print("   ✅ EXCELLENT: Very high reliability")
        elif success_rate >= 95:
            print("   ✅ GOOD: High reliability")
        elif success_rate >= 90:
            print("   ⚠️  ACCEPTABLE: Moderate reliability")
        else:
            print("   ❌ CRITICAL: Low reliability")

        # Bottleneck Analysis
        bottlenecks = self.analyzer.identify_bottlenecks(report)
        print(f"\n🔍 BOTTLENECK ANALYSIS:")
        for bottleneck in bottlenecks:
            if "NO_MAJOR_BOTTLENECKS" in bottleneck:
                print(f"   ✅ {bottleneck}")
            else:
                print(f"   ⚠️  {bottleneck}")

        # Capacity Recommendations
        recommendations = self.analyzer.capacity_recommendations(report, test_name)
        if 'current_capacity' in recommendations:
            print(f"\n🎯 CAPACITY ASSESSMENT:")
            for key, value in recommendations['current_capacity'].items():
                print(f"   • {value}")

        if recommendations.get('scaling_recommendations'):
            print(f"\n📈 SCALING RECOMMENDATIONS:")
            for rec in recommendations['scaling_recommendations']:
                print(f"   • {rec}")

        if recommendations.get('optimization_suggestions'):
            print(f"\n⚡ OPTIMIZATION SUGGESTIONS:")
            for suggestion in recommendations['optimization_suggestions']:
                print(f"   • {suggestion}")

        # Status Code Distribution
        print(f"\n📊 STATUS CODE DISTRIBUTION:")
        for status_code, count in sorted(report.status_codes.items()):
            status_meaning = {
                200: "OK", 201: "Created", 404: "Not Found",
                500: "Server Error", 502: "Bad Gateway", 503: "Service Unavailable"
            }.get(status_code, "Unknown")
            print(f"   {status_code} ({status_meaning}): {count:,} requests")

        # Slowest Requests
        if report.slowest_requests:
            print(f"\n🐌 SLOWEST REQUESTS:")
            for i, req in enumerate(report.slowest_requests, 1):
                print(f"   {i}. {req.response_time:.3f}s (Status: {req.status_code})")

        # Performance Trends
        trends = self.analyzer.analyze_performance_trends(report.results)
        if trends and trends.get('response_time_trend'):
            print(f"\n📈 PERFORMANCE TRENDS:")
            print(f"   Response Time Trend: {trends['response_time_trend'].upper()}")
            print(f"   Success Rate Trend: {trends['success_rate_trend'].upper()}")

            if trends.get('performance_degradation'):
                print("   ⚠️  WARNING: Significant performance degradation detected!")


def main(url):
    parser = argparse.ArgumentParser(description='Advanced stress test with performance insights')
    parser.add_argument('--url', default=url,
                        help='Base URL to test')
    parser.add_argument('--requests', type=int, default=100,
                        help='Number of requests per test')
    parser.add_argument('--workers', type=int, default=10,
                        help='Number of concurrent workers')
    parser.add_argument('--test', choices=['sequential', 'concurrent', 'ramp', 'all'],
                        default='all', help='Type of test to run')

    args = parser.parse_args()

    tester = StressTester(args.url)

    print(f"🎯 Starting Advanced Stress Test")
    print(f"Target: {args.url}")
    print(f"Connectivity: {'✅ REACHABLE' if test_connectivity(args.url) else '❌ UNREACHABLE'}")

    if args.test in ['sequential', 'all']:
        report = tester.sequential_test(args.requests)
        tester.print_enhanced_report(report, 'Sequential Test')

    if args.test in ['concurrent', 'all']:
        report = tester.concurrent_test(args.requests, args.workers)
        tester.print_enhanced_report(report, 'Concurrent Test')

    if args.test in ['ramp', 'all']:
        report = tester.ramp_up_test(args.workers, 30, 60)
        tester.print_enhanced_report(report, 'Ramp-up Test')


def test_connectivity(url: str) -> bool:
    """Test if the target URL is reachable"""
    try:
        response = requests.get(url, timeout=10)
        return response.status_code < 500
    except:
        return False


if __name__ == "__main__":
    main('https://www.google.com')
