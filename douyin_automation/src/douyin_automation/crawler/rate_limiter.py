"""
请求频率限制器
使用滑动窗口算法，确保每分钟请求次数不超过指定上限（默认30次）
"""

import threading
import time
from collections import deque


class RateLimiter:
    """
    基于滑动窗口算法的请求频率限制器。
    线程安全，维护最近60秒内的请求时间戳列表。
    """

    def __init__(self, max_requests: int = 30, window_seconds: float = 60.0):
        """
        初始化频率限制器。

        :param max_requests: 时间窗口内允许的最大请求数，默认30次
        :param window_seconds: 滑动窗口大小（秒），默认60秒
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        # 使用 deque 存储请求时间戳，便于高效地从头部移除过期记录
        self._timestamps: deque[float] = deque()
        self._lock = threading.Lock()

    def _evict_expired(self, now: float) -> None:
        """移除窗口外的过期时间戳（调用前需持有锁）"""
        cutoff = now - self.window_seconds
        while self._timestamps and self._timestamps[0] <= cutoff:
            self._timestamps.popleft()

    def acquire(self) -> None:
        """
        获取一次请求许可。
        若当前窗口内请求数已达上限，则阻塞等待直到可以发出请求。
        """
        while True:
            with self._lock:
                now = time.time()
                self._evict_expired(now)

                if len(self._timestamps) < self.max_requests:
                    # 窗口内还有余量，直接记录并返回
                    self._timestamps.append(now)
                    return

                # 窗口已满，计算需要等待的时间
                # 最早的请求时间戳 + 窗口大小 = 最早可以发出下一个请求的时间
                oldest = self._timestamps[0]
                wait_time = (oldest + self.window_seconds) - now

            # 在锁外等待，避免长时间持锁
            if wait_time > 0:
                time.sleep(wait_time)
            # 等待后重新检查（循环）

    def get_request_count(self, window_seconds: float = 60.0) -> int:
        """
        返回指定时间窗口内的请求数量（用于测试验证）。

        :param window_seconds: 查询的时间窗口大小（秒），默认60秒
        :return: 窗口内的请求数量
        """
        with self._lock:
            now = time.time()
            cutoff = now - window_seconds
            # 统计在窗口内的时间戳数量
            return sum(1 for ts in self._timestamps if ts > cutoff)
