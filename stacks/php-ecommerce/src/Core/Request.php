<?php

declare(strict_types=1);

/**
 * Хелперы для работы с HTTP-запросом.
 */

function requestMethod(): string
{
    return strtoupper($_SERVER['REQUEST_METHOD'] ?? 'GET');
}

function requestPath(): string
{
    $uri  = $_SERVER['REQUEST_URI'] ?? '/';
    $path = parse_url($uri, PHP_URL_PATH);
    return is_string($path) ? rtrim($path, '/') ?: '/' : '/';
}

function isPost(): bool
{
    return requestMethod() === 'POST';
}

function isGet(): bool
{
    return requestMethod() === 'GET';
}
