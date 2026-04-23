package com.example.common

import io.ktor.client.HttpClient
import io.ktor.client.request.get

class ExpenseRepoImpl(private val client: HttpClient) {
    suspend fun getExpenses(): List<String> {
        return client.get("https://api.example.com/expenses").body()
    }
}
