<?php

declare(strict_types=1);

/**
 * Все маршруты приложения.
 * Формат: 'МЕТОД' => ['/путь' => ['ИмяКонтроллера', 'метод']]
 */

return [
    'GET' => [
        '/'         => ['HomeController', 'index'],
        '/login'    => ['AuthController', 'showLogin'],
        '/register' => ['AuthController', 'showRegister'],
    ],
    'POST' => [
        '/login'    => ['AuthController', 'login'],
        '/register' => ['AuthController', 'register'],
        '/logout'   => ['AuthController', 'logout'],
    ],
];
