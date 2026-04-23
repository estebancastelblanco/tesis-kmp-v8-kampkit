package com.example.common

import android.content.Context

actual class DatabaseDriverFactory(private val context: Context) {
    actual fun createDriver(): Any {
        return context.getDatabasePath("app.db")
    }
}
