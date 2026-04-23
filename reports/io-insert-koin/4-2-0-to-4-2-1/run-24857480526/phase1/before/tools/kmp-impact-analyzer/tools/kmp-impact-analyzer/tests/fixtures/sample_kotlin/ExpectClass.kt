package com.example.common

expect class DatabaseDriverFactory {
    fun createDriver(): Any
}
