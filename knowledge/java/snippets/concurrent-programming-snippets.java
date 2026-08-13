package com.example.concurrent;

import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

/**
 * Java 并发编程代码示例
 */
public class ConcurrentSnippets {

    // 1. 线程池配置
    static ExecutorService threadPool = new ThreadPoolExecutor(
        4,  // 核心线程数
        8,  // 最大线程数
        60L, TimeUnit.SECONDS,
        new LinkedBlockingQueue<>(100),
        new ThreadFactoryBuilder().setNameFormat("worker-%d").build(),
        new ThreadPoolExecutor.CallerRunsPolicy()
    );

    // 2. 原子操作
    static AtomicInteger counter = new AtomicInteger(0);
    static AtomicLong totalAmount = new AtomicLong(0);

    // 3. 读写锁
    static ReadWriteLock rwLock = new ReentrantReadWriteLock();
    static Map<String, Object> cache = new HashMap<>();

    public static Object getCache(String key) {
        rwLock.readLock().lock();
        try {
            return cache.get(key);
        } finally {
            rwLock.readLock().unlock();
        }
    }

    public static void putCache(String key, Object value) {
        rwLock.writeLock().lock();
        try {
            cache.put(key, value);
        } finally {
            rwLock.writeLock().unlock();
        }
    }

    // 4. CompletableFuture
    public static CompletableFuture<String> fetchAdAsync(String adId) {
        return CompletableFuture.supplyAsync(() -> {
            // 模拟异步获取广告
            return "Ad-" + adId;
        }, threadPool);
    }

    // 5. 分布式锁
    public static boolean tryLock(String lockKey) {
        return Jedis.set("lock:" + lockKey, "1", new SetParams().nx().ex(10)) != null;
    }
}
