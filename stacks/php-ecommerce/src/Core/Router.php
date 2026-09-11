<?php

declare(strict_types=1);

require_once __DIR__ . '/Request.php';

/**
 * Маршрутизатор.
 * Читает config/routes.php, матчит запрос, вызывает контроллер.
 */

function loadRoutes(string $routesFile): array
{
    if (!is_readable($routesFile)) {
        throw new RuntimeException("Файл маршрутов недоступен: {$routesFile}");
    }
    $routes = require $routesFile;
    if (!is_array($routes)) {
        throw new RuntimeException('config/routes.php должен возвращать массив.');
    }
    return $routes;
}

function matchRoute(array $routes, string $method, string $path): ?array
{
    $methodRoutes = $routes[$method] ?? null;
    if (!is_array($methodRoutes)) {
        return null;
    }

    foreach ($methodRoutes as $pattern => $handler) {
        $params = [];
        if (matchPattern($pattern, $path, $params)) {
            return ['handler' => $handler, 'params' => $params];
        }
    }

    return null;
}

function matchPattern(string $pattern, string $path, array &$params): bool
{
    $regex = '#^' . preg_replace('#\{([a-zA-Z_][a-zA-Z0-9_]*)\}#', '(?P<$1>[^/]+)', $pattern) . '$#';
    if (preg_match($regex, $path, $matches) !== 1) {
        return false;
    }
    foreach ($matches as $key => $value) {
        if (!is_int($key) && is_string($value)) {
            $params[$key] = $value;
        }
    }
    return true;
}

function pathExistsInOtherMethod(array $routes, string $method, string $path): bool
{
    foreach ($routes as $routeMethod => $methodRoutes) {
        if (strtoupper($routeMethod) === $method || !is_array($methodRoutes)) {
            continue;
        }
        foreach ($methodRoutes as $pattern => $handler) {
            $params = [];
            if (matchPattern($pattern, $path, $params)) {
                return true;
            }
        }
    }
    return false;
}

function invokeControllerAction(object $controller, string $action, array $params): mixed
{
    $reflection = new ReflectionMethod($controller, $action);
    $args = [];
    foreach ($reflection->getParameters() as $parameter) {
        $name = $parameter->getName();
        if (array_key_exists($name, $params)) {
            $args[] = $params[$name];
        } elseif ($parameter->isDefaultValueAvailable()) {
            $args[] = $parameter->getDefaultValue();
        } else {
            throw new RuntimeException("Отсутствует параметр маршрута: {$name}");
        }
    }
    return $reflection->invokeArgs($controller, $args);
}

function dispatch(array $routes): void
{
    $method = requestMethod();
    $path   = requestPath();

    $match = matchRoute($routes, $method, $path);
    if ($match === null) {
        $statusCode = pathExistsInOtherMethod($routes, $method, $path) ? 405 : 404;
        http_response_code($statusCode);
        echo $statusCode === 405 ? '405 Method Not Allowed' : '404 Not Found';
        return;
    }

    [$controllerName, $action] = $match['handler'];
    $params = $match['params'];

    $controllerClass = "App\\Controllers\\{$controllerName}";
    if (!class_exists($controllerClass)) {
        throw new RuntimeException("Контроллер не найден: {$controllerClass}");
    }

    $controller = new $controllerClass();
    if (!method_exists($controller, $action)) {
        throw new RuntimeException("Метод {$action} не найден в {$controllerClass}");
    }

    invokeControllerAction($controller, $action, $params);
}
