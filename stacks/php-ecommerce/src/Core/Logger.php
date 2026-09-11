<?php

declare(strict_types=1);

/**
 * Логгер приложения.
 * Пишет в storage/logs/app.log
 * Уровни: debug < info < warning < error
 */

function logWrite(string $level, string $message, array $context = []): void
{
    $levels = ['debug' => 0, 'info' => 1, 'warning' => 2, 'error' => 3];
    $minLevel = defined('APP_LOG_LEVEL') ? strtolower(APP_LOG_LEVEL) : 'error';

    if (($levels[$level] ?? 0) < ($levels[$minLevel] ?? 3)) {
        return;
    }

    $logDir  = defined('LOG_DIR')  ? LOG_DIR  : dirname(__DIR__, 2) . '/storage/logs';
    $logFile = defined('LOG_FILE') ? LOG_FILE : 'app.log';

    if (!is_dir($logDir)) {
        mkdir($logDir, 0755, true);
    }

    $safeContext = sanitizeLogContext($context);
    $contextJson = $safeContext !== [] ? ' | ' . json_encode($safeContext, JSON_UNESCAPED_UNICODE) : '';
    $line = sprintf("[%s] %s %s%s\n", date('c'), strtoupper($level), $message, $contextJson);

    file_put_contents($logDir . '/' . $logFile, $line, FILE_APPEND | LOCK_EX);
}

function logDebug(string $message, array $context = []): void
{
    logWrite('debug', $message, $context);
}

function logInfo(string $message, array $context = []): void
{
    logWrite('info', $message, $context);
}

function logWarning(string $message, array $context = []): void
{
    logWrite('warning', $message, $context);
}

function logError(string $message, array $context = []): void
{
    logWrite('error', $message, $context);
}

function logException(Throwable $e, array $context = []): void
{
    logWrite('error', get_class($e) . ': ' . $e->getMessage(), array_merge($context, [
        'file'  => $e->getFile(),
        'line'  => $e->getLine(),
        'trace' => array_slice(explode("\n", $e->getTraceAsString()), 0, 5),
    ]));
}

function sanitizeLogContext(mixed $data): mixed
{
    $sensitiveKeys = ['password', 'token', 'secret', 'key', 'auth', 'credential'];

    if (is_array($data)) {
        $result = [];
        foreach ($data as $k => $v) {
            $keyLower = strtolower((string) $k);
            $isSensitive = false;
            foreach ($sensitiveKeys as $sensitive) {
                if (str_contains($keyLower, $sensitive)) {
                    $isSensitive = true;
                    break;
                }
            }
            $result[$k] = $isSensitive ? '[REDACTED]' : sanitizeLogContext($v);
        }
        return $result;
    }

    if ($data instanceof Throwable) {
        return get_class($data) . ': ' . $data->getMessage();
    }

    return $data;
}
