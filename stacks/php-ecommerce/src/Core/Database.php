<?php

declare(strict_types=1);

require_once __DIR__ . '/functions.php';

/**
 * Подключение к MySQL через PDO.
 * Singleton — одно соединение на запрос.
 */
function getPdo(): PDO
{
    static $pdo = null;
    if ($pdo instanceof PDO) {
        return $pdo;
    }

    if (!extension_loaded('pdo_mysql')) {
        throw new RuntimeException(
            'Не загружено расширение pdo_mysql. Включите в php.ini: extension=pdo_mysql'
        );
    }

    $dsn = sprintf(
        'mysql:host=%s;dbname=%s;charset=%s',
        env('DB_HOST'),
        env('DB_NAME'),
        env('DB_CHARSET')
    );

    $pdo = new PDO($dsn, env('DB_USER'), env('DB_PASS'), [
        PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
        PDO::ATTR_EMULATE_PREPARES   => false,
    ]);

    return $pdo;
}
