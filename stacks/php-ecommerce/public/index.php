<?php

declare(strict_types=1);

/**
 * Front controller — единственная точка входа.
 * Document root = public/
 */

require_once dirname(__DIR__) . '/config/config.php';
require_once ROOT_PATH . '/src/Core/Router.php';
require_once ROOT_PATH . '/src/Core/ErrorHandlers.php';

// Глобальные обработчики ошибок PHP
registerAppErrorHandlers();

// Security-заголовки — на каждый ответ
sendSecurityHeaders();

// Автозагрузка классов App\*
spl_autoload_register(static function (string $class): void {
    $prefix = 'App\\';
    if (!str_starts_with($class, $prefix)) {
        return;
    }
    $relative = str_replace('\\', DIRECTORY_SEPARATOR, substr($class, strlen($prefix)));
    $file = ROOT_PATH . '/src/' . $relative . '.php';
    if (is_readable($file)) {
        require_once $file;
    }
});

ensureSessionStarted();

$routes = loadRoutes(ROOT_PATH . '/config/routes.php');
dispatch($routes);
