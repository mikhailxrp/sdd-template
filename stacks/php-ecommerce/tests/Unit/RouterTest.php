<?php

declare(strict_types=1);

namespace Tests\Unit;

use PHPUnit\Framework\TestCase;

final class RouterTest extends TestCase
{
    public function testMatchesStaticPath(): void
    {
        $params = [];

        $this->assertTrue(matchPattern('/login', '/login', $params));
        $this->assertSame([], $params);
    }

    public function testMatchesDynamicSegment(): void
    {
        $params = [];

        $this->assertTrue(matchPattern('/products/{id}', '/products/42', $params));
        $this->assertSame(['id' => '42'], $params);
    }

    public function testRejectsNonMatchingPath(): void
    {
        $params = [];

        $this->assertFalse(matchPattern('/products/{id}', '/products', $params));
    }

    public function testMatchRouteFindsHandlerByMethodAndPath(): void
    {
        $routes = [
            'GET' => [
                '/products/{id}' => ['ProductController', 'show'],
            ],
        ];

        $match = matchRoute($routes, 'GET', '/products/7');

        $this->assertNotNull($match);
        $this->assertSame(['ProductController', 'show'], $match['handler']);
        $this->assertSame(['id' => '7'], $match['params']);
    }

    public function testMatchRouteReturnsNullForUnknownPath(): void
    {
        $routes = ['GET' => ['/products/{id}' => ['ProductController', 'show']]];

        $this->assertNull(matchRoute($routes, 'GET', '/unknown'));
    }

    public function testMatchRouteReturnsNullForWrongMethod(): void
    {
        $routes = ['GET' => ['/products/{id}' => ['ProductController', 'show']]];

        $this->assertNull(matchRoute($routes, 'POST', '/products/7'));
    }
}
