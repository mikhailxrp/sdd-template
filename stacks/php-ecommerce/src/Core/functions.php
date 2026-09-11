<?php

declare(strict_types=1);

/**
 * Общие хелперы приложения.
 */

function loadEnv(string $path): void
{
    if (!is_readable($path)) {
        throw new RuntimeException("Файл окружения не найден: {$path}");
    }

    foreach (file($path, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) as $line) {
        $line = trim($line);
        if ($line === '' || str_starts_with($line, '#') || !str_contains($line, '=')) {
            continue;
        }
        [$key, $value] = explode('=', $line, 2);
        $key   = trim($key);
        $value = trim(trim($value), '"\'');
        $_ENV[$key] = $value;
        putenv("{$key}={$value}");
    }
}

function env(string $key, ?string $default = null): string
{
    $value = $_ENV[$key] ?? getenv($key);
    if ($value === false || $value === null || $value === '') {
        if ($default !== null) {
            return $default;
        }
        throw new RuntimeException("Отсутствует переменная окружения: {$key}");
    }
    return $value;
}

function ensureSessionStarted(): void
{
    if (session_status() === PHP_SESSION_ACTIVE) {
        return;
    }
    if (!headers_sent()) {
        session_set_cookie_params([
            'lifetime' => 0,
            'path'     => '/',
            'secure'   => defined('APP_ENV') && APP_ENV === 'production',
            'httponly' => true,
            'samesite' => 'Lax',
        ]);
        session_start();
    }
}

function regenerateSession(): void
{
    ensureSessionStarted();
    session_regenerate_id(true);
    unset($_SESSION['csrf_token']);
}

function sendSecurityHeaders(): void
{
    if (headers_sent()) {
        return;
    }
    header('X-Content-Type-Options: nosniff');
    header('X-Frame-Options: DENY');
    header("Content-Security-Policy: frame-ancestors 'none'");
    header('Referrer-Policy: strict-origin-when-cross-origin');
}

function redirect(string $path): void
{
    header("Location: {$path}");
    exit;
}

function isAuthenticated(): bool
{
    ensureSessionStarted();
    return normalizeUserId($_SESSION['user_id'] ?? null) !== null;
}

function requireAuth(): void
{
    if (!isAuthenticated()) {
        redirect('/login');
    }
}

function redirectIfAuthenticated(): void
{
    if (isAuthenticated()) {
        redirect('/dashboard');
    }
}

function setFlash(string $key, string $message): void
{
    ensureSessionStarted();
    $_SESSION['flash'][$key] = $message;
}

function getFlash(string $key): ?string
{
    ensureSessionStarted();
    $flash = $_SESSION['flash'][$key] ?? null;
    if (!is_string($flash) || $flash === '') {
        return null;
    }
    unset($_SESSION['flash'][$key]);
    return $flash;
}

function normalizeUserId(mixed $value): ?int
{
    if (is_int($value) && $value > 0) {
        return $value;
    }
    if (is_string($value) && ctype_digit($value)) {
        $intValue = (int) $value;
        return $intValue > 0 ? $intValue : null;
    }
    return null;
}

function render(string $view, array $data = []): void
{
    if ($view === '' || str_contains($view, '..') || str_ends_with($view, '.php')) {
        throw new RuntimeException("Некорректное имя шаблона: {$view}");
    }

    $viewPath = ROOT_PATH . '/src/Views/' . trim($view, '/') . '.php';

    if (!is_file($viewPath)) {
        throw new RuntimeException("Шаблон не найден: {$view}. Ожидался путь: {$viewPath}");
    }

    extract($data, EXTR_SKIP);
    require $viewPath;
}

function e(string $value): string
{
    return htmlspecialchars($value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}

function input(string $key, mixed $default = ''): mixed
{
    return $_POST[$key] ?? $_GET[$key] ?? $default;
}

// ─── CSRF ───────────────────────────────────────────────────────────────

function csrfToken(): string
{
    ensureSessionStarted();
    if (empty($_SESSION['csrf_token'])) {
        $_SESSION['csrf_token'] = bin2hex(random_bytes(32));
    }
    return $_SESSION['csrf_token'];
}

function csrfField(): string
{
    return '<input type="hidden" name="_csrf" value="' . e(csrfToken()) . '">';
}

function verifyCsrfToken(mixed $token): bool
{
    ensureSessionStarted();
    $sessionToken = $_SESSION['csrf_token'] ?? null;
    if (!is_string($sessionToken) || !is_string($token) || $token === '') {
        return false;
    }
    return hash_equals($sessionToken, $token);
}

function requireCsrf(): void
{
    if (!verifyCsrfToken(input('_csrf'))) {
        http_response_code(419);
        exit('419 Неверный CSRF-токен. Обновите страницу и попробуйте снова.');
    }
}

// ─── Rate limiting ──────────────────────────────────────────────────────
// Файловый счётчик в storage/cache/rate-limit/ — без Redis/Memcached,
// подходит для shared-хостинга. Ключ = действие + IP клиента.

function rateLimitStoragePath(string $action): string
{
    $ip  = $_SERVER['REMOTE_ADDR'] ?? 'unknown';
    $dir = ROOT_PATH . '/storage/cache/rate-limit';
    if (!is_dir($dir) && !mkdir($dir, 0755, true) && !is_dir($dir)) {
        throw new RuntimeException("Не удалось создать директорию: {$dir}");
    }
    return $dir . '/' . sha1($action . '|' . $ip) . '.json';
}

function tooManyAttempts(string $action, int $maxAttempts, int $decaySeconds = 60): bool
{
    $path = rateLimitStoragePath($action);
    if (!is_file($path)) {
        return false;
    }
    $data = json_decode((string) file_get_contents($path), true);
    if (!is_array($data) || !isset($data['count'], $data['first_at'])) {
        return false;
    }
    if (time() - (int) $data['first_at'] > $decaySeconds) {
        return false;
    }
    return (int) $data['count'] >= $maxAttempts;
}

function hitRateLimit(string $action): void
{
    $path = rateLimitStoragePath($action);
    $data = ['count' => 1, 'first_at' => time()];

    if (is_file($path)) {
        $existing = json_decode((string) file_get_contents($path), true);
        if (is_array($existing) && isset($existing['count'], $existing['first_at'])) {
            $data = $existing;
            $data['count'] = (int) $data['count'] + 1;
        }
    }

    file_put_contents($path, json_encode($data), LOCK_EX);
}

function clearRateLimit(string $action): void
{
    $path = rateLimitStoragePath($action);
    if (is_file($path)) {
        unlink($path);
    }
}
