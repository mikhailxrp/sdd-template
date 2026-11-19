<?php
/**
 * Локальная конфигурация WordPress для OpenServer.
 *
 * Скопируй в wp-config-local.php (файл в .gitignore) и подключи в wp-config.php:
 *   if ( file_exists( __DIR__ . '/wp-config-local.php' ) ) {
 *       require_once __DIR__ . '/wp-config-local.php';
 *   }
 *
 * Никогда не коммить реальные пароли и ключи (CORE-10).
 */

define( 'DB_NAME', 'project_local' );
define( 'DB_USER', 'root' );
define( 'DB_PASSWORD', '' );
define( 'DB_HOST', 'MySQL-8.2' ); // или 127.0.0.1 / localhost — зависит от модуля OpenServer

define( 'WP_ENVIRONMENT_TYPE', 'local' );
define( 'WP_DEBUG', true );
define( 'WP_DEBUG_LOG', true );
define( 'WP_DEBUG_DISPLAY', false );
@ini_set( 'display_errors', '0' );

// Для отладки скриптов без кэша
define( 'SCRIPT_DEBUG', true );
